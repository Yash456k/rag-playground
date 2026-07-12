from __future__ import annotations

import pytest

from app.config import PipelineConfig
from app.database import Database


class _Cursor:
    async def fetchall(self) -> list:
        return []


class _HealthCursor:
    def __init__(self, row: dict) -> None:
        self.row = row

    async def fetchone(self) -> dict:
        return self.row


class _Connection:
    def __init__(self) -> None:
        self.query = ""
        self.parameters = None

    async def execute(self, query: str, parameters):
        self.query = query
        self.parameters = parameters
        return _Cursor()


class _HealthConnection:
    def __init__(self, row: dict) -> None:
        self.row = row
        self.query = ""

    async def execute(self, query):
        self.query = query
        return _HealthCursor(self.row)


class _ConnectionContext:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _Connection:
        return self.connection

    async def __aexit__(self, *_args) -> None:
        return None


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    def connection(self) -> _ConnectionContext:
        return _ConnectionContext(self._connection)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedder_id",
    [
        "minilm-l6",
        "bge-small",
        "bge-base",
        "qwen3-embedding",
        "portfolio-e5-small",
        "portfolio-gte-small",
    ],
)
async def test_retrieve_uses_only_the_selected_embedders_column(
    pipeline: PipelineConfig, embedder_id: str
) -> None:
    connection = _Connection()
    database = object.__new__(Database)
    database.pool = _Pool(connection)
    embedder = pipeline.embedder(embedder_id)

    assert await database.retrieve(embedder, [0.25] * embedder.dimensions, 5) == []

    normalized_query = " ".join(connection.query.as_string(None).split())
    assert normalized_query.count(embedder.column) == 3
    assert all(
        other.column not in normalized_query
        for other in pipeline.embedders
        if other.id != embedder_id
    )
    assert connection.parameters == (
        [0.25] * embedder.dimensions,
        [0.25] * embedder.dimensions,
        5,
    )


@pytest.mark.asyncio
async def test_health_coverage_is_derived_from_the_embedder_registry(
    pipeline: PipelineConfig,
) -> None:
    chunk_count = 9
    row = {
        "chunks": chunk_count,
        **{embedder.column: chunk_count for embedder in pipeline.embedders},
    }
    connection = _HealthConnection(row)
    database = object.__new__(Database)
    database.embedders = tuple(pipeline.embedders)
    database.pool = _Pool(connection)

    health = await database.health()

    assert health == {
        "ok": True,
        "chunks": chunk_count,
        "vectorCoverage": {embedder.id: chunk_count for embedder in pipeline.embedders},
    }
    normalized_query = " ".join(connection.query.as_string(None).split())
    assert all(embedder.column in normalized_query for embedder in pipeline.embedders)
