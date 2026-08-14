from __future__ import annotations

import pytest

from app.config import PipelineConfig
from app.ingest import SourceDocument, _split_oversized, _word_aligned_suffix, chunk_document


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


def test_new_chunk_starts_with_word_aligned_overlap(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data, overlap=24, minimum=20)
    first = " ".join(f"first-{index}" for index in range(18))
    second = " ".join(f"second-{index}" for index in range(10))

    chunks = chunk_document(_document(f"{first}\n\n{second}"), pipeline)

    assert len(chunks) == 2
    expected_overlap = _word_aligned_suffix(
        chunks[0].content, pipeline.chunking.overlap_characters
    )
    assert chunks[1].content.startswith(expected_overlap)
    assert chunks[1].content.split(maxsplit=1)[0] in chunks[0].content.split()
    assert all(len(chunk.content) <= pipeline.chunking.max_characters for chunk in chunks)


def test_overlap_suffix_drops_partial_leading_word() -> None:
    assert _word_aligned_suffix("alpha product engineering", 15) == "engineering"


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


def test_manual_chunks_use_exact_boundaries_without_overlap(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data, maximum=200, overlap=20, minimum=20)
    content = """<!-- rag-chunk: profile | Education and engineering focus -->
# Profile

Alpha facts stay together.

<!-- rag-chunk: delivery | Production delivery evidence -->
## Delivery

Beta facts stay together.
"""

    chunks = chunk_document(_document(content), pipeline)

    assert [chunk.semantic_id for chunk in chunks] == ["profile", "delivery"]
    assert chunks[0].content == (
        "Topic: Education and engineering focus\n\n# Profile\n\nAlpha facts stay together."
    )
    assert chunks[1].content == (
        "Topic: Production delivery evidence\n\n## Delivery\n\nBeta facts stay together."
    )
    assert "Beta facts" not in chunks[0].content
    assert "Alpha facts" not in chunks[1].content


def test_locked_automatic_chunking_ignores_manual_marker_lines(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data, maximum=200, overlap=20, minimum=20)
    marked = """<!-- rag-chunk: alpha | Alpha -->
# Profile

Alpha facts.

<!-- rag-chunk: beta | Beta -->
## Delivery

Beta facts.
"""
    plain = """# Profile

Alpha facts.

## Delivery

Beta facts.
"""

    marked_chunks = chunk_document(_document(marked), pipeline, honor_manual=False)
    plain_chunks = chunk_document(_document(plain), pipeline)

    assert [chunk.content for chunk in marked_chunks] == [chunk.content for chunk in plain_chunks]


def test_inline_manual_boundary_preserves_automatic_sentence_stream(
    pipeline_data: dict,
) -> None:
    pipeline = _with_chunking(pipeline_data, maximum=200, overlap=20, minimum=20)
    marked = """<!-- rag-chunk: first | First topic -->
Alpha facts end here.<!-- rag-chunk: second | Second topic -->Beta facts start here.
"""
    plain = "Alpha facts end here. Beta facts start here."

    manual_chunks = chunk_document(_document(marked), pipeline)
    marked_auto = chunk_document(_document(marked), pipeline, honor_manual=False)
    plain_auto = chunk_document(_document(plain), pipeline)

    assert [chunk.semantic_id for chunk in manual_chunks] == ["first", "second"]
    assert [(chunk.index, chunk.content) for chunk in marked_auto] == [
        (chunk.index, chunk.content) for chunk in plain_auto
    ]


def test_duplicate_manual_chunk_ids_fail_closed(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data)
    content = """<!-- rag-chunk: repeated | First -->
Alpha.

<!-- rag-chunk: repeated | Second -->
Beta.
"""

    with pytest.raises(RuntimeError, match="duplicate manual chunk id"):
        chunk_document(_document(content), pipeline)


def test_malformed_manual_chunk_markers_fail_closed(pipeline_data: dict) -> None:
    pipeline = _with_chunking(pipeline_data)
    content = """<!-- rag-chunk: missing-topic -->
Alpha facts must not silently fall back to automatic chunking.
"""

    with pytest.raises(RuntimeError, match="Malformed manual chunk marker"):
        chunk_document(_document(content), pipeline)
