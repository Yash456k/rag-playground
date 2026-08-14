# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.eval_lib import EvaluationDataError, mean  # noqa: E402
from scripts.compare_chunking_runs import paired_metric_summary  # noqa: E402

Direction = Literal["higher", "lower", "descriptive"]
METRICS: dict[str, tuple[str, Direction]] = {
    "qualityPassRate": ("Contract pass rate", "higher"),
    "groundedClaimPassRate": ("Required-claim gate", "higher"),
    "refusalPassRate": ("Refusal gate", "higher"),
    "forbiddenClaimPassRate": ("Forbidden-claim gate", "higher"),
    "citationPassRate": ("Citation gate", "higher"),
    "claimCoverage": ("Required claim-group coverage", "higher"),
    "retrievalEvidenceCoverageAt3": ("Retrieved evidence-group coverage@3", "higher"),
    "citedEvidenceCoverage": ("Cited evidence-group coverage", "higher"),
    "validCitationReferences": ("Valid citation references", "higher"),
    "totalLatencyMs": ("Total latency (ms)", "descriptive"),
    "totalTokens": ("Total tokens", "descriptive"),
    "reportedCostUsd": ("Reported provider cost (USD)", "descriptive"),
}


def _key(row: dict[str, Any]) -> tuple[str, int, str, str]:
    request = row.get("request", {})
    return (
        str(row.get("caseId")),
        int(row.get("run", 0)),
        str(request.get("embedder")),
        str(request.get("model")),
    )


def align_answer_rows(
    automatic_rows: list[dict[str, Any]], manual_rows: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    def index(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str, str], dict[str, Any]]:
        result: dict[tuple[str, int, str, str], dict[str, Any]] = {}
        for row in rows:
            key = _key(row)
            if key in result:
                raise EvaluationDataError(f"Duplicate answer row for {key}")
            result[key] = row
        return result

    automatic = index(automatic_rows)
    manual = index(manual_rows)
    if automatic.keys() != manual.keys():
        raise EvaluationDataError("Answer runs must contain the same case/run/model pairs")
    pairs = [(automatic[key], manual[key]) for key in sorted(automatic)]
    for baseline, candidate in pairs:
        if baseline.get("category") != candidate.get("category"):
            raise EvaluationDataError("Paired answer rows disagree on category")
        if baseline.get("request") != candidate.get("request"):
            raise EvaluationDataError("Paired answer rows disagree on request payload")
    return pairs


def provider_failure_reason(row: dict[str, Any]) -> str | None:
    response = row.get("response", {})
    if response.get("httpStatus") != 200:
        return "http-status"
    if response.get("httpError"):
        return "http-error"
    if response.get("streamError"):
        return "stream-error"
    if not isinstance(response.get("done"), dict):
        return "missing-done"
    if not row.get("evaluation", {}).get("gates", {}).get("completion", False):
        return "incomplete"
    return None


def _quality_exclusion_reason(row: dict[str, Any]) -> str | None:
    failure = provider_failure_reason(row)
    if failure:
        return failure
    response_model = row.get("response", {}).get("model")
    if not isinstance(response_model, dict):
        done = row.get("response", {}).get("done") or {}
        if done.get("localRefusal") is True:
            return None
        return "missing-model-event"
    if response_model.get("fallbackUsed"):
        return "fallback-model"
    if response_model.get("requestedModel") != response_model.get("servedModel"):
        return "served-model-mismatch"
    return None


def _fraction(values: list[bool]) -> float | None:
    return None if not values else mean(float(value) for value in values)


def _row_metrics(row: dict[str, Any]) -> dict[str, float | None]:
    evaluation = row["evaluation"]
    gates = evaluation["gates"]
    claims = [bool(item["matched"]) for item in evaluation.get("claimGroups", [])]
    ranks = evaluation.get("evidenceGroupRanks", [])
    citation = evaluation.get("citation", {})
    citation_support = [bool(value) for value in citation.get("evidenceGroupCitationSupport", [])]
    response = row.get("response", {})
    done = response.get("done") or {}
    latency = done.get("latencies", {}).get("totalMs")
    usage = response.get("usage", [])
    return {
        "qualityPassRate": float(evaluation["passed"]),
        "groundedClaimPassRate": float(gates["groundedClaim"]),
        "refusalPassRate": float(gates["refusal"]),
        "forbiddenClaimPassRate": float(gates["forbiddenClaim"]),
        "citationPassRate": float(gates["citation"]),
        "claimCoverage": _fraction(claims),
        "retrievalEvidenceCoverageAt3": (
            None if not ranks else mean(float(rank is not None and rank <= 3) for rank in ranks)
        ),
        "citedEvidenceCoverage": _fraction(citation_support),
        "validCitationReferences": (
            None if "allReferencesValid" not in citation else float(citation["allReferencesValid"])
        ),
        "totalLatencyMs": None if latency is None else float(latency),
        "totalTokens": (
            None if not usage else float(sum(float(item.get("total_tokens", 0)) for item in usage))
        ),
        "reportedCostUsd": (
            None if not usage else float(sum(float(item.get("cost", 0.0)) for item in usage))
        ),
    }


