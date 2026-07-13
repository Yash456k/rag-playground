from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChunkingConfig(BaseModel):
    max_characters: int = Field(ge=200, le=4000)
    overlap_characters: int = Field(ge=0, le=1000)
    minimum_characters: int = Field(ge=1, le=1000)

    @model_validator(mode="after")
    def validate_overlap(self) -> ChunkingConfig:
        if self.overlap_characters >= self.max_characters:
            raise ValueError("chunk overlap must be smaller than chunk size")
        return self


class RetrievalConfig(BaseModel):
    top_k: int = Field(ge=1, le=12)


class GenerationConfig(BaseModel):
    temperature: float = Field(ge=0, le=1)
    max_tokens: int = Field(ge=64, le=1200)
    request_timeout_seconds: int = Field(ge=5, le=120)


class EmbedderConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str
    description: str
    model: str
    revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    dimensions: int = Field(ge=64, le=4096)
    column: Literal[
        "embedding_minilm",
        "embedding_bge_small",
        "embedding_bge_base",
        "embedding_qwen3",
        "embedding_portfolio_e5",
        "embedding_portfolio_gte",
    ]
    query_prefix: str = ""
    document_prefix: str = ""
    dtype: Literal["float32", "bfloat16"] = "float32"
    minimum_score: float = Field(ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def require_pinned_remote_revision(self) -> EmbedderConfig:
        is_local = self.model.startswith(("/", "./", "../"))
        if not is_local and self.revision is None:
            raise ValueError("remote embedder models require a pinned revision")
        return self


class LlmConfig(BaseModel):
    id: str
    label: str
    description: str
    provider: Literal["groq", "openrouter"] = "groq"
    input_usd_per_million: float = Field(ge=0)
    output_usd_per_million: float = Field(ge=0)

    def reserve_micro_usd(self, input_tokens: int, output_tokens: int) -> int:
        # $/million-token pricing is numerically equal to micro-USD/token.
        return math.ceil(
            input_tokens * self.input_usd_per_million
            + output_tokens * self.output_usd_per_million
        )


class PipelineConfig(BaseModel):
    version: int
    chunking: ChunkingConfig
    retrieval: RetrievalConfig
    generation: GenerationConfig
    embedders: list[EmbedderConfig] = Field(min_length=1)
    llms: list[LlmConfig] = Field(min_length=1)
    fallback_order: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_registry(self) -> PipelineConfig:
        embedder_ids = [item.id for item in self.embedders]
        columns = [item.column for item in self.embedders]
        llm_ids = [item.id for item in self.llms]
        if len(embedder_ids) != len(set(embedder_ids)):
            raise ValueError("embedder ids must be unique")
        if len(columns) != len(set(columns)):
            raise ValueError("each embedder must have its own vector column")
        if len(llm_ids) != len(set(llm_ids)):
            raise ValueError("LLM ids must be unique")
        if not set(self.fallback_order).issubset(llm_ids):
            raise ValueError("fallback_order may only contain configured LLM ids")
        return self

    def embedder(self, embedder_id: str) -> EmbedderConfig:
        try:
            return next(item for item in self.embedders if item.id == embedder_id)
        except StopIteration as exc:
            raise KeyError(embedder_id) from exc

    def llm(self, llm_id: str) -> LlmConfig:
        try:
            return next(item for item in self.llms if item.id == llm_id)
        except StopIteration as exc:
            raise KeyError(llm_id) from exc

    def request_cost_reserve_micro_usd(self, llm_id: str, input_tokens: int) -> int:
        candidates = dict.fromkeys([llm_id, *self.fallback_order])
        # Reserve every possible attempt. A provider may consume input before an
        # empty/error stream causes the client to try the fallback.
        return sum(
            self.llm(candidate).reserve_micro_usd(
                input_tokens,
                self.generation.max_tokens,
            )
            for candidate in candidates
        )

    def public_dict(self) -> dict:
        return {
            "version": self.version,
            "defaults": {
                "embedder": (
                    self.embedders[1].id if len(self.embedders) > 1 else self.embedders[0].id
                ),
                "llm": self.llms[0].id,
            },
            "embedders": [
                {
                    "id": item.id,
                    "label": item.label,
                    "description": item.description,
                    "dimensions": item.dimensions,
                    "optimization": {
                        "portfolioTuned": item.id.startswith("portfolio-"),
                        "queryTransform": (
                            "E5 query/passage prefixes"
                            if item.document_prefix
                            else "retrieval query instruction"
                            if item.query_prefix
                            else "symmetric text encoding"
                        ),
                        "minimumScore": item.minimum_score,
                    },
                }
                for item in self.embedders
            ],
            "llms": [
                {
                    "id": item.id,
                    "label": item.label,
                    "description": item.description,
                    "provider": item.provider,
                }
                for item in self.llms
            ],
            "retrieval": {
                "topK": self.retrieval.top_k,
                "selectableTopK": [3, 5, 7],
                "historyAware": True,
            },
        }


@lru_cache
def load_pipeline(path: str | Path | None = None) -> PipelineConfig:
    config_path = Path(path or Path(__file__).parents[1] / "config" / "pipeline.yaml")
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return PipelineConfig.model_validate(raw)
