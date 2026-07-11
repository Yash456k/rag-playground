from __future__ import annotations

from app.config import PipelineConfig
from app.ingest import SourceDocument, _split_oversized, chunk_document


def _with_chunking(
    pipeline_data: dict,
    *,
    maximum: int = 200,
    overlap: int = 20,
    minimum: int = 40,
) -> PipelineConfig:
    pipeline_data["chunking"] = {
        "max_characters": maximum,
        "overlap_characters": overlap,
        "minimum_characters": minimum,
    }
    return PipelineConfig.model_validate(pipeline_data)


def _document(content: str) -> SourceDocument:
    return SourceDocument(source="test.md", title="Test", content=content)


def test_chunk_indices_are_contiguous_and_normal_chunks_respect_hard_limit(
    pipeline_data: dict,
) -> None:
    pipeline = _with_chunking(pipeline_data)
    paragraphs = [
        " ".join(f"alpha-{index}" for index in range(24)),
        " ".join(f"beta-{index}" for index in range(24)),
        " ".join(f"gamma-{index}" for index in range(24)),
    ]

    chunks = chunk_document(_document("\n\n".join(paragraphs)), pipeline)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.source == "test.md" and chunk.title == "Test" for chunk in chunks)
    assert all(0 < len(chunk.content) <= pipeline.chunking.max_characters for chunk in chunks)


def test_new_chunk_starts_with_configured_overlap(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data, overlap=24, minimum=20)
    first = " ".join(f"first-{index}" for index in range(18))
    second = " ".join(f"second-{index}" for index in range(10))

    chunks = chunk_document(_document(f"{first}\n\n{second}"), pipeline)

    assert len(chunks) == 2
    expected_overlap = chunks[0].content[-pipeline.chunking.overlap_characters :].lstrip()
    assert chunks[1].content.startswith(expected_overlap)


def test_short_tail_merge_never_exceeds_hard_maximum(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data, overlap=20, minimum=100)
    nearly_full = " ".join("a" for _ in range(95))
    short_tail = " ".join("b" for _ in range(10))

    chunks = chunk_document(_document(f"{nearly_full}\n\n{short_tail}"), pipeline)

    assert all(len(chunk.content) <= pipeline.chunking.max_characters for chunk in chunks)


def test_unbroken_tokens_are_split_at_hard_maximum(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data)

    chunks = chunk_document(_document("x" * 450), pipeline)

    assert _split_oversized("x" * 450, 200) == ["x" * 200, "x" * 200, "x" * 50]
    assert chunks[-1].content.endswith("x" * 50)
    assert all(len(chunk.content) <= pipeline.chunking.max_characters for chunk in chunks)