def summarize_answer_pairs(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, Any]:
    if not pairs:
        raise EvaluationDataError("Cannot compare empty answer runs")
    eligible: list[tuple[dict[str, Any], dict[str, Any]]] = []
    exclusions: list[dict[str, Any]] = []
    for automatic, manual in pairs:
        automatic_reason = _quality_exclusion_reason(automatic)
        manual_reason = _quality_exclusion_reason(manual)
        if automatic_reason or manual_reason:
            exclusions.append(
                {
                    "caseId": automatic["caseId"],
                    "category": automatic["category"],
                    "run": automatic["run"],
                    "automaticReason": automatic_reason,
                    "manualReason": manual_reason,
                }
            )
        else:
            eligible.append((automatic, manual))

    enriched = [
        (automatic, manual, _row_metrics(automatic), _row_metrics(manual))
        for automatic, manual in eligible
    ]
    metric_summaries: dict[str, Any] = {}
    for metric, (_, direction) in METRICS.items():
        case_values: dict[str, tuple[list[float], list[float]]] = defaultdict(lambda: ([], []))
        for automatic, _, automatic_metrics, manual_metrics in enriched:
            automatic_value = automatic_metrics[metric]
            manual_value = manual_metrics[metric]
            if automatic_value is None or manual_value is None:
                continue
            case_values[automatic["caseId"]][0].append(automatic_value)
            case_values[automatic["caseId"]][1].append(manual_value)
        automatic_values = [
            mean(case_values[case_id][0])
            for case_id in sorted(case_values)
            if case_values[case_id][0]
        ]
        manual_values = [
            mean(case_values[case_id][1])
            for case_id in sorted(case_values)
            if case_values[case_id][1]
        ]
        metric_summaries[metric] = (
            None
            if not automatic_values
            else paired_metric_summary(
                automatic_values,
                manual_values,
                direction=direction,
                bootstrap_samples=bootstrap_samples,
                seed=seed + int(hashlib.sha256(metric.encode()).hexdigest()[:8], 16),
            )
        )

    gains: list[dict[str, Any]] = []
    losses: list[dict[str, Any]] = []
    for automatic, manual in eligible:
        change = {
            "caseId": automatic["caseId"],
            "category": automatic["category"],
            "run": automatic["run"],
        }
        if manual["evaluation"]["passed"] and not automatic["evaluation"]["passed"]:
            gains.append(change)
        elif automatic["evaluation"]["passed"] and not manual["evaluation"]["passed"]:
            losses.append(change)

    by_category: dict[str, Any] = {}
    for category in sorted({automatic["category"] for automatic, _ in eligible}):
        selected = [pair for pair in eligible if pair[0]["category"] == category]
        by_category[category] = {
            "pairCount": len(selected),
            "automaticPassRate": round(
                mean(float(pair[0]["evaluation"]["passed"]) for pair in selected), 6
            ),
            "manualPassRate": round(
                mean(float(pair[1]["evaluation"]["passed"]) for pair in selected), 6
            ),
        }

    return {
        "sample": {
            "alignedPairs": len(pairs),
            "qualityEligiblePairs": len(eligible),
            "qualityEligibleCases": len({pair[0]["caseId"] for pair in eligible}),
            "providerExcludedPairs": len(exclusions),
            "bootstrapUnit": "case (repeated runs averaged within case)",
            "bootstrapSamples": bootstrap_samples,
            "bootstrapSeed": seed,
        },
        "metrics": metric_summaries,
        "qualityChanges": {"passGains": gains, "passLosses": losses},
        "providerExclusions": exclusions,
        "byCategory": by_category,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise EvaluationDataError(f"Empty or malformed answer details: {path}")
    return rows


def _find_details(directory: Path) -> Path:
    matches = sorted(directory.glob("*.jsonl"))
    if len(matches) != 1:
        raise EvaluationDataError(f"{directory} must contain exactly one JSONL details file")
    return matches[0]


def _find_summary(directory: Path) -> Path:
    matches = sorted(directory.glob("*.json"))
    if len(matches) != 1:
        raise EvaluationDataError(f"{directory} must contain exactly one JSON summary file")
    return matches[0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_answer_dirs(
    *,
    automatic_dir: Path,
    manual_dir: Path,
    bootstrap_samples: int,
    seed: int,
    automatic_label: str | None = None,
    manual_label: str | None = None,
) -> dict[str, Any]:
    if automatic_dir.resolve() == manual_dir.resolve():
        raise EvaluationDataError("Automatic and manual answer directories must differ")
    automatic_summary_path = _find_summary(automatic_dir)
    manual_summary_path = _find_summary(manual_dir)
    automatic_summary = json.loads(automatic_summary_path.read_text(encoding="utf-8"))
    manual_summary = json.loads(manual_summary_path.read_text(encoding="utf-8"))
    for field in ("kind", "splits", "caseIds", "runs", "embedders", "models", "baseUrl"):
        if automatic_summary.get(field) != manual_summary.get(field):
            raise EvaluationDataError(f"Answer summaries disagree on {field}")
    automatic_path = _find_details(automatic_dir)
    manual_path = _find_details(manual_dir)
    automatic_rows = _load_jsonl(automatic_path)
    manual_rows = _load_jsonl(manual_path)
    pairs = align_answer_rows(automatic_rows, manual_rows)
    summary = summarize_answer_pairs(
        pairs,
        bootstrap_samples=bootstrap_samples,
        seed=seed,
    )
    return {
        "schemaVersion": 1,
        "kind": "paired-generated-answer-comparison",
        "lineage": {
            "automatic": {
                "artifact": automatic_label or str(automatic_path),
                "summarySha256": _sha256(automatic_summary_path),
                "detailsSha256": _sha256(automatic_path),
            },
            "manual": {
                "artifact": manual_label or str(manual_path),
                "summarySha256": _sha256(manual_summary_path),
                "detailsSha256": _sha256(manual_path),
            },
        },
        "configurationParity": {
            "caseRunModelPairsMatch": True,
            "summaryConfigurationMatch": True,
            "requestPayloadMatch": True,
            "providerFailuresExcludedFromQuality": True,
            "fallbacksExcludedFromQuality": True,
        },
        **summary,
    }


def _format_metric(metric: dict[str, Any] | None) -> str:
    if metric is None:
        return "not applicable"
    return f"{metric['automatic']:.3f} → {metric['manual']:.3f} ({metric['delta']:+.3f})"


def render_markdown(report: dict[str, Any], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "> Paired quality results include only requests completed by the requested model on both sides. Provider errors and fallbacks are reported separately and never scored as answer-quality losses.",
        "",
        "## Sample",
        "",
        f"- Aligned pairs: **{report['sample']['alignedPairs']}**",
        f"- Quality-eligible pairs: **{report['sample']['qualityEligiblePairs']}**",
        f"- Provider/fallback exclusions: **{report['sample']['providerExcludedPairs']}**",
        "",
        "## Paired quality table",
        "",
        "| Metric | Automatic → manual (delta) | 95% paired bootstrap CI | W/T/L |",
        "|---|---:|---:|---:|",
    ]
    for metric_name, (label, _) in METRICS.items():
        metric = report["metrics"][metric_name]
        if metric is None:
            lines.append(f"| {label} | not applicable | — | — |")
            continue
        ci = metric["deltaCi95"]
        wtl = (
            "descriptive"
            if metric["wins"] is None
            else f"{metric['wins']}/{metric['ties']}/{metric['losses']}"
        )
        lines.append(
            f"| {label} | {_format_metric(metric)} | [{ci[0]:+.3f}, {ci[1]:+.3f}] | {wtl} |"
        )
    lines.extend(
        [
            "",
            "## Contract pass changes",
            "",
            f"- Pass gains: **{len(report['qualityChanges']['passGains'])}**",
            f"- Pass losses: **{len(report['qualityChanges']['passLosses'])}**",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare paired generated-answer runs")
    parser.add_argument("--automatic-dir", type=Path, required=True)
    parser.add_argument("--manual-dir", type=Path, required=True)
    parser.add_argument("--automatic-label")
    parser.add_argument("--manual-label")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--title", default="Paired generated-answer evaluation")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bootstrap_samples < 1_000:
        raise SystemExit("--bootstrap-samples must be at least 1000")
    try:
        report = compare_answer_dirs(
            automatic_dir=args.automatic_dir,
            manual_dir=args.manual_dir,
            bootstrap_samples=args.bootstrap_samples,
            seed=args.seed,
            automatic_label=args.automatic_label,
            manual_label=args.manual_label,
        )
    except (EvaluationDataError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    args.output_markdown.write_text(render_markdown(report, args.title), encoding="utf-8")
    print(
        json.dumps(
            {
                "outputJson": str(args.output_json),
                "eligiblePairs": report["sample"]["qualityEligiblePairs"],
                "providerExclusions": report["sample"]["providerExcludedPairs"],
                "passGains": len(report["qualityChanges"]["passGains"]),
                "passLosses": len(report["qualityChanges"]["passLosses"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
