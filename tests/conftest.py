from __future__ import annotations

import os
import sys
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# app.main constructs the FastAPI object at import time. These inert values let
# helper tests import that module without reading a developer's .env file or
# opening a database/provider connection (the lifespan is never entered).
os.environ.update(
    {
        "GROQ_API_KEY": "test-groq-key-not-a-real-secret-000000",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:55432/test",
        "FRONTEND_ORIGINS": "https://portfolio.example.test",
        "PUBLIC_API_URL": "https://api.example.test",
        "ALLOWED_HOSTS": "testserver,api.example.test",
        "TRUSTED_PROXY_CIDRS": "127.0.0.1/32,172.16.0.0/12",
        "IP_HASH_SALT": "unit-test-ip-hash-salt-000000",
        "VERIFY_FALLBACK_TOKEN": "unit-test-fallback-token-000000",
    }
)

# Unit tests exercise chunking and event helpers, not model execution. Keep the
# suite runnable in a lightweight test environment while using the real modules
# automatically in the application image.
if find_spec("torch") is None:
    torch_stub = ModuleType("torch")
    torch_stub.bfloat16 = object()
    sys.modules["torch"] = torch_stub

if find_spec("sentence_transformers") is None:
    sentence_transformers_stub = ModuleType("sentence_transformers")

    class _UnavailableSentenceTransformer:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("unit tests must not load embedding models")

    sentence_transformers_stub.SentenceTransformer = _UnavailableSentenceTransformer
    sys.modules["sentence_transformers"] = sentence_transformers_stub

from app.config import PipelineConfig, load_pipeline  # noqa: E402


@pytest.fixture
def pipeline() -> PipelineConfig:
    load_pipeline.cache_clear()
    return load_pipeline(PROJECT_ROOT / "config" / "pipeline.yaml")


@pytest.fixture
def pipeline_data(pipeline: PipelineConfig) -> dict:
    return pipeline.model_dump(mode="python")
