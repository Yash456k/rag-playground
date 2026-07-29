from __future__ import annotations

import hashlib
import hmac
import json
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from app.config import load_pipeline

from .corpus import CorpusChunk, load_corpus_chunks

ROOT = Path(__file__).resolve().parent
KS = (1, 3, 5)


class EvaluationV2Error(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationV2Error(f"Cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationV2Error(f"{path.name} must contain an object")
    return value


def challenge_cases(cases: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [case for case in cases if case["split"] == "challenge"]


def verify_challenge_lock(cases: Sequence[dict[str, Any]], root: Path = ROOT) -> str:
    try:
        expected, name = (root / "challenge.sha256").read_text(encoding="ascii").split()
    except (OSError, ValueError) as exc:
        raise EvaluationV2Error("Challenge lock is missing or malformed") from exc
    if name != "canonical-challenge-v2.json" or len(expected) != 64:
        raise EvaluationV2Error("Challenge lock has the wrong format")
    actual = hashlib.sha256(canonical_json(challenge_cases(cases))).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise EvaluationV2Error("Challenge subset changed; intentionally regenerate its lock")
    return actual


def load_data(
    root: Path = ROOT,
    *,
    corpus_root: Path | None = None,
    config_path: Path | None = None,
    verify_lock: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[CorpusChunk]]:
    knowledge = _json(root / "knowledge_map.json")
    basic, intermediate = _json(root / "basic.json"), _json(root / "intermediate.json")
    if basic.get("tier") != "basic" or intermediate.get("tier") != "intermediate":
        raise EvaluationV2Error("Tier files have invalid metadata")
    cases = [*basic.get("cases", []), *intermediate.get("cases", [])]
    repo = root.parents[1]
    chunks = load_corpus_chunks(
        corpus_root or repo / "corpus", load_pipeline(config_path or repo / "config/pipeline.yaml")
    )
    validate_data(knowledge, cases, chunks)
    if verify_lock:
        verify_challenge_lock(cases, root)
    return knowledge, cases, chunks


def validate_data(
    knowledge: dict[str, Any],
    cases: Sequence[dict[str, Any]],
    chunks: Sequence[CorpusChunk],
) -> None:
    chunk_map = {chunk.id: chunk for chunk in chunks}
    if len(chunk_map) != len(chunks):
        raise EvaluationV2Error("Corpus chunk IDs are not unique")
    claims = knowledge.get("claims")
    if knowledge.get("version") != 2 or not isinstance(claims, dict) or not claims:
        raise EvaluationV2Error("Knowledge map is invalid")
    for claim_id, claim in claims.items():
        if not isinstance(claim.get("claim"), str) or not claim.get("evidence"):
            raise EvaluationV2Error(f"Claim {claim_id} has no text/evidence")
        for evidence in claim["evidence"]:
            chunk = chunk_map.get(evidence.get("chunk_id"))
            if chunk is None:
                raise EvaluationV2Error(f"Claim {claim_id} references an unknown chunk")
            if evidence.get("anchor") not in chunk.content:
                raise EvaluationV2Error(f"Claim {claim_id} evidence anchor is not exact")
    required_fields = {
        "id", "family_id", "variant_id", "tier", "split", "category", "difficulty",
        "question", "history", "answerable", "required_claim_ids", "graded_qrels",
        "hard_negative_chunk_ids", "expected_behavior", "notes", "training_overlap",
        "generalization_axis",
    }
    if len(cases) != 120:
        raise EvaluationV2Error(f"Expected 120 cases, found {len(cases)}")
    ids: set[str] = set()
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        missing = required_fields - case.keys()
        if missing:
            raise EvaluationV2Error(f"{case.get('id')}: missing {sorted(missing)}")
        if case["id"] in ids:
            raise EvaluationV2Error(f"Duplicate case ID {case['id']}")
        ids.add(case["id"])
        families[case["family_id"]].append(case)
        if (
            case["tier"] not in {"basic", "intermediate"}
            or case["split"] not in {"dev", "challenge"}
        ):
            raise EvaluationV2Error(f"{case['id']}: invalid tier/split")
        if case["expected_behavior"] not in {"answer", "refuse", "clarify"}:
            raise EvaluationV2Error(f"{case['id']}: invalid behavior")
        if case["training_overlap"] not in {
            "direct_intent_seen", "fact_seen_query_form_held_out", "none_unanswerable"
        }:
            raise EvaluationV2Error(f"{case['id']}: invalid training overlap")
        if case["generalization_axis"] not in {
            "regression", "paraphrase", "noise", "composition", "follow_up",
            "contrast", "answerability", "adversarial",
        }:
            raise EvaluationV2Error(f"{case['id']}: invalid generalization axis")
        if not isinstance(case["history"], list) or not isinstance(case["question"], str):
            raise EvaluationV2Error(f"{case['id']}: invalid question/history")
        required = case["required_claim_ids"]
        qrels = case["graded_qrels"]
        for claim_id in required:
            if claim_id not in claims:
                raise EvaluationV2Error(f"{case['id']}: unknown claim {claim_id}")
        if case["answerable"]:
            if not required or not any(grade == 3 for grade in qrels.values()):
                raise EvaluationV2Error(f"{case['id']}: answerable case needs claims and grade 3")
            expected_grade_three = {
                evidence["chunk_id"]
                for claim_id in required
                for evidence in claims[claim_id]["evidence"]
            }
            actual_grade_three = {
                chunk_id for chunk_id, grade in qrels.items() if grade == 3
            }
            if actual_grade_three != expected_grade_three:
                raise EvaluationV2Error(
                    f"{case['id']}: grade-3 qrels must exactly match required-claim evidence"
                )
        elif required:
            raise EvaluationV2Error(f"{case['id']}: unanswerable case has required claims")
        for chunk_id, grade in qrels.items():
            if chunk_id not in chunk_map or type(grade) is not int or not 0 <= grade <= 3:
                raise EvaluationV2Error(f"{case['id']}: invalid qrel {chunk_id}")
        for chunk_id in case["hard_negative_chunk_ids"]:
            if chunk_id not in chunk_map:
                raise EvaluationV2Error(f"{case['id']}: unknown hard negative {chunk_id}")
            if qrels.get(chunk_id, 0) > 0:
                raise EvaluationV2Error(
                    f"{case['id']}: hard negative cannot also be relevant: {chunk_id}"
                )
    if len(families) != 40:
        raise EvaluationV2Error(f"Expected 40 families, found {len(families)}")
    for family_id, variants in families.items():
        if len(variants) != 3 or {v["variant_id"] for v in variants} != {1, 2, 3}:
            raise EvaluationV2Error(f"{family_id}: expected variants 1, 2, 3")
        if len({v["split"] for v in variants}) != 1 or len({v["tier"] for v in variants}) != 1:
            raise EvaluationV2Error(f"{family_id}: family crosses split/tier")
        if len({v["question"] for v in variants}) != 3:
            raise EvaluationV2Error(f"{family_id}: variants must differ")
    split_counts = {
        split: len({case["family_id"] for case in cases if case["split"] == split})
        for split in ("dev", "challenge")
    }
    if split_counts != {"dev": 28, "challenge": 12}:
        raise EvaluationV2Error(f"Wrong family split counts: {split_counts}")
    for split in ("dev", "challenge"):
        if {c["tier"] for c in cases if c["split"] == split} != {"basic", "intermediate"}:
            raise EvaluationV2Error(f"{split} must contain both tiers")
        for tier in ("basic", "intermediate"):
            answerable = [
                case for case in cases
                if case["split"] == split and case["tier"] == tier and case["answerable"]
            ]
            if answerable and not any(
                grade in {1, 2}
                for case in answerable
                for grade in case["graded_qrels"].values()
            ):
                raise EvaluationV2Error(
                    f"{split}/{tier} needs at least one supporting grade-1/2 qrel"
                )
    expected_intermediate = {
        "paraphrase", "noisy", "multi_evidence", "follow_up", "hard_negative",
        "underspecified", "false_premise", "partially_answerable", "out_of_corpus",
        "prompt_injection",
    }
    categories = {c["category"] for c in cases if c["tier"] == "intermediate"}
    if not expected_intermediate <= categories:
        missing = expected_intermediate - categories
        raise EvaluationV2Error(f"Missing intermediate categories: {missing}")


def _ids(ranking: Sequence[Any]) -> list[str]:
    return [item if isinstance(item, str) else str(item["chunk_id"]) for item in ranking]


def query_metrics(case: dict[str, Any], ranking: Sequence[Any]) -> dict[str, float]:
    ranked = _ids(ranking)
    qrels = case["graded_qrels"]
    required_chunks = {
        chunk_id for chunk_id, grade in qrels.items() if grade == 3
    }
    result: dict[str, float] = {}
    first_relevant = next((i for i, cid in enumerate(ranked[:5], 1) if qrels.get(cid, 0) > 0), None)
    result["mrr@5"] = 0.0 if first_relevant is None else 1.0 / first_relevant
    for k in KS:
        top = ranked[:k]
        relevant_hits = sum(qrels.get(cid, 0) > 0 for cid in top)
        covered = len(required_chunks.intersection(top))
        result[f"required_recall@{k}"] = (
            covered / len(required_chunks) if required_chunks else 0.0
        )
        result[f"all_required@{k}"] = float(required_chunks <= set(top)) if required_chunks else 0.0
        result[f"hit_rate@{k}"] = float(relevant_hits > 0)
        result[f"precision@{k}"] = relevant_hits / k
        ideal = sorted(qrels.values(), reverse=True)[:k]
        dcg = sum((2 ** qrels.get(cid, 0) - 1) / math.log2(i + 2) for i, cid in enumerate(top))
        idcg = sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(ideal))
        result[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
        negatives = set(case["hard_negative_chunk_ids"])
        result[f"hard_negative_hit_rate@{k}"] = float(bool(negatives.intersection(top)))
    return result


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    if not 0 <= q <= 1:
        raise ValueError("percentile must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def timing_summary(milliseconds: Sequence[float]) -> dict[str, float | None]:
    return {
        "mean_ms": mean(milliseconds) if milliseconds else None,
        "p50_ms": percentile(milliseconds, 0.5),
        "p95_ms": percentile(milliseconds, 0.95),
    }


def aggregate(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "query_count": 0, "answerable_query_count": 0, "hard_negative_query_count": 0,
            "metrics": {}, "family_consistency": {},
        }
    answerable = [record for record in records if record["answerable"]]
    metric_names = sorted(records[0]["metrics"])
    relevance_names = [
        name for name in metric_names if not name.startswith("hard_negative_hit_rate@")
    ]
    hard_negative_names = [
        name for name in metric_names if name.startswith("hard_negative_hit_rate@")
    ]
    hard_negative_records = [
        record for record in records if record.get("hard_negative_chunk_ids")
    ]
    metrics = {
        name: mean(r["metrics"][name] for r in answerable)
        for name in relevance_names
    }
    metrics.update({
        name: (
            mean(r["metrics"][name] for r in hard_negative_records)
            if hard_negative_records else None
        )
        for name in hard_negative_names
    })
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in answerable:
        by_family[record["family_id"]].append(record)
    consistency = {
        name: mean(
            min(item["metrics"][name] for item in family)
            for family in by_family.values()
        )
        for name in ("required_recall@5", "ndcg@5")
    }
    slices: dict[str, Any] = {}
    for field in ("category", "difficulty", "tier", "split"):
        slices[field] = {}
        for value in sorted({r[field] for r in records}):
            subset = [r for r in records if r[field] == value]
            subset_answerable = [r for r in subset if r["answerable"]]
            subset_hard_negatives = [r for r in subset if r.get("hard_negative_chunk_ids")]
            slices[field][value] = {
                "query_count": len(subset),
                "answerable_query_count": len(subset_answerable),
                "hard_negative_query_count": len(subset_hard_negatives),
                "metrics": {
                    name: mean(r["metrics"][name] for r in subset_answerable)
                    for name in relevance_names
                } | {
                    name: (
                        mean(r["metrics"][name] for r in subset_hard_negatives)
                        if subset_hard_negatives else None
                    )
                    for name in hard_negative_names
                },
            }
    return {
        "query_count": len(records),
        "answerable_query_count": len(answerable),
        "hard_negative_query_count": len(hard_negative_records),
        "metrics": metrics,
        "family_consistency": consistency,
        "slices": slices,
    }


def threshold_diagnostics(
    rows: Sequence[dict[str, Any]],
    *,
    score_key: str = "top_score",
    label_key: str = "answerable",
) -> dict[str, float | int | None]:
    if not rows:
        return {
            "threshold": None,
            "balanced_accuracy": None,
            "false_answer_rate": None,
            "false_refusal_rate": None,
        }
    scores = [float(row[score_key]) for row in rows]
    candidates = [
        math.nextafter(min(scores), -math.inf),
        *sorted(set(scores)),
        math.nextafter(max(scores), math.inf),
    ]
    positives = sum(bool(row[label_key]) for row in rows)
    negatives = len(rows) - positives
    best: tuple[float, float, float, float] | None = None
    for threshold in candidates:
        false_refusals = sum(bool(r[label_key]) and float(r[score_key]) < threshold for r in rows)
        false_answers = sum(
            not bool(r[label_key]) and float(r[score_key]) >= threshold for r in rows
        )
        tpr = 1 - false_refusals / positives if positives else 1.0
        tnr = 1 - false_answers / negatives if negatives else 1.0
        candidate = ((tpr + tnr) / 2, -false_answers, -false_refusals, threshold)
        if best is None or candidate > best:
            best = candidate
    assert best is not None
    threshold = best[3]
    fa = sum(not bool(r[label_key]) and float(r[score_key]) >= threshold for r in rows)
    fr = sum(bool(r[label_key]) and float(r[score_key]) < threshold for r in rows)
    return {
        "threshold": threshold,
        "balanced_accuracy": best[0],
        "false_answer_rate": fa / negatives if negatives else 0.0,
        "false_refusal_rate": fr / positives if positives else 0.0,
        "positive_count": positives,
        "negative_count": negatives,
    }


def evaluate_threshold(
    rows: Sequence[dict[str, Any]],
    threshold: float,
    *,
    score_key: str = "top_score",
    label_key: str = "answerable",
) -> dict[str, float | int]:
    positives = sum(bool(row[label_key]) for row in rows)
    negatives = len(rows) - positives
    false_refusals = sum(
        bool(row[label_key]) and float(row[score_key]) < threshold for row in rows
    )
    false_answers = sum(
        not bool(row[label_key]) and float(row[score_key]) >= threshold for row in rows
    )
    tpr = 1 - false_refusals / positives if positives else 1.0
    tnr = 1 - false_answers / negatives if negatives else 1.0
    return {
        "threshold": threshold,
        "balanced_accuracy": (tpr + tnr) / 2,
        "false_answer_rate": false_answers / negatives if negatives else 0.0,
        "false_refusal_rate": false_refusals / positives if positives else 0.0,
        "positive_count": positives,
        "negative_count": negatives,
    }


def cluster_bootstrap(
    records: Sequence[dict[str, Any]],
    metric_names: Sequence[str] = ("ndcg@5", "required_recall@5"),
    *,
    samples: int = 1000,
    seed: int = 17,
) -> dict[str, dict[str, float | None]]:
    records = [record for record in records if record["answerable"]]
    if not records or samples <= 0:
        return {name: {"low": None, "high": None} for name in metric_names}
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        families[record["family_id"]].append(record)
    keys = sorted(families)
    rng = random.Random(seed)  # noqa: S311 - deterministic statistical bootstrap
    distributions = {name: [] for name in metric_names}
    for _ in range(samples):
        sampled = [
            item
            for _ in keys
            for item in families[rng.choice(keys)]  # noqa: S311
        ]
        for name in metric_names:
            distributions[name].append(mean(row["metrics"][name] for row in sampled))
    return {
        name: {"low": percentile(values, 0.025), "high": percentile(values, 0.975)}
        for name, values in distributions.items()
    }


def paired_comparison(
    left: Sequence[dict[str, Any]],
    right: Sequence[dict[str, Any]],
    *,
    tolerance: float = 1e-9,
) -> dict[str, Any]:
    left_map, right_map = (
        {r["id"]: r for r in rows if r["answerable"]} for rows in (left, right)
    )
    shared = sorted(left_map.keys() & right_map.keys())
    output: dict[str, Any] = {"query_count": len(shared), "tie_tolerance": tolerance, "metrics": {}}
    for name in ("ndcg@5", "required_recall@5"):
        deltas = [
            left_map[key]["metrics"][name] - right_map[key]["metrics"][name]
            for key in shared
        ]
        output["metrics"][name] = {
            "wins": sum(delta > tolerance for delta in deltas),
            "ties": sum(abs(delta) <= tolerance for delta in deltas),
            "losses": sum(delta < -tolerance for delta in deltas),
            "mean_delta": mean(deltas),
        }
    return output


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
