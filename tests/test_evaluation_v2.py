from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from app.config import load_pipeline
from evaluation.v2.benchmark import (
    build_retrieval_query,
    effective_dtype,
    relocate_model_path,
    select_diverse_chunks,
    stable_exact_ranking,
)
from evaluation.v2.corpus import load_corpus_chunks
from evaluation.v2.eval_lib import (
    EvaluationV2Error,
    aggregate,
    cluster_bootstrap,
    evaluate_threshold,
    load_data,
    paired_comparison,
    percentile,
    query_metrics,
    threshold_diagnostics,
    timing_summary,
    validate_data,
    verify_challenge_lock,
)
from evaluation.v2.report import markdown_report
from scripts import evaluate_embeddings_v2


def test_checked_in_data_invariants_and_corpus_validity() -> None:
    knowledge, cases, chunks = load_data()
    assert len(knowledge["claims"]) >= 20
    assert len(cases) == 120
    assert len({case["family_id"] for case in cases}) == 40
    assert len(chunks) == 22
    assert sum(case["split"] == "dev" for case in cases) == 84
    assert sum(case["split"] == "challenge" for case in cases) == 36
    assert all("training_overlap" in case and "generalization_axis" in case for case in cases)
    assert any(
        grade in {1, 2} for case in cases for grade in case["graded_qrels"].values()
    )


def test_eval_chunking_exactly_matches_production() -> None:
    from app.ingest import chunk_document, discover_documents

    root = Path("corpus")
    pipeline = load_pipeline(Path("config/pipeline.yaml"))
    production = [
        chunk
        for document in discover_documents(root)
        for chunk in chunk_document(document, pipeline)
    ]
    evaluation = load_corpus_chunks(root, pipeline)
    assert [
        (chunk.id, chunk.source, chunk.title, chunk.index, chunk.content)
        for chunk in evaluation
    ] == [
        (
            f"{chunk.source}#{chunk.index}",
            chunk.source,
            chunk.title,
            chunk.index,
            chunk.content,
        )
        for chunk in production
    ]


def test_history_query_uses_only_recent_user_messages() -> None:
    case = {
        "question": "And under load?",
        "history": [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Do not include this"},
            {"role": "user", "content": "Second"},
        ],
    }
    assert build_retrieval_query(case) == (
        "Previous user context:\nFirst\nSecond\n\n"
        "Current question:\nAnd under load?"
    )
    assert build_retrieval_query({"question": "Standalone", "history": []}) == "Standalone"


def test_diversity_skips_redundant_adjacent_candidate() -> None:
    candidates = [
        {
            "chunk_id": "doc#0", "source": "doc", "chunkIndex": 0,
            "content": "alpha beta gamma delta epsilon zeta", "score": 0.9,
        },
        {
            "chunk_id": "doc#1", "source": "doc", "chunkIndex": 1,
            "content": "alpha beta gamma delta epsilon other", "score": 0.8,
        },
        {
            "chunk_id": "other#0", "source": "other", "chunkIndex": 0,
            "content": "pickleball booking transaction contention", "score": 0.7,
        },
    ]
    assert [row["chunk_id"] for row in select_diverse_chunks(candidates, 2)] == [
        "doc#0", "other#0"
    ]


def test_challenge_lock_detects_change(tmp_path: Path) -> None:
    _, cases, _ = load_data()
    (tmp_path / "challenge.sha256").write_text(
        (Path("evaluation/v2/challenge.sha256")).read_text(), encoding="ascii"
    )
    changed = deepcopy(cases)
    next(case for case in changed if case["split"] == "challenge")["question"] += " changed"
    with pytest.raises(EvaluationV2Error, match="changed"):
        verify_challenge_lock(changed, tmp_path)


def test_unknown_qrel_and_split_crossing_are_rejected() -> None:
    knowledge, cases, chunks = load_data()
    broken = deepcopy(cases)
    broken[0]["graded_qrels"]["missing.md#0"] = 3
    with pytest.raises(EvaluationV2Error, match="qrel"):
        validate_data(knowledge, broken, chunks)
    broken = deepcopy(cases)
    broken[0]["split"] = "challenge"
    with pytest.raises(EvaluationV2Error, match="crosses split"):
        validate_data(knowledge, broken, chunks)


