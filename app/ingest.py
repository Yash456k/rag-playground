from __future__ import annotations

import argparse
import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from pypdf import PdfReader

from app.config import PipelineConfig, load_pipeline
from app.database import content_digest
from app.embeddings import EmbeddingRegistry
from app.settings import get_settings

logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}


@dataclass(frozen=True)
class SourceDocument:
    source: str
    title: str
    content: str


@dataclass(frozen=True)
class Chunk:
    source: str
    title: str
    index: int
    content: str


def read_source(path: Path, root: Path) -> SourceDocument:
    if path.suffix.lower() == ".pdf":
        pages = [page.extract_text() or "" for page in PdfReader(path).pages]
        content = "\n\n".join(pages)
    else:
        content = path.read_text(encoding="utf-8")
    content = content.replace("\r\n", "\n").strip()
    heading = next(
        (line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("#")),
        path.stem.replace("-", " ").title(),
    )
    return SourceDocument(
        source=path.relative_to(root).as_posix(),
        title=heading,
        content=content,
    )


def discover_documents(root: Path) -> list[SourceDocument]:
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if not paths:
        raise RuntimeError(f"No supported corpus documents found in {root}")
    documents = [read_source(path, root) for path in paths]
    empty = [document.source for document in documents if not document.content]
    if empty:
        raise RuntimeError(f"Empty corpus documents: {', '.join(empty)}")
    return documents


def _split_oversized(text: str, maximum: int) -> list[str]:
    words = text.split()
    sections: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        if len(word) > maximum:
            if current:
                sections.append(" ".join(current))
                current = []
                length = 0
            sections.extend(word[index : index + maximum] for index in range(0, len(word), maximum))
            continue
        extra = len(word) + (1 if current else 0)
        if current and length + extra > maximum:
            sections.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += extra
    if current:
        sections.append(" ".join(current))
    return sections


def _word_aligned_suffix(text: str, maximum: int) -> str:
    """Return at most ``maximum`` trailing characters without starting mid-token."""
    if maximum <= 0:
        return ""
    start = max(0, len(text) - maximum)
    if start == 0:
        return text
    if text[start - 1].isspace() or text[start].isspace():
        return text[start:].lstrip()
    boundary = re.search(r"\s+", text[start:])
    if boundary is None:
        return ""
    return text[start + boundary.end() :].lstrip()


def chunk_document(document: SourceDocument, pipeline: PipelineConfig) -> list[Chunk]:
    config = pipeline.chunking
    raw_sections = [
        re.sub(r"\s+", " ", section).strip()
        for section in re.split(r"\n\s*\n", document.content)
        if section.strip()
    ]
    sections: list[str] = []
    for section in raw_sections:
        if len(section) > config.max_characters:
            sections.extend(_split_oversized(section, config.max_characters))
        else:
            sections.append(section)

    texts: list[str] = []
    current = ""
    for section in sections:
        candidate = f"{current}\n\n{section}".strip() if current else section
        if current and len(candidate) > config.max_characters:
            texts.append(current)
            available_overlap = max(0, config.max_characters - len(section) - 2)
            overlap_length = min(config.overlap_characters, available_overlap)
            overlap = _word_aligned_suffix(current, overlap_length)
            current = f"{overlap}\n\n{section}".strip() if overlap else section
        else:
            current = candidate
    if current:
        merged_length = len(texts[-1]) + 2 + len(current) if texts else 0
        if (
            texts
            and len(current) < config.minimum_characters
            and merged_length <= config.max_characters
        ):
            texts[-1] = f"{texts[-1]}\n\n{current}"
        else:
            texts.append(current)

    return [Chunk(document.source, document.title, index, text) for index, text in enumerate(texts)]


async def load_registry(pipeline: PipelineConfig) -> EmbeddingRegistry:
    registry = EmbeddingRegistry(pipeline)
    await registry.load_all()
    return registry


def ingest(corpus_path: Path) -> None:
    settings = get_settings()
    pipeline = load_pipeline()
    documents = discover_documents(corpus_path)
    chunks = [chunk for document in documents for chunk in chunk_document(document, pipeline)]
    logger.info("Prepared %d chunks from %d documents", len(chunks), len(documents))

    registry = asyncio.run(load_registry(pipeline))
    texts = [chunk.content for chunk in chunks]
    vectors = {
        config.id: registry.encode_documents(config.id, texts).tolist()
        for config in pipeline.embedders
    }

    schema = (Path(__file__).parents[1] / "sql" / "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(settings.database_url) as connection:
        connection.execute(schema)
        register_vector(connection)
        with connection.transaction():
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM documents")
            document_ids: dict[str, int] = {}
            for document in documents:
                row = connection.execute(
                    """
                    INSERT INTO documents (source, title, content_hash, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (document.source, document.title, content_digest(document.content), "{}"),
                ).fetchone()
                if row is None:
                    raise RuntimeError(f"Failed to insert {document.source}")
                document_ids[document.source] = int(row[0])

            rows = []
            for index, chunk in enumerate(chunks):
                rows.append(
                    (
                        document_ids[chunk.source],
                        chunk.source,
                        chunk.title,
                        chunk.index,
                        chunk.content,
                        *(vectors[config.id][index] for config in pipeline.embedders),
                    )
                )
            insert_columns = [
                "document_id",
                "source",
                "title",
                "chunk_index",
                "content",
                *(config.column for config in pipeline.embedders),
            ]
            insert_query = sql.SQL("INSERT INTO chunks ({columns}) VALUES ({values})").format(
                columns=sql.SQL(", ").join(map(sql.Identifier, insert_columns)),
                values=sql.SQL(", ").join(sql.Placeholder() for _ in insert_columns),
            )
            with connection.cursor() as cursor:
                cursor.executemany(insert_query, rows)
    logger.info(
        "Ingestion complete: %d documents / %d chunks / %d vector spaces",
        len(documents),
        len(chunks),
        len(pipeline.embedders),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest portfolio documents into all vector spaces"
    )
    parser.add_argument("--corpus", type=Path, default=Path("corpus"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest(args.corpus.resolve())


if __name__ == "__main__":
    main()
