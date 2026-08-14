from __future__ import annotations

from app.retrieval_context import format_source_excerpts
from app.retrieval_protocol import retrieval_candidate_depth, retrieval_protocol


def test_candidate_depth_matches_production_cap() -> None:
    assert retrieval_candidate_depth(3) == 9
    assert retrieval_candidate_depth(5) == 12
    assert retrieval_candidate_depth(12) == 12


def test_retrieval_protocol_serializes_selector_settings() -> None:
    protocol = retrieval_protocol(5)

    assert protocol["topK"] == 5
    assert protocol["candidateDepth"] == 12
    assert protocol["queryBuilder"] == "app.retrieval_query.build_retrieval_query"
    assert protocol["selector"] == {
        "implementation": "app.retrieval_selection.select_diverse_chunks",
        "globalSimilarityThreshold": 0.6,
        "adjacentSimilarityThreshold": 0.32,
        "adjacencyDistance": 1,
        "backfillBySimilarityOrder": True,
    }


def test_source_excerpt_format_matches_prompt_contract() -> None:
    chunks = [
        {"title": "First", "source": "one.md", "content": "alpha"},
        {"title": "Second", "source": "two.md", "content": "beta"},
    ]

    assert format_source_excerpts(chunks) == (
        "[S1] First (one.md)\nalpha\n\n[S2] Second (two.md)\nbeta"
    )
