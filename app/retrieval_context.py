from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def format_source_excerpt(chunk: dict[str, Any], index: int) -> str:
    return (
        f"[S{index}] {chunk.get('title', '')} ({chunk.get('source', '')})\n"
        f"{chunk.get('content', '')}"
    )


def format_source_excerpts(chunks: Sequence[dict[str, Any]]) -> str:
    return "\n\n".join(
        format_source_excerpt(chunk, index) for index, chunk in enumerate(chunks, start=1)
    )
