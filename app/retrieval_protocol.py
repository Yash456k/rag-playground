from __future__ import annotations

from typing import Any

from app.retrieval_selection import (
    ADJACENCY_DISTANCE,
    ADJACENT_SIMILARITY_THRESHOLD,
    GLOBAL_SIMILARITY_THRESHOLD,
)


def embedding_route_protocol(config: Any) -> dict[str, Any]:
    return {
        "model": config.model,
        "revision": config.revision,
        "dimensions": config.dimensions,
        "queryPrefix": config.query_prefix,
        "documentPrefix": config.document_prefix,
        "dtype": config.dtype,
        "minimumScore": config.minimum_score,
    }


def retrieval_candidate_depth(top_k: int) -> int:
    return min(12, top_k * 3)


def retrieval_protocol(top_k: int) -> dict[str, Any]:
    return {
        "ranking": "exact cosine via normalized matrix-vector product",
        "topK": top_k,
        "candidateDepth": retrieval_candidate_depth(top_k),
        "queryBuilder": "app.retrieval_query.build_retrieval_query",
        "selector": {
            "implementation": "app.retrieval_selection.select_diverse_chunks",
            "globalSimilarityThreshold": GLOBAL_SIMILARITY_THRESHOLD,
            "adjacentSimilarityThreshold": ADJACENT_SIMILARITY_THRESHOLD,
            "adjacencyDistance": ADJACENCY_DISTANCE,
            "backfillBySimilarityOrder": True,
        },
    }
