#!/usr/bin/env python3
from __future__ import annotations

# ruff: noqa: E402
import argparse
import gc
import hashlib
import itertools
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import load_pipeline
from evaluation.v2.benchmark import benchmark_model, sanitize_failure
from evaluation.v2.challengers import load_challengers
from evaluation.v2.eval_lib import (
    EvaluationV2Error,
    aggregate,
    cluster_bootstrap,
    evaluate_threshold,
    load_data,
    paired_comparison,
    sha256_path,
    threshold_diagnostics,
    write_json,
    write_jsonl,
)
from evaluation.v2.report import markdown_report


def _csv(values: list[str] | None) -> list[str]:
    return [item.strip() for value in values or [] for item in value.split(",") if item.strip()]


def _git_sha() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        return subprocess.run(  # noqa: S603
            [git, "rev-parse", "HEAD"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _corpus_hash(chunks: list[Any]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(f"{chunk.id}\0{chunk.content}\0".encode())
    return digest.hexdigest()


def _views(
    rows: list[dict[str, Any]],
    samples: int,
    seed: int,
    configured_threshold: float | None,
    configured_threshold_source: str = "config/pipeline.yaml",
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    combinations = [
        (split, tier)
        for split in ("dev", "challenge", "all")
        for tier in ("basic", "intermediate", "all")
    ]
    for split, tier in combinations:
        subset = [
            row for row in rows
            if (split == "all" or row["split"] == split)
            and (tier == "all" or row["tier"] == tier)
        ]
        if not subset:
            continue
        item = aggregate(subset)
        if configured_threshold is None:
            item["configured_threshold_diagnostics"] = {
                "threshold": None,
                "balanced_accuracy": None,
                "false_answer_rate": None,
                "false_refusal_rate": None,
                "available": False,
                "reason": (
                    "No production threshold is configured for this "
                    "benchmark-only challenger."
                ),
                "source": configured_threshold_source,
            }
        else:
            item["configured_threshold_diagnostics"] = {
                **evaluate_threshold(subset, configured_threshold),
                "available": True,
                "source": configured_threshold_source,
            }
        calibration_tier = tier
        calibration = [
            row for row in rows
            if row["split"] == "dev"
            and (calibration_tier == "all" or row["tier"] == calibration_tier)
        ]
        if calibration:
            calibrated = threshold_diagnostics(calibration)
            item["threshold_diagnostics"] = {
                **evaluate_threshold(subset, float(calibrated["threshold"])),
                "calibrated_on": f"dev/{calibration_tier}",
                "available": True,
            }
        else:
            item["threshold_diagnostics"] = {
                "threshold": None,
                "balanced_accuracy": None,
                "false_answer_rate": None,
                "false_refusal_rate": None,
                "available": False,
                "reason": (
                    f"Threshold unavailable: dev/{calibration_tier} calibration "
                    "rows were not selected."
                ),
            }
        item["confidence_intervals"] = cluster_bootstrap(subset, samples=samples, seed=seed)
        item["informational_only"] = split == "all"
        output[f"{split}/{tier}"] = item
    return output


def _paired_views(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for split in ("dev", "challenge"):
        for tier in ("basic", "intermediate", "all"):
            left_subset = [
                row for row in left
                if row["split"] == split and (tier == "all" or row["tier"] == tier)
            ]
            right_subset = [
                row for row in right
                if row["split"] == split and (tier == "all" or row["tier"] == tier)
            ]
            if left_subset and right_subset:
                output[f"{split}/{tier}"] = paired_comparison(left_subset, right_subset)
    if left and right:
        output["all/all"] = {
            **paired_comparison(left, right),
            "informational_only": True,
        }
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Database-free portfolio embedding benchmark V2")
    parser.add_argument("--tier", choices=("basic", "intermediate", "all"), default="all")
    parser.add_argument("--split", choices=("dev", "challenge", "all"), default="all")
    parser.add_argument("--embedder", action="append", help="Repeat or pass comma-separated IDs")
    parser.add_argument(
        "--candidate-manifest",
        type=Path,
        help="Add benchmark-only embedders from a validated YAML manifest",
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--artifact-root", type=Path, default=REPO / "model-artifacts")
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timing-runs", type=int, default=1)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=REPO / "evaluation/results/v2")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.top_k < 5 or args.warmup < 0 or args.timing_runs < 1 or args.bootstrap_samples < 0:
        message = (
            "--top-k >= 5, --warmup >= 0, --timing-runs >= 1, "
            "and --bootstrap-samples >= 0 are required"
        )
        raise EvaluationV2Error(message)
    pipeline = load_pipeline(REPO / "config/pipeline.yaml")
    production = {item.id: item for item in pipeline.embedders}
    configured: dict[str, Any] = dict(production)
    challenger_ids: set[str] = set()
    challenger_manifest_path = (
        args.candidate_manifest.resolve() if args.candidate_manifest else None
    )
    if challenger_manifest_path is not None:
        manifest = load_challengers(challenger_manifest_path)
        challengers = {item.id: item for item in manifest.candidates}
        overlap = sorted(production.keys() & challengers.keys())
        if overlap:
            raise EvaluationV2Error(
                f"Challenger IDs conflict with production embedders: {', '.join(overlap)}"
            )
        configured.update(challengers)
        challenger_ids = set(challengers)
    _, all_cases, chunks = load_data()
    cases = [
        case for case in all_cases
        if (args.tier == "all" or case["tier"] == args.tier)
        and (args.split == "all" or case["split"] == args.split)
    ]
    requested = _csv(args.embedder) or [item.id for item in pipeline.embedders]
    unknown = sorted(set(requested) - configured.keys())
    if unknown:
        raise EvaluationV2Error(f"Unknown embedder IDs: {', '.join(unknown)}")
    if len(requested) != len(set(requested)):
        raise EvaluationV2Error("Embedder IDs must not be duplicated")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_results: list[dict[str, Any]] = []
    raw_by_model: dict[str, list[dict[str, Any]]] = {}
    for embedder_id in requested:
        config = configured[embedder_id]
        try:
            timing, rows = benchmark_model(
                config,
                cases,
                chunks,
                artifact_root=args.artifact_root.resolve(),
                device=args.device,
                warmup=args.warmup,
                timing_runs=args.timing_runs,
                top_k=args.top_k,
            )
            raw_by_model[embedder_id] = rows
            write_jsonl(args.output_dir / f"{embedder_id}.raw.jsonl", rows)
            model_results.append(
                {
                    "id": embedder_id,
                    "status": "ok",
                    "timing": timing,
                    "quality": _views(
                        rows,
                        args.bootstrap_samples,
                        args.seed,
                        config.minimum_score,
                        (
                            str(challenger_manifest_path)
                            if embedder_id in challenger_ids
                            else "config/pipeline.yaml"
                        ),
                    ),
                    "failures": sorted(
                        [row for row in rows if row["answerable"]],
                        key=lambda row: (
                            row["metrics"]["ndcg@5"],
                            row["metrics"]["required_recall@5"],
                            row["id"],
                        ),
                    ),
                    "threshold_errors": sorted(
                        [row for row in rows if not row["answerable"]],
                        key=lambda row: (-row["top_score"], row["id"]),
                    ),
                }
            )
        except Exception as exc:
            model_results.append(
                {"id": embedder_id, "status": "failed", "error": sanitize_failure(exc)}
            )
        finally:
            gc.collect()
            try:
                import torch

            except ImportError:
                cuda = None
            else:
                cuda = getattr(torch, "cuda", None)
            if cuda is not None and cuda.is_available():
                cuda.empty_cache()
    comparisons = {}
    successful = [item["id"] for item in model_results if item["status"] == "ok"]
    for left, right in itertools.combinations(successful, 2):
        comparisons[f"{left} vs {right}"] = _paired_views(
            raw_by_model[left], raw_by_model[right]
        )
    summary = {
        "version": 2,
        "selection": {"tier": args.tier, "split": args.split},
        "models": model_results,
        "paired_comparisons": comparisons,
    }
    manifest = {
        "version": 2,
        "utc_time": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "hashes": {
            "corpus": _corpus_hash(chunks),
            "knowledge_map": sha256_path(REPO / "evaluation/v2/knowledge_map.json"),
            "basic": sha256_path(REPO / "evaluation/v2/basic.json"),
            "intermediate": sha256_path(REPO / "evaluation/v2/intermediate.json"),
            "challenge_lock": sha256_path(REPO / "evaluation/v2/challenge.sha256"),
            "pipeline_config": sha256_path(REPO / "config/pipeline.yaml"),
            "challenger_manifest": (
                sha256_path(challenger_manifest_path)
                if challenger_manifest_path is not None
                else None
            ),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "gpu_name": _gpu_name(),
        },
        "models": [
            {
                "id": configured[item].id,
                "model": configured[item].model,
                "revision": configured[item].revision,
                "dimensions": configured[item].dimensions,
                "dtype": configured[item].dtype,
                "registry": "challenger" if item in challenger_ids else "production",
                "query_prompt_name": getattr(configured[item], "query_prompt_name", None),
                "document_prompt_name": getattr(
                    configured[item], "document_prompt_name", None
                ),
                "trust_remote_code": bool(
                    getattr(configured[item], "trust_remote_code", False)
                ),
                "license": getattr(configured[item], "license", None),
            }
            for item in requested
        ],
        "settings": {
            "tier": args.tier,
            "split": args.split,
            "device": args.device,
            "artifact_root": str(args.artifact_root.resolve()),
            "candidate_manifest": (
                str(challenger_manifest_path)
                if challenger_manifest_path is not None
                else None
            ),
            "warmup": args.warmup,
            "timing_runs": args.timing_runs,
            "bootstrap_samples": args.bootstrap_samples,
            "seed": args.seed,
            "top_k": args.top_k,
        },
    }
    write_json(args.output_dir / "summary.json", summary)
    write_json(args.output_dir / "environment.json", manifest)
    (args.output_dir / "report.md").write_text(markdown_report(summary), encoding="utf-8")
    return 0 if successful else 1


def _gpu_name() -> str | None:
    try:
        import torch

        cuda = getattr(torch, "cuda", None)
        return cuda.get_device_name(0) if cuda is not None and cuda.is_available() else None
    except ImportError:
        return None


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except EvaluationV2Error as exc:
        print(f"data/configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
