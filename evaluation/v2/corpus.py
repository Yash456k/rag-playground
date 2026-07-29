from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CorpusChunk:
    id: str
    source: str
    title: str
    index: int
    content: str


def load_corpus_chunks(corpus_root: Path, pipeline: Any) -> list[CorpusChunk]:
    """Build the evaluation corpus through the production ingestion path."""
    # Keep pure metric/report helpers importable in lightweight environments;
    # the target benchmark host installs the production ingestion dependencies.
    from app.ingest import chunk_document, discover_documents

    chunks = [
        chunk
        for document in discover_documents(corpus_root)
        for chunk in chunk_document(document, pipeline)
    ]
    return [
        CorpusChunk(
            id=f"{chunk.source}#{chunk.index}",
            source=chunk.source,
            title=chunk.title,
            index=chunk.index,
            content=chunk.content,
        )
        for chunk in chunks
    ]
