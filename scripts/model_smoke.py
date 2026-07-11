from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from app.config import load_pipeline
from app.embeddings import EmbeddingRegistry


def rss_mib() -> float:
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    row = next(line for line in status.splitlines() if line.startswith("VmRSS:"))
    return round(int(row.split()[1]) / 1024, 1)


async def main() -> None:
    pipeline = load_pipeline()
    registry = EmbeddingRegistry(pipeline)
    started = time.perf_counter()

    for config in pipeline.embedders:
        model_started = time.perf_counter()
        registry.models[config.id] = await asyncio.to_thread(registry._load_model, config)
        print(
            json.dumps(
                {
                    "event": "loaded",
                    "embedder": config.id,
                    "rssMiB": rss_mib(),
                    "seconds": round(time.perf_counter() - model_started, 2),
                }
            ),
            flush=True,
        )

    for config in pipeline.embedders:
        query_started = time.perf_counter()
        vector = await registry.encode_query(config.id, "What projects has Yash built?")
        print(
            json.dumps(
                {
                    "event": "query",
                    "embedder": config.id,
                    "dimensions": len(vector),
                    "rssMiB": rss_mib(),
                    "milliseconds": round((time.perf_counter() - query_started) * 1000, 1),
                }
            ),
            flush=True,
        )

    print(
        json.dumps(
            {
                "event": "complete",
                "resident": registry.loaded_ids,
                "rssMiB": rss_mib(),
                "seconds": round(time.perf_counter() - started, 2),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
