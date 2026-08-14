# ruff: noqa: E501
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.eval_lib import (  # noqa: E402
    CONTEXT_CHAR_BUDGETS,
    SPLITS,
    EvaluationDataError,
    load_cases,
    mean,
    percentile,
    ranking_metrics,
    select_cases,
)

Direction = Literal["higher", "lower", "descriptive"]
METRIC_SPECS: dict[str, tuple[str, Direction]] = {
    "recallAt1": ("Evidence recall@1", "higher"),
    "recallAt3": ("Evidence recall@3", "higher"),
    "recallAt5": ("Evidence recall@5", "higher"),
    "reciprocalRankAt5": ("First-evidence reciprocal rank@5", "higher"),
    "allEvidenceAt1": ("All-evidence success@1", "higher"),
    "allEvidenceAt3": ("All-evidence success@3", "higher"),
    "allEvidenceAt5": ("All-evidence success@5", "higher"),
    "meanReciprocalEvidenceRankAt5": ("Mean evidence reciprocal rank@5", "higher"),
    "meanEvidenceDiscountAt5": ("Mean discounted evidence gain@5", "higher"),
    "requiredContextPrecisionAt5": ("Required-context precision@5", "higher"),
    "contextRedundancyAt5": ("Context token-set redundancy@5", "lower"),
    "contextCharsAt5": ("Context characters@5", "descriptive"),
    "sourceDiversityAt5": ("Source diversity@5", "descriptive"),
    **{
        f"recallAt{budget}Chars": (f"Evidence recall within {budget} chars", "higher")
        for budget in CONTEXT_CHAR_BUDGETS
    },
    **{
        f"allEvidenceAt{budget}Chars": (
            f"All-evidence success within {budget} chars",
            "higher",
        )
        for budget in CONTEXT_CHAR_BUDGETS
    },
    **{
        f"contextChunksAt{budget}Chars": (
            f"Context chunks within {budget} chars",
            "descriptive",
        )
        for budget in CONTEXT_CHAR_BUDGETS
    },
    **{
        f"contextCharsAt{budget}Chars": (
            f"Actual context characters within {budget}-char budget",
            "descriptive",
        )
        for budget in CONTEXT_CHAR_BUDGETS
    },
}
PRIMARY_TABLE_METRICS = (
    "recallAt1",
    "recallAt3",
    "recallAt5",
    "allEvidenceAt5",
    "meanReciprocalEvidenceRankAt5",
    "requiredContextPrecisionAt5",
    "contextRedundancyAt5",
    "contextCharsAt5",
)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _linear_percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise EvaluationDataError("Cannot calculate a percentile from no values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def exact_sign_test(wins: int, losses: int) -> float | None:
    """Two-sided exact binomial sign test; ties are excluded."""
    observations = wins + losses
    if observations == 0:
        return None
    tail = min(wins, losses)
    probability = sum(math.comb(observations, index) for index in range(tail + 1))
    return min(1.0, 2.0 * probability / (2**observations))


def paired_metric_summary(
    automatic: list[float],
    manual: list[float],
    *,
    direction: Direction,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    if not automatic or len(automatic) != len(manual):
        raise EvaluationDataError("Paired metrics require equal non-empty samples")
    deltas = [candidate - baseline for baseline, candidate in zip(automatic, manual, strict=True)]
    tolerance = 1e-12
    wins = losses = ties = 0
    for delta in deltas:
        directed = delta if direction != "lower" else -delta
        if direction == "descriptive" or abs(directed) <= tolerance:
            ties += 1
        elif directed > 0:
            wins += 1
        else:
            losses += 1

    rng = random.Random(seed)  # noqa: S311 - deterministic statistical resampling, not security
    bootstrapped = [
        mean(deltas[rng.randrange(len(deltas))] for _ in deltas) for _ in range(bootstrap_samples)
    ]
    return {
        "sampleCount": len(deltas),
        "automatic": _round(mean(automatic)),
        "manual": _round(mean(manual)),
        "delta": _round(mean(deltas)),
        "deltaCi95": [
            _round(_linear_percentile(bootstrapped, 0.025)),
            _round(_linear_percentile(bootstrapped, 0.975)),
        ],
        "wins": wins if direction != "descriptive" else None,
        "ties": ties if direction != "descriptive" else None,
        "losses": losses if direction != "descriptive" else None,
        "signTestPValue": (
            _round(exact_sign_test(wins, losses)) if direction != "descriptive" else None
        ),
        "direction": direction,
    }


def fact_clusters(cases: dict[str, dict[str, Any]]) -> list[list[str]] | None:
    parent = {case_id: case_id for case_id in cases}

    def find(case_id: str) -> str:
        while parent[case_id] != case_id:
            parent[case_id] = parent[parent[case_id]]
            case_id = parent[case_id]
        return case_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    owners: dict[str, str] = {}
    has_fact_ids = False
    for case_id, case in cases.items():
        fact_ids = case.get("fact_ids")
        if not isinstance(fact_ids, list) or not fact_ids:
            continue
        has_fact_ids = True
        for fact_id in map(str, fact_ids):
            if fact_id in owners:
                union(case_id, owners[fact_id])
            else:
                owners[fact_id] = case_id
    if not has_fact_ids:
        return None
    clusters: dict[str, list[str]] = defaultdict(list)
    for case_id in sorted(cases):
        clusters[find(case_id)].append(case_id)
    return sorted(clusters.values(), key=lambda cluster: cluster[0])


def clustered_delta_ci(
    deltas_by_case: dict[str, float],
    clusters: list[list[str]],
    *,
    bootstrap_samples: int,
    seed: int,
) -> list[float]:
    clustered_cases = {case_id for cluster in clusters for case_id in cluster}
    if not clusters or set(deltas_by_case) != clustered_cases:
        raise EvaluationDataError("Fact-cluster bootstrap requires every case exactly once")
    rng = random.Random(seed)  # noqa: S311 - deterministic statistical resampling, not security
    bootstrapped: list[float] = []
    for _ in range(bootstrap_samples):
        sampled = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        case_ids = [case_id for cluster in sampled for case_id in cluster]
        bootstrapped.append(mean(deltas_by_case[case_id] for case_id in case_ids))
    return [
        round(_linear_percentile(bootstrapped, 0.025), 6),
        round(_linear_percentile(bootstrapped, 0.975), 6),
    ]


def align_rows(
    automatic_rows: list[dict[str, Any]], manual_rows: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    def index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (str(row.get("caseId")), str(row.get("embedder")))
            if key in result:
                raise EvaluationDataError(f"Duplicate retrieval row for {key[0]} / {key[1]}")
            result[key] = row
        return result

    automatic = index(automatic_rows)
    manual = index(manual_rows)
    if automatic.keys() != manual.keys():
        raise EvaluationDataError(
            "Automatic and manual runs must contain the same case/embedder pairs"
        )
    pairs = [(automatic[key], manual[key]) for key in sorted(automatic)]
    for baseline, candidate in pairs:
        for field in ("split", "category", "question"):
            if baseline.get(field) != candidate.get(field):
                raise EvaluationDataError(f"Paired rows disagree on {field}")
    return pairs


def _rank_changes(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    labels_by_case: dict[str, list[str]],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {
        "coverageGains": [],
        "coverageLosses": [],
        "rankImprovementsWithinTop5": [],
        "rankRegressionsWithinTop5": [],
    }
    for automatic, manual in pairs:
        case_id = automatic["caseId"]
        labels = labels_by_case[case_id]
        automatic_ranks = automatic["metrics"]["evidenceGroupRanks"]
        manual_ranks = manual["metrics"]["evidenceGroupRanks"]
        if len(labels) != len(automatic_ranks) or len(labels) != len(manual_ranks):
            raise EvaluationDataError(f"Evidence-group count changed for {case_id}")
        for label, automatic_rank, manual_rank in zip(
            labels, automatic_ranks, manual_ranks, strict=True
        ):
            item = {
                "caseId": case_id,
                "category": automatic["category"],
                "embedder": automatic["embedder"],
                "evidenceLabel": label,
                "automaticRank": automatic_rank,
                "manualRank": manual_rank,
            }
            automatic_covered = automatic_rank is not None and automatic_rank <= 5
            manual_covered = manual_rank is not None and manual_rank <= 5
            if manual_covered and not automatic_covered:
                result["coverageGains"].append(item)
            elif automatic_covered and not manual_covered:
                result["coverageLosses"].append(item)
            elif automatic_covered and manual_covered:
                assert automatic_rank is not None and manual_rank is not None
                automatic_position = int(automatic_rank)
                manual_position = int(manual_rank)
                if manual_position < automatic_position:
                    result["rankImprovementsWithinTop5"].append(item)
                elif manual_position > automatic_position:
                    result["rankRegressionsWithinTop5"].append(item)
    return result


def _load_report_dir(path: Path) -> tuple[Path, dict[str, Any], Path, list[dict[str, Any]]]:
    summaries = sorted(item for item in path.glob("*.json") if item.is_file())
    details = sorted(item for item in path.glob("*.jsonl") if item.is_file())
    if len(summaries) != 1 or len(details) != 1:
        raise EvaluationDataError(
            f"{path} must contain exactly one JSON summary and one JSONL details file"
        )
    summary = json.loads(summaries[0].read_text(encoding="utf-8"))
    rows = [
        json.loads(line) for line in details[0].read_text(encoding="utf-8").splitlines() if line
    ]
    if not isinstance(summary, dict) or not rows:
        raise EvaluationDataError(f"{path} contains an empty or malformed report")
    return summaries[0], summary, details[0], rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corpus_hash(chunks: list[dict[str, Any]]) -> str:
    canonical = json.dumps(chunks, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_chunks(
    *, corpus_dir: Path, pipeline_path: Path, honor_manual: bool
) -> list[dict[str, Any]]:
    from app.config import load_pipeline
    from app.ingest import chunk_document, discover_documents

    load_pipeline.cache_clear()
    pipeline = load_pipeline(pipeline_path)
    return [
        {
            "source": chunk.source,
            "title": chunk.title,
            "chunkIndex": chunk.index,
            "semanticId": chunk.semantic_id,
            "content": chunk.content,
        }
        for document in discover_documents(corpus_dir)
        for chunk in chunk_document(document, pipeline, honor_manual=honor_manual)
    ]


def _mode_cases(
    *, split: str, evaluation_dir: Path, chunks: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    from scripts.remap_evaluation_qrels import remap_cases_to_chunks

    cases = select_cases(
        load_cases([split], evaluation_dir),
        include_refusals=False,
    )
    remap_cases_to_chunks(cases, chunks)
    return {case["id"]: case for case in cases}


def _enrich_rows(
    rows: list[dict[str, Any]], cases: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        case = cases.get(row["caseId"])
        if case is None:
            raise EvaluationDataError(f"Report contains unknown case {row['caseId']}")
        for field in ("split", "category", "question"):
            if row.get(field) != case.get(field):
                raise EvaluationDataError(
                    f"Report row {row['caseId']} disagrees with locked case field {field}"
                )
        if not isinstance(row.get("retrievedChunks"), list):
            raise EvaluationDataError(f"Report row {row['caseId']} has invalid retrieved chunks")
        item = copy.deepcopy(row)
        item["metrics"] = ranking_metrics(case["required_evidence"], item["retrievedChunks"])
        enriched.append(item)
    return enriched


def _topology(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(chunk["content"]) for chunk in chunks]
    words = [len(chunk["content"].split()) for chunk in chunks]
    by_source: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        by_source[chunk["source"]] += 1
    return {
        "chunkCount": len(chunks),
        "bySource": dict(sorted(by_source.items())),
        "characters": {
            "min": min(lengths),
            "median": _round(statistics.median(lengths)),
            "mean": _round(mean(lengths)),
            "p95": _round(percentile(lengths, 0.95)),
            "max": max(lengths),
        },
        "words": {
            "min": min(words),
            "median": _round(statistics.median(words)),
            "mean": _round(mean(words)),
            "p95": _round(percentile(words, 0.95)),
            "max": max(words),
        },
    }


def _seed(base: int, label: str) -> int:
    return base + int(hashlib.sha256(label.encode()).hexdigest()[:8], 16)


def _metric_views(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    embedders = sorted({automatic["embedder"] for automatic, _ in pairs})
    by_embedder: dict[str, Any] = {}
    for embedder in embedders:
        selected = [pair for pair in pairs if pair[0]["embedder"] == embedder]
        by_embedder[embedder] = {
            metric: paired_metric_summary(
                [float(row[0]["metrics"][metric]) for row in selected],
                [float(row[1]["metrics"][metric]) for row in selected],
                direction=direction,
                bootstrap_samples=bootstrap_samples,
                seed=_seed(seed, f"{embedder}:{metric}"),
            )
            for metric, (_, direction) in METRIC_SPECS.items()
        }

    by_case: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for pair in pairs:
        by_case[pair[0]["caseId"]].append(pair)
    macro: dict[str, Any] = {}
    for metric, (_, direction) in METRIC_SPECS.items():
        automatic = [
            mean(float(pair[0]["metrics"][metric]) for pair in by_case[case_id])
            for case_id in sorted(by_case)
        ]
        manual = [
            mean(float(pair[1]["metrics"][metric]) for pair in by_case[case_id])
            for case_id in sorted(by_case)
        ]
        macro[metric] = paired_metric_summary(
            automatic,
            manual,
            direction=direction,
            bootstrap_samples=bootstrap_samples,
            seed=_seed(seed, f"macro:{metric}"),
        )

    categories = sorted({pair[0]["category"] for pair in pairs})
    by_category: dict[str, Any] = {}
    for category in categories:
        selected = [pair for pair in pairs if pair[0]["category"] == category]
        by_category[category] = {
            "caseCount": len({pair[0]["caseId"] for pair in selected}),
            "routeCaseCount": len(selected),
            "metrics": {
                metric: {
                    "automatic": _round(
                        mean(float(pair[0]["metrics"][metric]) for pair in selected)
                    ),
                    "manual": _round(mean(float(pair[1]["metrics"][metric]) for pair in selected)),
                    "delta": _round(
                        mean(
                            float(pair[1]["metrics"][metric]) - float(pair[0]["metrics"][metric])
                            for pair in selected
                        )
                    ),
                }
                for metric in PRIMARY_TABLE_METRICS
            },
        }
    return {"byEmbedder": by_embedder, "macroAcrossEmbedders": macro, "byCategory": by_category}


def _fact_cluster_sensitivity(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    cases: dict[str, dict[str, Any]],
    *,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any] | None:
    clusters = fact_clusters(cases)
    if clusters is None or len(clusters) == len(cases):
        return None
    metrics: dict[str, Any] = {}
    for metric in PRIMARY_TABLE_METRICS:
        if METRIC_SPECS[metric][1] == "descriptive":
            continue
        route_deltas: dict[str, list[float]] = defaultdict(list)
        for automatic, manual in pairs:
            route_deltas[automatic["caseId"]].append(
                float(manual["metrics"][metric]) - float(automatic["metrics"][metric])
            )
        deltas_by_case = {case_id: mean(deltas) for case_id, deltas in sorted(route_deltas.items())}
        metrics[metric] = {
            "delta": _round(mean(deltas_by_case.values())),
            "deltaCi95": clustered_delta_ci(
                deltas_by_case,
                clusters,
                bootstrap_samples=bootstrap_samples,
                seed=_seed(seed, f"fact-cluster:{metric}"),
            ),
        }
    return {
        "clusterDefinition": "connected components of answerable cases sharing any fact_ids value",
        "caseCount": len(cases),
        "clusterCount": len(clusters),
        "clusterSizes": sorted((len(cluster) for cluster in clusters), reverse=True),
        "bootstrapSamples": bootstrap_samples,
        "metrics": metrics,
    }


def _validate_summaries(
    automatic: dict[str, Any], manual: dict[str, Any], *, split: str
) -> dict[str, Any]:
    if automatic.get("split") != split or manual.get("split") != split:
        raise EvaluationDataError("Report split does not match --split")
    if automatic.get("chunkingMode") != "auto" or manual.get("chunkingMode") != "manual":
        raise EvaluationDataError("Expected automatic and manual chunking reports")
    for key in ("caseIds", "topK"):
        if automatic.get(key) != manual.get(key):
            raise EvaluationDataError(f"Automatic/manual reports disagree on {key}")
    automatic_runtime = automatic.get("runtime", {})
    manual_runtime = manual.get("runtime", {})
    if automatic_runtime.keys() != manual_runtime.keys():
        raise EvaluationDataError("Automatic/manual reports use different embedding routes")
    model_parity = all(
        {
            key: automatic_runtime[embedder].get(key)
            for key in ("model", "revision", "dimensions", "device")
        }
        == {
            key: manual_runtime[embedder].get(key)
            for key in ("model", "revision", "dimensions", "device")
        }
        for embedder in automatic_runtime
    )
    if not model_parity:
        raise EvaluationDataError("Automatic/manual reports use different model configurations")
    automatic_routes = automatic.get("embeddingRoutes")
    manual_routes = manual.get("embeddingRoutes")
    if (automatic_routes is None) != (manual_routes is None):
        raise EvaluationDataError("Only one source report records embedding-route settings")
    if automatic_routes is not None:
        if automatic_routes != manual_routes:
            raise EvaluationDataError("Automatic/manual reports use different embedding routes")
        if set(automatic_routes) != set(automatic_runtime):
            raise EvaluationDataError("Serialized embedding routes do not match runtime routes")
    automatic_protocol = automatic.get("retrievalProtocol")
    manual_protocol = manual.get("retrievalProtocol")
    if (automatic_protocol is None) != (manual_protocol is None):
        raise EvaluationDataError("Only one source report records the retrieval protocol")
    if automatic_protocol is not None and automatic_protocol != manual_protocol:
        raise EvaluationDataError("Automatic/manual reports use different retrieval protocols")
    return {
        "topK": automatic["topK"],
        "caseIdsMatch": True,
        "embeddingModelRuntimeMatch": True,
        "embeddingRouteProtocolArtifactVerified": automatic_routes is not None,
        "embeddingRoutes": automatic_routes,
        "retrievalProtocolArtifactVerified": automatic_protocol is not None,
        "retrievalProtocol": automatic_protocol,
        "embedders": sorted(automatic_runtime),
        "device": sorted({item.get("device") for item in automatic_runtime.values()}),
    }


def source_gate_status(summary: dict[str, Any]) -> dict[str, Any]:
    by_embedder: dict[str, Any] = {}
    for embedder, result in sorted(summary.get("embedders", {}).items()):
        failures = [
            {
                "gate": str(failure["gate"]),
                "actual": _round(float(failure["actual"])),
                "required": _round(float(failure["required"])),
            }
            for failure in result.get("gateFailures", [])
        ]
        by_embedder[embedder] = {
            "passed": bool(result.get("passed", not failures)),
            "gateFailures": failures,
        }
    return {
        "gatesEnforcedDuringRun": bool(summary.get("gatesEnforced", False)),
        "passed": bool(summary.get("passed", False)),
        "passingRoutes": sum(1 for result in by_embedder.values() if result["passed"]),
        "routeCount": len(by_embedder),
        "byEmbedder": by_embedder,
    }


def compare_report_dirs(
    *,
    automatic_dir: Path,
    manual_dir: Path,
    split: str,
    evaluation_dir: Path,
    corpus_dir: Path,
    pipeline_path: Path,
    bootstrap_samples: int,
    seed: int,
    automatic_label: str | None = None,
    manual_label: str | None = None,
) -> dict[str, Any]:
    if automatic_dir.resolve() == manual_dir.resolve():
        raise EvaluationDataError("Automatic and manual retrieval directories must differ")
    auto_summary_path, auto_summary, auto_details_path, auto_rows = _load_report_dir(automatic_dir)
    manual_summary_path, manual_summary, manual_details_path, manual_rows = _load_report_dir(
        manual_dir
    )
    parity = _validate_summaries(auto_summary, manual_summary, split=split)

    automatic_chunks = _build_chunks(
        corpus_dir=corpus_dir, pipeline_path=pipeline_path, honor_manual=False
    )
    manual_chunks = _build_chunks(
        corpus_dir=corpus_dir, pipeline_path=pipeline_path, honor_manual=True
    )
    automatic_corpus_hash = _corpus_hash(automatic_chunks)
    manual_corpus_hash = _corpus_hash(manual_chunks)
    if auto_summary.get("corpusSha256") != automatic_corpus_hash:
        raise EvaluationDataError(
            "Rebuilt automatic corpus does not match the preserved automatic report"
        )
    if manual_summary.get("corpusSha256") != manual_corpus_hash:
        raise EvaluationDataError(
            "Rebuilt manual corpus does not match the preserved manual report"
        )
    parity["corpusHashesMatchReports"] = True
    automatic_cases = _mode_cases(
        split=split, evaluation_dir=evaluation_dir, chunks=automatic_chunks
    )
    manual_cases = _mode_cases(split=split, evaluation_dir=evaluation_dir, chunks=manual_chunks)
    if automatic_cases.keys() != manual_cases.keys():
        raise EvaluationDataError("Chunking modes resolved different evaluation cases")

    auto_rows = _enrich_rows(auto_rows, automatic_cases)
    manual_rows = _enrich_rows(manual_rows, manual_cases)
    pairs = align_rows(auto_rows, manual_rows)
    parity["reportedQuestionFieldsMatch"] = True
    labels = {
        case_id: [group["label"] for group in case["required_evidence"]]
        for case_id, case in automatic_cases.items()
    }
    split_path = evaluation_dir / f"{split}.json"
    lock_path = evaluation_dir / f"{split}.sha256"
    return {
        "schemaVersion": 1,
        "kind": "paired-semantic-chunking-comparison",
        "split": split,
        "sample": {
            "answerableCases": len(automatic_cases),
            "evidenceGroups": sum(len(labels_for_case) for labels_for_case in labels.values()),
            "embeddingRoutes": len(parity["embedders"]),
            "pairedRouteCases": len(pairs),
            "bootstrapUnit": "case (embedding routes averaged within each sampled case)",
            "bootstrapSamples": bootstrap_samples,
            "bootstrapSeed": seed,
        },
        "lineage": {
            "evaluationSplit": {
                "artifact": f"evaluation/{split}.json",
                "sha256": _sha256(split_path),
                "lockArtifact": f"evaluation/{split}.sha256" if lock_path.exists() else None,
                "lockSha256": _sha256(lock_path) if lock_path.exists() else None,
            },
            "automatic": {
                "artifact": automatic_label or str(automatic_dir),
                "summaryFile": auto_summary_path.name,
                "summarySha256": _sha256(auto_summary_path),
                "detailsFile": auto_details_path.name,
                "detailsSha256": _sha256(auto_details_path),
                "corpusSha256": automatic_corpus_hash,
            },
            "manual": {
                "artifact": manual_label or str(manual_dir),
                "summaryFile": manual_summary_path.name,
                "summarySha256": _sha256(manual_summary_path),
                "detailsFile": manual_details_path.name,
                "detailsSha256": _sha256(manual_details_path),
                "corpusSha256": manual_corpus_hash,
            },
        },
        "configurationParity": parity,
        "sourceGateStatus": {
            "automatic": source_gate_status(auto_summary),
            "manual": source_gate_status(manual_summary),
        },
        "chunkTopology": {
            "automatic": _topology(automatic_chunks),
            "manual": _topology(manual_chunks),
        },
        "metrics": _metric_views(pairs, bootstrap_samples=bootstrap_samples, seed=seed),
        "sensitivity": {
            "factClusterBootstrap": _fact_cluster_sensitivity(
                pairs,
                automatic_cases,
                bootstrap_samples=bootstrap_samples,
                seed=seed,
            )
        },
        "rankChanges": _rank_changes(pairs, labels),
        "interpretationRules": {
            "confidenceIntervals": "paired percentile bootstrap; descriptive with tiny samples",
            "signTests": "two-sided exact binomial tests; ties excluded; no multiple-testing correction",
            "requiredContextPrecisionAt5": "lower bound: qrels label required evidence, not every potentially useful chunk",
            "fixedContextBudgets": "rank-preserving Top-5 prefix measured as production-formatted source excerpts, stopped before the next whole chunk would exceed the character budget",
            "heldoutProtection": "output contains case IDs and evidence labels, never held-out question text",
        },
    }


def _transition(metric: dict[str, Any]) -> str:
    return f"{metric['automatic']:.3f} → {metric['manual']:.3f} ({metric['delta']:+.3f})"


def render_markdown(report: dict[str, Any]) -> str:
    topology = report["chunkTopology"]
    protocol_artifact_verified = (
        report["configurationParity"]["retrievalProtocolArtifactVerified"]
        and report["configurationParity"]["embeddingRouteProtocolArtifactVerified"]
    )
    protocol_note = (
        "Candidate depth, query builder, diversity-selector settings, and embedding prefixes are serialized and equal."
        if protocol_artifact_verified
        else "The source reports predate serialized protocol metadata; Top K and model/revision/dimension/device are artifact-verified, while candidate depth, query builder, selector, embedding-prefix, dtype, and score-threshold parity rely on their shared evaluator implementation."
    )
    lines = [
        f"# Paired semantic-chunking evaluation: {report['split']}",
        "",
        "> Automatic and manual chunking use the same cases, six embedding routes, model revisions, and Top K. "
        + protocol_note
        + " Confidence intervals are descriptive because the corpus and case sets are small.",
        "",
        "## Sample and topology",
        "",
        f"- Answerable cases: **{report['sample']['answerableCases']}**",
        f"- Required evidence groups: **{report['sample']['evidenceGroups']}**",
        f"- Paired route/case observations: **{report['sample']['pairedRouteCases']}**",
        f"- Chunks: **{topology['automatic']['chunkCount']} automatic → {topology['manual']['chunkCount']} manual**",
        f"- Mean chunk words: **{topology['automatic']['words']['mean']} → {topology['manual']['words']['mean']}**",
        "",
        "## Source-run absolute gates",
        "",
    ]
    for mode in ("automatic", "manual"):
        status = report["sourceGateStatus"][mode]
        lines.append(
            f"- {mode.title()}: **{status['passingRoutes']}/{status['routeCount']} routes passed**; "
            f"gates enforced during run: **{status['gatesEnforcedDuringRun']}**"
        )
    lines.extend(
        [
            "",
            "> These are the source evaluator's absolute thresholds. They are reported separately from paired automatic/manual regression statistics.",
            "",
            "## Per-embedder retrieval table",
            "",
            "| Embedder | R@1 | R@3 | R@5 | All evidence@5 | Mean evidence RR@5 | Required context P@5 | Redundancy@5 | Context chars@5 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for embedder, metrics in report["metrics"]["byEmbedder"].items():
        cells = [_transition(metrics[name]) for name in PRIMARY_TABLE_METRICS]
        lines.append(f"| {embedder} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Macro paired uncertainty",
            "",
            "Embedding routes are averaged within each case before cases are resampled, so six correlated model outputs are not treated as six independent questions.",
            "",
            "| Metric | Automatic | Manual | Delta | 95% paired bootstrap CI | W/T/L | Exact sign p |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name in PRIMARY_TABLE_METRICS:
        label, _ = METRIC_SPECS[name]
        metric = report["metrics"]["macroAcrossEmbedders"][name]
        ci = metric["deltaCi95"]
        wtl = (
            "descriptive"
            if metric["wins"] is None
            else f"{metric['wins']}/{metric['ties']}/{metric['losses']}"
        )
        p_value = "—" if metric["signTestPValue"] is None else f"{metric['signTestPValue']:.4f}"
        lines.append(
            f"| {label} | {metric['automatic']:.3f} | {metric['manual']:.3f} | "
            f"{metric['delta']:+.3f} | [{ci[0]:+.3f}, {ci[1]:+.3f}] | {wtl} | {p_value} |"
        )

    sensitivity = report["sensitivity"]["factClusterBootstrap"]
    if sensitivity is not None:
        lines.extend(
            [
                "",
                "## Shared-fact cluster sensitivity",
                "",
                f"The {sensitivity['caseCount']} cases form **{sensitivity['clusterCount']} fact clusters**. Resampling those clusters keeps query variants about the same fact together.",
                "",
                "| Metric | Delta | Case-bootstrap CI | Fact-cluster CI |",
                "|---|---:|---:|---:|",
            ]
        )
        for name, clustered in sensitivity["metrics"].items():
            label, _ = METRIC_SPECS[name]
            primary = report["metrics"]["macroAcrossEmbedders"][name]
            lines.append(
                f"| {label} | {clustered['delta']:+.3f} | "
                f"[{primary['deltaCi95'][0]:+.3f}, {primary['deltaCi95'][1]:+.3f}] | "
                f"[{clustered['deltaCi95'][0]:+.3f}, {clustered['deltaCi95'][1]:+.3f}] |"
            )

    lines.extend(
        [
            "",
            "## Fixed context-budget comparison",
            "",
            "This controls the main Top-K confound: manual chunks are larger. Each row measures the production-formatted source excerpts, keeps the rank-preserving Top-5 prefix, and stops before adding a whole chunk that would exceed the budget.",
            "",
            "| Budget | Evidence recall | All-evidence success | Actual chars (automatic → manual) | Chunks (automatic → manual) |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    macro = report["metrics"]["macroAcrossEmbedders"]
    for budget in CONTEXT_CHAR_BUDGETS:
        recall = macro[f"recallAt{budget}Chars"]
        all_evidence = macro[f"allEvidenceAt{budget}Chars"]
        characters = macro[f"contextCharsAt{budget}Chars"]
        chunks = macro[f"contextChunksAt{budget}Chars"]
        lines.append(
            f"| {budget} | {_transition(recall)} | {_transition(all_evidence)} | "
            f"{characters['automatic']:.0f} → {characters['manual']:.0f} | "
            f"{chunks['automatic']:.2f} → {chunks['manual']:.2f} |"
        )

    changes = report["rankChanges"]
    lines.extend(
        [
            "",
            "## Evidence-level regressions",
            "",
            f"- Coverage gains: **{len(changes['coverageGains'])}**",
            f"- Coverage losses: **{len(changes['coverageLosses'])}**",
            f"- Rank improvements within Top 5: **{len(changes['rankImprovementsWithinTop5'])}**",
            f"- Rank regressions within Top 5: **{len(changes['rankRegressionsWithinTop5'])}**",
            "",
            "## Metric definitions",
            "",
            "- **R@K:** fraction of required evidence groups found by rank K.",
            "- **All evidence@K:** fraction of questions for which every required evidence group is present by rank K.",
            "- **Mean evidence RR@5:** reciprocal rank averaged across every evidence group, not only the first hit.",
            "- **Required context P@5:** fraction of returned chunks matching required qrels; it is a lower bound because qrels do not label every merely useful chunk.",
            "- **Redundancy@5:** mean pairwise Jaccard similarity between retrieved chunk token sets; lower means less repeated context.",
            "- **Context chars@5:** production-formatted source-excerpt size; descriptive, not automatically better when smaller.",
            "- **Fixed context budget:** evidence metrics after limiting production-formatted source excerpts to the same strict character ceiling; this separates boundary quality from simply returning more text.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare paired automatic/manual chunking runs")
    parser.add_argument("--automatic-dir", type=Path, required=True)
    parser.add_argument("--manual-dir", type=Path, required=True)
    parser.add_argument("--automatic-label")
    parser.add_argument("--manual-label")
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--evaluation-dir", type=Path, default=Path("evaluation"))
    parser.add_argument("--corpus-dir", type=Path, default=Path("corpus"))
    parser.add_argument("--pipeline", type=Path, default=Path("config/pipeline.yaml"))
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bootstrap_samples < 1_000:
        raise SystemExit("--bootstrap-samples must be at least 1000")
    try:
        report = compare_report_dirs(
            automatic_dir=args.automatic_dir,
            manual_dir=args.manual_dir,
            split=args.split,
            evaluation_dir=args.evaluation_dir,
            corpus_dir=args.corpus_dir,
            pipeline_path=args.pipeline,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seed,
            automatic_label=args.automatic_label,
            manual_label=args.manual_label,
        )
    except (EvaluationDataError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.output_markdown.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "split": report["split"],
                "outputJson": str(args.output_json),
                "outputMarkdown": str(args.output_markdown),
                "coverageGains": len(report["rankChanges"]["coverageGains"]),
                "coverageLosses": len(report["rankChanges"]["coverageLosses"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
