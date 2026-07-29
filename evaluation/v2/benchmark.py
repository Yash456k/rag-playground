from __future__ import annotations

import gc
import re
import time
from pathlib import Path
from typing import Any

from .eval_lib import query_metrics, timing_summary


def relocate_model_path(model: str, artifact_root: Path) -> str:
    prefix = "/model-artifacts/"
    return str(artifact_root / model[len(prefix) :]) if model.startswith(prefix) else model


def effective_dtype(configured: str, device: str) -> str:
    if device == "cuda" and configured == "bfloat16":
        return "float16"
    return configured


def stable_exact_ranking(
    query: Any, corpus: Any, chunk_ids: list[str], top_k: int
) -> list[dict[str, Any]]:
    import numpy as np

    query_array = np.asarray(query, dtype=np.float32).reshape(-1)
    corpus_array = np.asarray(corpus, dtype=np.float32)
    query_array /= max(float(np.linalg.norm(query_array)), 1e-12)
    norms = np.linalg.norm(corpus_array, axis=1, keepdims=True)
    corpus_array = corpus_array / np.maximum(norms, 1e-12)
    scores = corpus_array @ query_array
    order = np.argsort(-scores, kind="stable")[:top_k]
    return [{"chunk_id": chunk_ids[int(i)], "score": float(scores[int(i)])} for i in order]


def build_retrieval_query(case: dict[str, Any]) -> str:
    """Mirror the API query rewriting without importing the API module."""
    prior_user_messages = [
        message["content"]
        for message in case.get("history", [])[-4:]
        if message.get("role") == "user"
    ]
    if not prior_user_messages:
        return case["question"]
    context = "\n".join(prior_user_messages)
    return (
        f"Previous user context:\n{context}\n\n"
        f"Current question:\n{case['question']}"
    )


def chunk_terms(content: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.-]{3,}", content.casefold())
        if token not in {"about", "and", "for", "from", "that", "the", "this", "with", "yash"}
    }


def select_diverse_chunks(
    candidates: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    """Mirror production's deterministic adjacent/lexical de-duplication."""
    selected: list[dict[str, Any]] = []
    selected_terms: list[set[str]] = []
    for candidate in candidates:
        terms = chunk_terms(candidate["content"])
        duplicate = False
        for existing, existing_terms in zip(selected, selected_terms, strict=True):
            union = terms | existing_terms
            similarity = len(terms & existing_terms) / len(union) if union else 0.0
            adjacent = (
                candidate["source"] == existing["source"]
                and abs(candidate["chunkIndex"] - existing["chunkIndex"]) <= 1
            )
            if similarity >= 0.60 or (adjacent and similarity >= 0.32):
                duplicate = True
                break
        if duplicate:
            continue
        selected.append(candidate)
        selected_terms.append(terms)
        if len(selected) == top_k:
            break
    if len(selected) < top_k:
        for candidate in candidates:
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) == top_k:
                break
    return selected


def diversified_exact_ranking(
    query: Any, corpus: Any, chunks: list[Any], top_k: int
) -> list[dict[str, Any]]:
    candidate_count = min(12, top_k * 3)
    ranked = stable_exact_ranking(
        query, corpus, [chunk.id for chunk in chunks], candidate_count
    )
    chunk_by_id = {chunk.id: chunk for chunk in chunks}
    candidates = [
        {
            **item,
            "source": chunk_by_id[item["chunk_id"]].source,
            "chunkIndex": chunk_by_id[item["chunk_id"]].index,
            "content": chunk_by_id[item["chunk_id"]].content,
        }
        for item in ranked
    ]
    return [
        {"chunk_id": item["chunk_id"], "score": item["score"]}
        for item in select_diverse_chunks(candidates, top_k)
    ]


def current_rss_mib() -> float | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def resolve_device(requested: str) -> str:
    if requested in {"cpu", "cuda"}:
        return requested
    try:
        import torch

        cuda = getattr(torch, "cuda", None)
        return "cuda" if cuda is not None and cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _sentence_transformer(config: Any, model_path: str, device: str, dtype: str) -> Any:
    import torch
    from sentence_transformers import SentenceTransformer

    dtype_value = {
        "float32": torch.float32,
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
    }[dtype]
    kwargs: dict[str, Any] = {
        "device": device,
        "trust_remote_code": False,
        "model_kwargs": {"dtype": dtype_value},
    }
    if config.revision:
        kwargs["revision"] = config.revision
    return SentenceTransformer(model_path, **kwargs)


