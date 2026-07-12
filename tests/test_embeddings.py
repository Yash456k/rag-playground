from __future__ import annotations

import numpy as np

from app.config import PipelineConfig
from app.embeddings import EmbeddingRegistry


def test_local_model_loader_omits_null_revision(
    pipeline: PipelineConfig, monkeypatch
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeModel:
        max_seq_length = 256

        def __init__(self, model: str, **kwargs) -> None:
            calls.append((model, kwargs))

    monkeypatch.setattr("app.embeddings.SentenceTransformer", FakeModel)
    monkeypatch.setattr(
        EmbeddingRegistry,
        "_encode_sync",
        staticmethod(lambda *_args, **_kwargs: np.zeros((1, 384), dtype=np.float32)),
    )
    registry = EmbeddingRegistry(pipeline)

    registry._load_model(pipeline.embedder("portfolio-e5-small"))

    assert calls[0][0] == "/model-artifacts/portfolio-e5-small-v1"
    assert "revision" not in calls[0][1]


def test_remote_model_loader_forwards_pinned_revision(
    pipeline: PipelineConfig, monkeypatch
) -> None:
    calls: list[dict] = []

    class FakeModel:
        max_seq_length = 256

        def __init__(self, _model: str, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.setattr("app.embeddings.SentenceTransformer", FakeModel)
    monkeypatch.setattr(
        EmbeddingRegistry,
        "_encode_sync",
        staticmethod(lambda *_args, **_kwargs: np.zeros((1, 384), dtype=np.float32)),
    )
    registry = EmbeddingRegistry(pipeline)
    config = pipeline.embedder("minilm-l6")

    registry._load_model(config)

    assert calls[0]["revision"] == config.revision


def test_document_encoding_applies_configured_document_prefix(
    pipeline: PipelineConfig, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    def fake_encode(_model, texts, *, prefix: str, batch_size: int):
        captured.update(texts=list(texts), prefix=prefix, batch_size=batch_size)
        return np.zeros((len(texts), 384), dtype=np.float32)

    monkeypatch.setattr(EmbeddingRegistry, "_encode_sync", staticmethod(fake_encode))
    registry = EmbeddingRegistry(pipeline)
    registry.models["portfolio-e5-small"] = object()

    result = registry.encode_documents("portfolio-e5-small", ["one", "two"], batch_size=2)

    assert result.shape == (2, 384)
    assert captured == {"texts": ["one", "two"], "prefix": "passage: ", "batch_size": 2}
