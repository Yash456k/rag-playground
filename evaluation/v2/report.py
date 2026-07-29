# ruff: noqa: E501
from __future__ import annotations

from typing import Any


def _number(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Portfolio RAG embedding evaluation V2",
        "",
        "Dev and challenge results are reported independently. The pooled `all` view is informational only and must not be used as a release gate.",
        "This is a locked query-form, compositional, and adversarial generalization benchmark; it is not a pristine fact-family holdout because direct corpus facts overlap training.",
        "",
        "## Quality",
        "",
        "| Model | Split | Tier | Total | Answerable | nDCG@5 | Required recall@5 | MRR@5 | Hard-negative hit@5 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    quality_rows: list[tuple[float, str]] = []
    for model in summary.get("models", []):
        if model.get("status") != "ok":
            continue
        for key, result in model["quality"].items():
            split, tier = key.split("/", 1)
            metrics = result["metrics"]
            quality_rows.append(
                (
                    metrics.get("ndcg@5", 0),
                    f"| {model['id']} | {split} | {tier} | {result['query_count']} | "
                    f"{result['answerable_query_count']} | "
                    f"{_number(metrics.get('ndcg@5'))} | {_number(metrics.get('required_recall@5'))} | "
                    f"{_number(metrics.get('mrr@5'))} | {_number(metrics.get('hard_negative_hit_rate@5'))} |",
                )
            )
    lines.extend(row for _, row in sorted(quality_rows, reverse=True))
    lines += [
        "",
        "## Speed",
        "",
        "| Model | Device / dtype | Load + warmup s | Corpus encode s | Query loop s | Encode mean/p50/p95 ms | Retrieval mean/p50/p95 ms | E2E mean/p50/p95 ms | QPS | Peak alloc/reserved CUDA MiB | RSS before/warmup/corpus MiB |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in summary.get("models", []):
        if model.get("status") != "ok":
            continue
        timing = model["timing"]
        lines.append(
            f"| {model['id']} | {timing['device']} / {timing['effective_dtype']} | "
            f"{_number(timing['load_warmup_seconds'])} | {_number(timing['corpus_encoding_index_seconds'])} | "
            f"{_number(timing['query_benchmark_seconds'])} | "
            f"{_number(timing['encode']['mean_ms'])}/{_number(timing['encode']['p50_ms'])}/{_number(timing['encode']['p95_ms'])} | "
            f"{_number(timing['retrieval']['mean_ms'])}/{_number(timing['retrieval']['p50_ms'])}/{_number(timing['retrieval']['p95_ms'])} | "
            f"{_number(timing['end_to_end']['mean_ms'])}/{_number(timing['end_to_end']['p50_ms'])}/{_number(timing['end_to_end']['p95_ms'])} | "
            f"{_number(timing['end_to_end_throughput_qps'])} | "
            f"{_number(timing['peak_allocated_cuda_mib'], 1)}/{_number(timing['peak_reserved_cuda_mib'], 1)} |"
            f"{_number(timing['rss_mib']['before_load'], 1)}/"
            f"{_number(timing['rss_mib']['after_warmup'], 1)}/"
            f"{_number(timing['rss_mib']['after_corpus_encoding'], 1)} |"
        )
    failures = [model for model in summary.get("models", []) if model.get("status") == "failed"]
    if failures:
        lines += ["", "## Model failures", ""]
        lines.extend(
            f"- `{model['id']}`: {model['error']['type']}: {model['error']['message']}"
            for model in failures
        )
    lines += ["", "## Diagnostics and confidence intervals", ""]
    for model in summary.get("models", []):
        if model.get("status") != "ok":
            continue
        lines.append(f"### {model['id']}")
        lines.append("")
        for key in sorted(model["quality"]):
            item = model["quality"][key]
            threshold = item["threshold_diagnostics"]
            configured = item["configured_threshold_diagnostics"]
            ci = item["confidence_intervals"]
            if not threshold.get("available", True):
                threshold_text = threshold["reason"]
            else:
                threshold_text = (
                    f"dev-calibrated threshold {_number(threshold['threshold'])} from "
                    f"{threshold['calibrated_on']}, balanced accuracy "
                    f"{_number(threshold['balanced_accuracy'])}, false-answer rate "
                    f"{_number(threshold['false_answer_rate'])}, false-refusal rate "
                    f"{_number(threshold['false_refusal_rate'])}"
                )
            configured_text = (
                f"configured threshold {_number(configured['threshold'])}, balanced accuracy "
                f"{_number(configured['balanced_accuracy'])}, false-answer rate "
                f"{_number(configured['false_answer_rate'])}, false-refusal rate "
                f"{_number(configured['false_refusal_rate'])}"
            )
            lines.append(
                f"- `{key}`: {configured_text}; {threshold_text}; nDCG@5 CI "
                f"[{_number(ci['ndcg@5']['low'])}, {_number(ci['ndcg@5']['high'])}], "
                f"recall@5 CI [{_number(ci['required_recall@5']['low'])}, "
                f"{_number(ci['required_recall@5']['high'])}]."
            )
        lines += ["", "Worst slices/failures:", ""]
        for failure in model.get("failures", [])[:20]:
            lines.append(
                f"- `{failure['id']}` ({failure['split']}/{failure['tier']}/{failure['category']}): "
                f"nDCG@5 {_number(failure['metrics']['ndcg@5'])}, recall@5 "
                f"{_number(failure['metrics']['required_recall@5'])}."
            )
        if model.get("threshold_errors"):
            lines += ["", "Highest-scoring unanswerable/refusal cases:", ""]
            for failure in model["threshold_errors"][:10]:
                lines.append(
                    f"- `{failure['id']}` ({failure['split']}/{failure['tier']}/"
                    f"{failure['category']}): top score {_number(failure['top_score'])}."
                )
        lines.append("")
    lines += ["## Paired comparisons", ""]
    if summary.get("paired_comparisons"):
        for name, views in summary["paired_comparisons"].items():
            for view, comparison in views.items():
                ndcg = comparison["metrics"]["ndcg@5"]
                recall = comparison["metrics"]["required_recall@5"]
                label = " (informational only)" if comparison.get("informational_only") else ""
                lines.append(
                    f"- `{name}` `{view}`{label} ({comparison['query_count']} shared answerable queries, tolerance "
                    f"{comparison['tie_tolerance']}): nDCG@5 W/T/L "
                    f"{ndcg['wins']}/{ndcg['ties']}/{ndcg['losses']} (Δ {_number(ndcg['mean_delta'])}); "
                    f"recall@5 W/T/L {recall['wins']}/{recall['ties']}/{recall['losses']} "
                    f"(Δ {_number(recall['mean_delta'])})."
                )
    else:
        lines.append("No successful model pair was available.")
    lines += [
        "",
        "## Leakage rule",
        "",
        "The challenge set is blind only until it is inspected. After anyone reviews its questions or results, it becomes regression data; create a new locked challenge set for future unbiased selection.",
        "",
    ]
    return "\n".join(lines)
