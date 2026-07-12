from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from evaluation.eval_lib import (
    EVALUATION_ROOT,
    EvaluationDataError,
    load_cases,
    load_gates,
    mean,
    ranking_metrics,
    select_cases,
    write_report,
)

METRIC_GATE_MAP = {
    "minRecallAt1": "recallAt1",
    "minRecallAt3": "recallAt3",
    "minRecallAt5": "recallAt5",
    "minMrrAt5": "mrrAt5",
    "minRequiredCoverage": "requiredCoverage",
}


def aggregate_embedder_rows(
    rows: list[dict[str, Any]], gates: dict[str, float]
) -> dict[str, Any]:
    if not rows:
        raise EvaluationDataError("Cannot aggregate an empty retrieval result")
    metrics = {
        "recallAt1": mean(row["metrics"]["recallAt1"] for row in rows),
        "recallAt3": mean(row["metrics"]["recallAt3"] for row in rows),
        "recallAt5": mean(row["metrics"]["recallAt5"] for row in rows),
        "mrrAt5": mean(row["metrics"]["reciprocalRankAt5"] for row in rows),
        "requiredCoverage": mean(
            float(row["metrics"]["requiredCoveredAt5"]) for row in rows
        ),
        "meanQueryMs": mean(row["queryMs"] for row in rows),
    }
    metrics = {key: round(value, 6) for key, value in metrics.items()}
    failures = [
        {
            "gate": gate,
            "actual": metrics[metric],
            "required": threshold,
        }
        for gate, metric in METRIC_GATE_MAP.items()
        if (threshold := gates.get(gate)) is not None and metrics[metric] < threshold
    ]
    return {
        "caseCount": len(rows),
        **metrics,
        "gateFailures": failures,
        "passed": not failures,
    }


async def run_retrieval(
    cases: list[dict[str, Any]],
    *,
    embedder_ids: list[str],
    pipeline_path: Path,
    top_k: int,
) -> list[dict[str, Any]]:
    # Heavy runtime imports stay inside the live path so metric tests remain lightweight.
    from app.config import load_pipeline
    from app.database import Database
    from app.embeddings import EmbeddingRegistry
    from app.settings import get_settings

    load_pipeline.cache_clear()
    pipeline = load_pipeline(pipeline_path)
    known = {item.id for item in pipeline.embedders}
    unknown = set(embedder_ids) - known
    if unknown:
        raise EvaluationDataError(f"Unknown embedders: {', '.join(sorted(unknown))}")
    selected_configs = [item for item in pipeline.embedders if item.id in embedder_ids]
    selected_pipeline = pipeline.model_copy(update={"embedders": selected_configs})
    registry = EmbeddingRegistry(selected_pipeline)
    database = Database(get_settings().database_url)
    await database.open()
    try:
        await registry.load_all()
        rows: list[dict[str, Any]] = []
        for config in selected_configs:
            for case in cases:
                started = time.perf_counter()
                vector = await registry.encode_query(config.id, case["question"])
                chunks = await database.retrieve(config, vector, top_k)
                elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
                rows.append(
                    {
                        "split": case["split"],
                        "caseId": case["id"],
                        "category": case["category"],
                        "question": case["question"],
                        "embedder": config.id,
                        "queryMs": elapsed_ms,
                        "metrics": ranking_metrics(case["required_evidence"], chunks),
                        "retrievedChunks": chunks,
                    }
                )
        return rows
    finally:
        await database.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate every configured embedding route against locked portfolio qrels"
    )
    parser.add_argument("--split", choices=["dev", "heldout", "all"], default="all")
    parser.add_argument("--embedder", action="append", default=[])
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--pipeline", type=Path, default=Path("config/pipeline.yaml"))
    parser.add_argument("--evaluation-dir", type=Path, default=EVALUATION_ROOT)
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--no-gate", action="store_true")
    return parser.parse_args(argv)


def async_main(args: argparse.Namespace) -> int:
    if not 5 <= args.top_k <= 12:
        raise EvaluationDataError("--top-k must be between 5 and 12")
    splits = ["dev", "heldout"] if args.split == "all" else [args.split]
    all_cases = load_cases(splits, args.evaluation_dir)
    cases = select_cases(
        all_cases,
        case_ids=args.case,
        categories=args.category,
        include_refusals=False,
    )
    gates = load_gates(args.evaluation_dir)["retrieval"]

    from app.config import load_pipeline

    load_pipeline.cache_clear()
    pipeline = load_pipeline(args.pipeline)
    embedder_ids = args.embedder or [item.id for item in pipeline.embedders]
    rows = asyncio.run(
        run_retrieval(
            cases,
            embedder_ids=embedder_ids,
            pipeline_path=args.pipeline,
            top_k=args.top_k,
        )
    )
    by_embedder = {
        embedder_id: aggregate_embedder_rows(
            [row for row in rows if row["embedder"] == embedder_id], gates
        )
        for embedder_id in embedder_ids
    }
    passed = all(result["passed"] for result in by_embedder.values())
    summary = {
        "schemaVersion": 1,
        "kind": "retrieval-evaluation",
        "splits": splits,
        "caseIds": [case["id"] for case in cases],
        "topK": args.top_k,
        "gatesEnforced": not args.no_gate,
        "gates": gates,
        "embedders": by_embedder,
        "passed": passed,
    }
    json_path, jsonl_path = write_report(args.output_dir, "retrieval", summary, rows)
    print(
        json.dumps(
            {
                "passed": passed,
                "summary": str(json_path),
                "details": str(jsonl_path),
                "embedders": by_embedder,
            },
            separators=(",", ":"),
        )
    )
    return 0 if passed or args.no_gate else 1


def main(argv: list[str] | None = None) -> int:
    try:
        return async_main(parse_args(argv))
    except EvaluationDataError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        # Database URLs can contain credentials; never echo arbitrary exception text.
        print(json.dumps({"error": "retrieval_runtime_failed", "type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