def _case() -> dict:
    return {
        "answerable": True,
        "graded_qrels": {"a": 3, "b": 2},
        "hard_negative_chunk_ids": ["x"],
    }


def test_metric_formulas_and_ndcg() -> None:
    metrics = query_metrics(_case(), ["b", "x", "a", "z", "q"])
    assert metrics["required_recall@1"] == 0
    assert metrics["required_recall@3"] == 1
    assert metrics["all_required@3"] == 1
    assert metrics["mrr@5"] == 1
    assert metrics["precision@3"] == pytest.approx(2 / 3)
    assert 0 < metrics["ndcg@3"] < 1
    assert metrics["hard_negative_hit_rate@3"] == 1
    assert query_metrics(_case(), ["a", "b"])["ndcg@5"] == 1


def test_threshold_diagnostics_and_degenerate_sets() -> None:
    rows = [
        {"top_score": 0.9, "answerable": True},
        {"top_score": 0.8, "answerable": True},
        {"top_score": 0.2, "answerable": False},
        {"top_score": 0.1, "answerable": False},
    ]
    result = threshold_diagnostics(rows)
    assert result["balanced_accuracy"] == 1
    assert result["false_answer_rate"] == 0
    assert threshold_diagnostics(rows[:2])["false_refusal_rate"] == 0
    assert threshold_diagnostics([])["threshold"] is None
    calibrated = threshold_diagnostics(rows[:3])
    changed_challenge = [
        {"top_score": 0.99, "answerable": False},
        {"top_score": 0.01, "answerable": True},
    ]
    evaluated = evaluate_threshold(changed_challenge, calibrated["threshold"])
    assert evaluated["threshold"] == calibrated["threshold"]


def test_challenge_view_cannot_retune_dev_threshold() -> None:
    dev = [
        {
            **_record("d1", "d1", 1), "top_score": 0.8, "answerable": True,
        },
        {
            **_record("d2", "d2", 0), "top_score": 0.2, "answerable": False,
        },
    ]
    challenge = [
        {
            **_record("c1", "c1", 1), "split": "challenge",
            "top_score": 0.99, "answerable": False,
        },
        {
            **_record("c2", "c2", 0), "split": "challenge",
            "top_score": 0.01, "answerable": True,
        },
    ]
    expected = threshold_diagnostics(dev)["threshold"]
    view = evaluate_embeddings_v2._views(dev + challenge, 0, 17, 0.5)["challenge/basic"]
    assert view["threshold_diagnostics"]["threshold"] == expected
    assert view["configured_threshold_diagnostics"]["threshold"] == 0.5
    unavailable = evaluate_embeddings_v2._views(challenge, 0, 17, 0.5)["challenge/basic"]
    assert unavailable["threshold_diagnostics"]["available"] is False


def _record(case_id: str, family: str, value: float) -> dict:
    return {
        "id": case_id,
        "family_id": family,
        "tier": "basic",
        "split": "dev",
        "category": "fact",
        "difficulty": "easy",
        "answerable": True,
        "hard_negative_chunk_ids": [],
        "metrics": {"ndcg@5": value, "required_recall@5": value},
    }


def test_bootstrap_is_deterministic_and_clustered() -> None:
    records = [_record("a1", "a", 1), _record("a2", "a", 1), _record("b1", "b", 0)]
    assert cluster_bootstrap(records, samples=50, seed=4) == cluster_bootstrap(
        records, samples=50, seed=4
    )


def test_family_consistency_uses_worst_variant() -> None:
    result = aggregate([_record("a1", "a", 1), _record("a2", "a", 0.5), _record("b1", "b", 0)])
    assert result["family_consistency"]["ndcg@5"] == pytest.approx(0.25)


def test_aggregate_excludes_unanswerable_from_relevance() -> None:
    answerable = _record("a", "a", 1)
    unanswerable = {**_record("u", "u", 0), "answerable": False}
    result = aggregate([answerable, unanswerable])
    assert result["query_count"] == 2
    assert result["answerable_query_count"] == 1
    assert result["metrics"]["ndcg@5"] == 1


def test_timing_helpers() -> None:
    assert percentile([0, 10], 0.5) == 5
    assert timing_summary([1, 2, 9]) == {"mean_ms": 4, "p50_ms": 2, "p95_ms": 8.299999999999999}
    assert timing_summary([])["p95_ms"] is None


