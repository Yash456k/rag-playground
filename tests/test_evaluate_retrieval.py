from __future__ import annotations

from evaluation.eval_lib import ranking_metrics
from scripts.evaluate_retrieval import aggregate_embedder_rows


def _group(source: str, chunk_index: int) -> dict:
    return {
        "label": f"{source}-{chunk_index}",
        "any_of": [{"source": source, "chunk_indexes": [chunk_index]}],
    }


def test_ranking_metrics_score_multiple_required_evidence_groups() -> None:
    groups = [_group("experience.md", 1), _group("projects.md", 2)]
    chunks = [
        {"source": "experience.md", "chunkIndex": 1, "content": "AIVID"},
        {"source": "noise.md", "chunkIndex": 0, "content": "noise"},
        {"source": "projects.md", "chunkIndex": 2, "content": "NSK"},
    ]

    metrics = ranking_metrics(groups, chunks)

    assert metrics["recallAt1"] == 0.5
    assert metrics["recallAt3"] == 1.0
    assert metrics["recallAt5"] == 1.0
    assert metrics["reciprocalRankAt5"] == 1.0
    assert metrics["requiredCoveredAt5"] is True
    assert metrics["evidenceGroupRanks"] == [1, 3]


def test_embedder_aggregation_enforces_every_metric_gate() -> None:
    rows = [
        {
            "queryMs": 10.0,
            "metrics": {
                "recallAt1": 1.0,
                "recallAt3": 1.0,
                "recallAt5": 1.0,
                "reciprocalRankAt5": 1.0,
                "requiredCoveredAt5": True,
            },
        },
        {
            "queryMs": 20.0,
            "metrics": {
                "recallAt1": 0.0,
                "recallAt3": 0.5,
                "recallAt5": 0.5,
                "reciprocalRankAt5": 0.5,
                "requiredCoveredAt5": False,
            },
        },
    ]
    gates = {
        "minRecallAt1": 0.6,
        "minRecallAt3": 0.8,
        "minRecallAt5": 0.8,
        "minMrrAt5": 0.8,
        "minRequiredCoverage": 0.8,
    }

    aggregate = aggregate_embedder_rows(rows, gates)

    assert aggregate["meanQueryMs"] == 15.0
    assert aggregate["passed"] is False
    assert {failure["gate"] for failure in aggregate["gateFailures"]} == set(gates)
