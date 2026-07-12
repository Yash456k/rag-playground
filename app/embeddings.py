from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.config import EmbedderConfig, PipelineConfig

logger = logging.getLogger(__name__)


class EmbeddingRegistry:
    """Loads the complete embedding ladder once and keeps every model resident."""

    def __init__(self, pipeline: PipelineConfig) -> None:
        self.pipeline = pipeline
        self.models: dict[str, SentenceTransformer] = {}
        self.encode_lock = asyncio.Lock()

    def _load_model(self, config: EmbedderConfig) -> SentenceTransformer:
        model_kwargs: dict[str, Any] = {"use_safetensors": True}
        if config.dtype == "bfloat16":
            model_kwargs["dtype"] = torch.bfloat16
            model_kwargs["attn_implementation"] = "eager"
        logger.info("Loading resident embedder %s from %s", config.id, config.model)
        loader_kwargs: dict[str, Any] = {
            "device": "cpu",
            "model_kwargs": model_kwargs,
            "trust_remote_code": False,
        }
        # Local fine-tuned artifacts do not have a Hugging Face commit revision.
        # Omit the argument instead of forwarding revision=None.
        if config.revision is not None:
            loader_kwargs["revision"] = config.revision
        model = SentenceTransformer(config.model, **loader_kwargs)
        model.max_seq_length = min(int(model.max_seq_length), 512)
        self._encode_sync(model, ["resident model warm-up"], prefix=config.query_prefix)
        return model

    async def load_all(self) -> None:
        # Sequential loading avoids overlapping allocation spikes on the 8 GiB host.
        for config in self.pipeline.embedders:
            self.models[config.id] = await asyncio.to_thread(self._load_model, config)
        logger.info("All %d embedders are resident", len(self.models))

    @staticmethod
    def _encode_sync(
        model: SentenceTransformer,
        texts: Sequence[str],
        *,
        prefix: str = "",
        batch_size: int = 8,
    ) -> np.ndarray:
        prepared = [f"{prefix}{text}" for text in texts]
        tensor = model.encode(
            prepared,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_tensor=True,
            show_progress_bar=False,
        )
        return tensor.float().cpu().numpy()

    async def encode_query(self, embedder_id: str, query: str) -> list[float]:
        config = self.pipeline.embedder(embedder_id)
        model = self.models[embedder_id]
        async with self.encode_lock:
            result = await asyncio.to_thread(
                self._encode_sync,
                model,
                [query],
                prefix=config.query_prefix,
                batch_size=1,
            )
        vector = result[0]
        if vector.shape[0] != config.dimensions:
            raise RuntimeError(
                f"{embedder_id} returned {vector.shape[0]} dimensions; expected {config.dimensions}"
            )
        return vector.tolist()

    def encode_documents(
        self,
        embedder_id: str,
        texts: Sequence[str],
        *,
        batch_size: int = 8,
    ) -> np.ndarray:
        config = self.pipeline.embedder(embedder_id)
        result = self._encode_sync(
            self.models[embedder_id],
            texts,
            prefix=config.document_prefix,
            batch_size=batch_size,
        )
        if result.shape[1] != config.dimensions:
            raise RuntimeError(
                f"{embedder_id} returned {result.shape[1]} dimensions; expected {config.dimensions}"
            )
        return result

    @property
    def loaded_ids(self) -> list[str]:
        return list(self.models)