def test_artifact_relocation_and_dtype_selection(tmp_path: Path) -> None:
    assert relocate_model_path("/model-artifacts/x", tmp_path) == str(tmp_path / "x")
    assert relocate_model_path("org/model", tmp_path) == "org/model"
    assert effective_dtype("bfloat16", "cuda") == "float16"
    assert effective_dtype("bfloat16", "cpu") == "bfloat16"


def test_exact_ranking_is_cosine_and_stable() -> None:
    corpus = np.array([[1, 0], [2, 0], [0, 1]], dtype=float)
    rows = stable_exact_ranking(np.array([1, 0]), corpus, ["first", "second", "third"], 3)
    assert [row["chunk_id"] for row in rows] == ["first", "second", "third"]


def test_paired_comparison_with_tolerance() -> None:
    left = [_record("one", "a", 0.8), _record("two", "b", 0.5)]
    right = [_record("one", "a", 0.7), _record("two", "b", 0.5 + 1e-10)]
    result = paired_comparison(left, right, tolerance=1e-8)
    assert result["metrics"]["ndcg@5"] == {
        "wins": 1,
        "ties": 1,
        "losses": 0,
        "mean_delta": pytest.approx(0.04999999995),
    }


def test_paired_comparisons_are_split_into_release_views() -> None:
    left, right = [], []
    for split in ("dev", "challenge"):
        for tier in ("basic", "intermediate"):
            for target, value in ((left, 1.0), (right, 0.5)):
                target.append({
                    **_record(f"{split}-{tier}", f"{split}-{tier}", value),
                    "split": split,
                    "tier": tier,
                })
    views = evaluate_embeddings_v2._paired_views(left, right)
    assert {
        "dev/basic", "dev/intermediate", "dev/all",
        "challenge/basic", "challenge/intermediate", "challenge/all", "all/all",
    } == views.keys()
    assert views["all/all"]["informational_only"] is True
    assert not any("/" not in key for key in views)


def test_report_generation_contains_release_warnings() -> None:
    report = markdown_report({"models": [], "paired_comparisons": {}})
    assert "informational only" in report
    assert "regression data" in report


def test_cli_continues_after_one_model_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_benchmark(config: object, cases: list[dict], chunks: list[object], **kwargs: object):
        if config.id == "minilm-l6":
            raise RuntimeError("model unavailable")
        rows = [
            {
                **{
                    key: case[key]
                    for key in (
                        "id", "family_id", "tier", "split", "category",
                        "difficulty", "answerable",
                    )
                },
                "question": case["question"],
                "hard_negative_chunk_ids": case["hard_negative_chunk_ids"],
                "top_score": 0.8,
                "ranking": [],
                "metrics": {"ndcg@5": 1.0, "required_recall@5": 1.0},
                "encode_ms": [1.0],
                "retrieval_ms": [1.0],
                "end_to_end_ms": [2.0],
            }
            for case in cases
        ]
        timing = {
            "device": "cpu",
            "effective_dtype": "float32",
            "load_warmup_seconds": 1.0,
            "corpus_encoding_index_seconds": 1.0,
            "query_benchmark_seconds": 1.0,
            "encode": {"mean_ms": 1.0, "p50_ms": 1.0, "p95_ms": 1.0},
            "retrieval": {"mean_ms": 1.0, "p50_ms": 1.0, "p95_ms": 1.0},
            "end_to_end": {"mean_ms": 2.0, "p50_ms": 2.0, "p95_ms": 2.0},
            "end_to_end_throughput_qps": 10.0,
            "peak_allocated_cuda_mib": None,
            "peak_reserved_cuda_mib": None,
            "rss_mib": {
                "before_load": 100.0,
                "after_warmup": 120.0,
                "after_corpus_encoding": 121.0,
            },
        }
        return timing, rows

    monkeypatch.setattr(evaluate_embeddings_v2, "benchmark_model", fake_benchmark)
    args = evaluate_embeddings_v2.build_parser().parse_args(
        [
            "--embedder", "minilm-l6,bge-small",
            "--split", "dev",
            "--bootstrap-samples", "0",
            "--output-dir", str(tmp_path),
        ]
    )
    assert evaluate_embeddings_v2.run(args) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert [model["status"] for model in summary["models"]] == ["failed", "ok"]
