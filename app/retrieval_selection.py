from __future__ import annotations

import re
from typing import Any


def _chunk_terms(content: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.-]{3,}", content.casefold())
        if token not in {"about", "and", "for", "from", "that", "the", "this", "with", "yash"}
    }


def select_diverse_chunks(
    candidates: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    """Prefer distinct evidence over adjacent chunks repeating the same claim."""
    selected: list[dict[str, Any]] = []
    selected_terms: list[set[str]] = []
    for candidate in candidates:
        terms = _chunk_terms(candidate["content"])
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
        # Preserve diversity when possible, then backfill by similarity so a
        # requested Top 3/5/7 route always returns that many available chunks.
        for candidate in candidates:
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) == top_k:
                break
    return selected