def _encode(model: Any, texts: list[str]) -> Any:
    return model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def benchmark_model(
    config: Any,
    cases: list[dict[str, Any]],
    chunks: list[Any],
    *,
    artifact_root: Path,
    device: str,
    warmup: int,
    timing_runs: int,
    top_k: int,
    model_factory: Any = _sentence_transformer,
    clock: Any = time.perf_counter,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    chosen_device = resolve_device(device)
    dtype = effective_dtype(config.dtype, chosen_device)
    path = relocate_model_path(config.model, artifact_root)
    wall_start = clock()
    rss_before_load = current_rss_mib()
    if chosen_device == "cuda":
        import torch

        torch.cuda.reset_peak_memory_stats()
    load_start = clock()
    model = model_factory(config, path, chosen_device, dtype)
    warmup_text = config.query_prefix + "portfolio retrieval warmup"
    for _ in range(warmup):
        _encode(model, [warmup_text])
    load_warmup = clock() - load_start
    rss_after_warmup = current_rss_mib()
    corpus_start = clock()
    corpus_vectors = _encode(model, [config.document_prefix + chunk.content for chunk in chunks])
    corpus_seconds = clock() - corpus_start
    rss_after_corpus_encoding = current_rss_mib()
    if corpus_vectors.shape != (len(chunks), config.dimensions):
        message = (
            f"Embedding dimensions mismatch: expected {config.dimensions}, "
            f"got {corpus_vectors.shape}"
        )
        raise ValueError(message)
    rows: list[dict[str, Any]] = []
    encode_timings: list[float] = []
    retrieval_timings: list[float] = []
    end_to_end_timings: list[float] = []
    query_total_start = clock()
    for case in cases:
        query = config.query_prefix + build_retrieval_query(case)
        ranking = None
        encode_ms: list[float] = []
        retrieval_ms: list[float] = []
        end_to_end_ms: list[float] = []
        for _ in range(timing_runs):
            end_started = clock()
            encode_started = clock()
            vector = _encode(model, [query])[0]
            encode_ms.append((clock() - encode_started) * 1000)
            retrieval_started = clock()
            ranking = diversified_exact_ranking(vector, corpus_vectors, chunks, top_k)
            retrieval_ms.append((clock() - retrieval_started) * 1000)
            end_to_end_ms.append((clock() - end_started) * 1000)
        assert ranking is not None
        encode_timings.extend(encode_ms)
        retrieval_timings.extend(retrieval_ms)
        end_to_end_timings.extend(end_to_end_ms)
        rows.append(
            {
                **{
                    key: case[key]
                    for key in (
                        "id", "family_id", "tier", "split", "category",
                        "difficulty", "answerable",
                        "training_overlap", "generalization_axis",
                    )
                },
                "question": case["question"],
                "hard_negative_chunk_ids": case["hard_negative_chunk_ids"],
                "top_score": ranking[0]["score"],
                "ranking": ranking,
                "metrics": query_metrics(case, ranking),
                "encode_ms": encode_ms,
                "retrieval_ms": retrieval_ms,
                "end_to_end_ms": end_to_end_ms,
            }
        )
    query_seconds = clock() - query_total_start
    peak_allocated = None
    peak_reserved = None
    if chosen_device == "cuda":
        import torch

        peak_allocated = torch.cuda.max_memory_allocated() / (1024 * 1024)
        peak_reserved = torch.cuda.max_memory_reserved() / (1024 * 1024)
    metadata = {
        "id": config.id,
        "label": config.label,
        "model": config.model,
        "resolved_source": path,
        "revision": config.revision,
        "dimensions": config.dimensions,
        "configured_minimum_score": config.minimum_score,
        "device": chosen_device,
        "effective_dtype": dtype,
        "load_warmup_seconds": load_warmup,
        "corpus_encoding_index_seconds": corpus_seconds,
        "query_benchmark_seconds": query_seconds,
        "total_wall_seconds": clock() - wall_start,
        "encode": timing_summary(encode_timings),
        "retrieval": timing_summary(retrieval_timings),
        "end_to_end": timing_summary(end_to_end_timings),
        "end_to_end_throughput_qps": (
            len(cases) * timing_runs / query_seconds if query_seconds else None
        ),
        "peak_allocated_cuda_mib": peak_allocated,
        "peak_reserved_cuda_mib": peak_reserved,
        "rss_mib": {
            "before_load": rss_before_load,
            "after_warmup": rss_after_warmup,
            "after_corpus_encoding": rss_after_corpus_encoding,
        },
        "query_count": len(cases),
    }
    del model, corpus_vectors
    gc.collect()
    if chosen_device == "cuda":
        import torch

        torch.cuda.empty_cache()
    return metadata, rows


def sanitize_failure(exc: BaseException) -> dict[str, str]:
    message = " ".join(str(exc).split())
    message = re.sub(
        r"(?i)(bearer|token|password|api[-_ ]?key)\s*[:=]?\s*\S+",
        r"\1 [REDACTED]",
        message,
    )
    message = re.sub(r"\b(?:hf|gsk)_[A-Za-z0-9_-]{8,}\b", "[REDACTED]", message)
    return {"type": type(exc).__name__, "message": message[:500]}
