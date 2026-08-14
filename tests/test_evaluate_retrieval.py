from __future__ import annotations

import pytest

from app.retrieval_context import format_source_excerpts
from evaluation.eval_lib import CONTEXT_CHAR_BUDGETS, ranking_metrics
from scripts.evaluate_retrieval import aggregate_embedder_rows


def _group(source: str, chunk_index: int) -> dict:
    return {
        "label": f"{source}-{chunk_index}",
        "any_of": [{"source": source, "chunk_indexes": [chunk_index]}],
    }


def test_ranking_metrics_score_multiple_required_evidence_groups() -> None:
    groups = [_group("experience.md", 1), _group("projects.md", 2)]
    chunks = [
        {
            "source": "experience.md",
            "chunkIndex": 1,
            "content": "AIVID scale notification system",
        },
        {"source": "noise.md", "chunkIndex": 0, "content": "unrelated words"},
        {
            "source": "projects.md",
            "chunkIndex": 2,
            "content": "NSK concurrency system",
        },
    ]

    metrics = ranking_metrics(groups, chunks)

    assert metrics["recallAt1"] == 0.5
    assert metrics["recallAt3"] == 1.0
    assert metrics["recallAt5"] == 1.0
    assert metrics["reciprocalRankAt5"] == 1.0
    assert metrics["requiredCoveredAt5"] is True
    assert metrics["evidenceGroupRanks"] == [1, 3]
    assert metrics["allEvidenceAt1"] is False
    assert metrics["allEvidenceAt3"] is True
    assert metrics["allEvidenceAt5"] is True
    assert metrics["meanReciprocalEvidenceRankAt5"] == pytest.approx(2 / 3)
    assert metrics["meanEvidenceDiscountAt5"] == pytest.approx(0.75)
    assert metrics["requiredContextPrecisionAt5"] == pytest.approx(2 / 3)
    assert metrics["contextRedundancyAt5"] == pytest.approx(1 / 18)
    assert metrics["contextCharsAt5"] == len(format_source_excerpts(chunks))
    assert metrics["sourceDiversityAt5"] == 1.0
    assert metrics["recallAt1500Chars"] == 1.0
    assert metrics["allEvidenceAt1500Chars"] is True


def test_ranking_metrics_compare_evidence_at_fixed_context_budgets() -> None:
    groups = [_group("experience.md", 1), _group("projects.md", 2)]
    chunks = [
        {"source": "experience.md", "chunkIndex": 1, "content": "a" * 700},
        {"source": "noise.md", "chunkIndex": 0, "content": "b" * 700},
        {"source": "projects.md", "chunkIndex": 2, "content": "c" * 700},
    ]

    metrics = ranking_metrics(groups, chunks)

    assert metrics["recallAt1500Chars"] == 0.5
    assert metrics["allEvidenceAt1500Chars"] is False
    assert metrics["contextChunksAt1500Chars"] == 2
    assert metrics["contextCharsAt1500Chars"] == len(format_source_excerpts(chunks[:2]))
    assert metrics["recallAt2000Chars"] == 0.5
    assert metrics["recallAt2500Chars"] == 1.0
    assert metrics["allEvidenceAt2500Chars"] is True
    assert metrics["contextChunksAt2500Chars"] == 3


def test_ranking_metrics_never_exceed_a_context_budget() -> None:
    groups = [_group("experience.md", 1)]
    chunks = [
        {"source": "experience.md", "chunkIndex": 1, "content": "x" * 1600},
    ]

    metrics = ranking_metrics(groups, chunks)

    assert metrics["contextChunksAt1500Chars"] == 0
    assert metrics["contextCharsAt1500Chars"] == 0
    assert metrics["recallAt1500Chars"] == 0.0


def test_ranking_metrics_penalize_missing_evidence_and_redundant_context() -> None:
    groups = [_group("experience.md", 1), _group("projects.md", 2)]
    chunks = [
        {"source": "experience.md", "chunkIndex": 1, "content": "same repeated evidence"},
        {"source": "experience.md", "chunkIndex": 3, "content": "same repeated context"},
        {"source": "noise.md", "chunkIndex": 0, "content": "unrelated"},
    ]

    metrics = ranking_metrics(groups, chunks)

    assert metrics["recallAt5"] == 0.5
    assert metrics["allEvidenceAt5"] is False
    assert metrics["requiredContextPrecisionAt5"] == pytest.approx(1 / 3)
    assert metrics["contextRedundancyAt5"] > 0
    assert metrics["sourceDiversityAt5"] == pytest.approx(2 / 3)


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
                "allEvidenceAt1": True,
                "allEvidenceAt3": True,
                "allEvidenceAt5": True,
                "meanReciprocalEvidenceRankAt5": 1.0,
                "meanEvidenceDiscountAt5": 1.0,
                "requiredContextPrecisionAt5": 0.5,
                "contextRedundancyAt5": 0.1,
                "contextCharsAt5": 500,
                "sourceDiversityAt5": 0.6,
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
                "allEvidenceAt1": False,
                "allEvidenceAt3": False,
                "allEvidenceAt5": False,
                "meanReciprocalEvidenceRankAt5": 0.25,
                "meanEvidenceDiscountAt5": 0.3,
                "requiredContextPrecisionAt5": 0.2,
                "contextRedundancyAt5": 0.3,
                "contextCharsAt5": 700,
                "sourceDiversityAt5": 0.4,
            },
        },
    ]
    for budget in CONTEXT_CHAR_BUDGETS:
        rows[0]["metrics"].update(
            {
                f"recallAt{budget}Chars": 1.0,
                f"allEvidenceAt{budget}Chars": True,
                f"contextChunksAt{budget}Chars": 3,
                f"contextCharsAt{budget}Chars": 1400,
            }
        )
        rows[1]["metrics"].update(
            {
                f"recallAt{budget}Chars": 0.5,
                f"allEvidenceAt{budget}Chars": False,
                f"contextChunksAt{budget}Chars": 2,
                f"contextCharsAt{budget}Chars": 1100,
            }
        )
    gates = {
        "minRecallAt1": 0.6,
        "minRecallAt3": 0.8,
        "minRecallAt5": 0.8,
        "minMrrAt5": 0.8,
        "minRequiredCoverage": 0.8,
    }

    aggregate = aggregate_embedder_rows(rows, gates)

    assert aggregate["meanQueryMs"] == 15.0
    assert aggregate["allEvidenceAt5"] == 0.5
    assert aggregate["meanReciprocalEvidenceRankAt5"] == 0.625
    assert aggregate["requiredContextPrecisionAt5"] == 0.35
    assert aggregate["contextRedundancyAt5"] == 0.2
    assert aggregate["meanContextCharsAt5"] == 600.0
    assert aggregate["recallAt1500Chars"] == 0.75
    assert aggregate["allEvidenceAt1500Chars"] == 0.5
    assert aggregate["meanContextChunksAt1500Chars"] == 2.5
    assert aggregate["meanContextCharsAt1500Chars"] == 1250.0
    assert aggregate["passed"] is False
    assert {failure["gate"] for failure in aggregate["gateFailures"]} == set(gates)
