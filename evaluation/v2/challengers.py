from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChallengerConfig(BaseModel):
    """Benchmark-only embedder definition; never enters the production registry."""

    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str
    description: str
    model: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    dimensions: int = Field(ge=64, le=4096)
    query_prefix: str = ""
    document_prefix: str = ""
    query_prompt_name: str | None = None
    document_prompt_name: str | None = None
    dtype: Literal["float32", "bfloat16", "float16"] = "float32"
    minimum_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    trust_remote_code: bool = False
    license: str
    parameters_millions: float = Field(gt=0)
    source_url: str
    rationale: str

    @model_validator(mode="after")
    def validate_prompt_configuration(self) -> ChallengerConfig:
        if self.query_prefix and self.query_prompt_name:
            raise ValueError("query_prefix and query_prompt_name are mutually exclusive")
        if self.document_prefix and self.document_prompt_name:
            raise ValueError("document_prefix and document_prompt_name are mutually exclusive")
        return self


class ChallengerManifest(BaseModel):
    version: Literal[1]
    researched_at: str
    candidates: list[ChallengerConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> ChallengerManifest:
        ids = [item.id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("challenger IDs must be unique")
        return self


def load_challengers(path: str | Path) -> ChallengerManifest:
    manifest_path = Path(path)
    with manifest_path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return ChallengerManifest.model_validate(payload)
