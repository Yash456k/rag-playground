from __future__ import annotations

import pytest

from evaluation.eval_lib import EvaluationDataError
from scripts.compare_chunking_runs import (
    _rank_changes,
    _validate_summaries,
    align_rows,
    clustered_delta_ci,
    exact_sign_test,
    fact_clusters,
    paired_metric_summary,
    source_gate_status,
)


def _summary(
    mode: str,
    protocol: dict | None = None,
    routes: dict | None = None,
) -> dict:
    summary = {
        "split": "dev",
        "chunkingMode": mode,
        "caseIds": ["case-a"],
        "topK": 5,
        "runtime": {
            "model-a": {
                "model": "model/path",
                "revision": "a" * 40,
                "dimensions": 384,
                "device": "cpu",
            }
        },
    }
    if protocol is not None:
        summary["retrievalProtocol"] = protocol
    if routes is not None:
        summary["embeddingRoutes"] = routes
    return summary


def test_paired_metric_summary_is_deterministic_and_directional() -> None:
    automatic = [0.0, 1.0, 0.0]
    manual = [1.0, 0.0, 0.0]

    first = paired_metric_summary(
        automatic,
        manual,
        direction="higher",
        bootstrap_samples=500,
        seed=7,
    )
    second = paired_metric_summary(
        automatic,
        manual,
        direction="higher",
        bootstrap_samples=500,
        seed=7,
    )

    assert first == second
    assert first["automatic"] == pytest.approx(1 / 3)
    assert first["manual"] == pytest.approx(1 / 3)
    assert first["delta"] == 0.0
    assert first["wins"] == 1
    assert first["ties"] == 1
    assert first["losses"] == 1
    assert first["signTestPValue"] == 1.0
    assert first["deltaCi95"][0] <= 0 <= first["deltaCi95"][1]


def test_exact_sign_test_ignores_ties() -> None:
    assert exact_sign_test(5, 0) == pytest.approx(0.0625)
    assert exact_sign_test(3, 3) == 1.0
    assert exact_sign_test(0, 0) is None


def test_summary_parity_discloses_missing_protocol_metadata() -> None:
    parity = _validate_summaries(_summary("auto"), _summary("manual"), split="dev")

    assert parity["retrievalProtocolArtifactVerified"] is False
    assert parity["retrievalProtocol"] is None
    assert parity["embeddingRouteProtocolArtifactVerified"] is False


def test_summary_parity_accepts_equal_serialized_protocols() -> None:
    protocol = {"topK": 5, "candidateDepth": 12, "selector": {"global": 0.6}}
    parity = _validate_summaries(
        _summary("auto", protocol),
        _summary("manual", protocol),
        split="dev",
    )

    assert parity["retrievalProtocolArtifactVerified"] is True
    assert parity["retrievalProtocol"] == protocol


def test_summary_parity_rejects_mismatched_serialized_protocols() -> None:
    with pytest.raises(EvaluationDataError, match="different retrieval protocols"):
        _validate_summaries(
            _summary("auto", {"candidateDepth": 12}),
            _summary("manual", {"candidateDepth": 10}),
            split="dev",
        )


def test_summary_parity_rejects_mismatched_embedding_route_settings() -> None:
    with pytest.raises(EvaluationDataError, match="different embedding routes"):
        _validate_summaries(
            _summary("auto", routes={"model-a": {"queryPrefix": "query: "}}),
            _summary("manual", routes={"model-a": {"queryPrefix": ""}}),
            split="dev",
        )


def test_align_rows_rejects_unpaired_inputs() -> None:
    automatic = [{"caseId": "a", "embedder": "model-a"}]
    manual = [{"caseId": "b", "embedder": "model-a"}]

    with pytest.raises(EvaluationDataError, match="same case/embedder pairs"):
        align_rows(automatic, manual)


def test_align_rows_rejects_split_mismatch() -> None:
    automatic = [{"caseId": "a", "embedder": "model-a", "split": "dev"}]
    manual = [{"caseId": "a", "embedder": "model-a", "split": "heldout"}]

    with pytest.raises(EvaluationDataError, match="split"):
        align_rows(automatic, manual)


def test_fact_cluster_bootstrap_keeps_shared_facts_together() -> None:
    clusters = fact_clusters(
        {
            "a": {"fact_ids": ["shared"]},
            "b": {"fact_ids": ["shared", "other"]},
            "c": {"fact_ids": ["independent"]},
        }
    )

    assert clusters == [["a", "b"], ["c"]]
    assert clusters is not None
    first = clustered_delta_ci(
        {"a": 1.0, "b": 1.0, "c": -1.0},
        clusters,
        bootstrap_samples=1000,
        seed=9,
    )
    second = clustered_delta_ci(
        {"a": 1.0, "b": 1.0, "c": -1.0},
        clusters,
        bootstrap_samples=1000,
        seed=9,
    )
    assert first == second
    assert first[0] <= 1 / 3 <= first[1]


def test_rank_changes_separate_coverage_from_within_top_five_movement() -> None:
    automatic = [
        {
            "caseId": "case-a",
            "category": "projects",
            "embedder": "model-a",
            "metrics": {"evidenceGroupRanks": [2, None, 4]},
        }
    ]
    manual = [
        {
            "caseId": "case-a",
            "category": "projects",
            "embedder": "model-a",
            "metrics": {"evidenceGroupRanks": [3, 5, None]},
        }
    ]

    changes = _rank_changes(
        align_rows(automatic, manual),
        {"case-a": ["first", "second", "third"]},
    )

    assert len(changes["coverageGains"]) == 1
    assert changes["coverageGains"][0]["evidenceLabel"] == "second"
    assert len(changes["coverageLosses"]) == 1
    assert changes["coverageLosses"][0]["evidenceLabel"] == "third"
    assert len(changes["rankRegressionsWithinTop5"]) == 1
    assert changes["rankRegressionsWithinTop5"][0]["automaticRank"] == 2
    assert changes["rankRegressionsWithinTop5"][0]["manualRank"] == 3


def test_source_gate_status_preserves_near_misses_without_enforcing_them() -> None:
    status = source_gate_status(
        {
            "gatesEnforced": False,
            "passed": False,
            "embedders": {
                "model-a": {"passed": True, "gateFailures": []},
                "model-b": {
                    "passed": False,
                    "gateFailures": [
                        {"gate": "minRecallAt5", "actual": 0.9444444, "required": 0.95}
                    ],
                },
            },
        }
    )

    assert status["gatesEnforcedDuringRun"] is False
    assert status["passed"] is False
    assert status["passingRoutes"] == 1
    assert status["routeCount"] == 2
    assert status["byEmbedder"]["model-b"]["gateFailures"] == [
        {"gate": "minRecallAt5", "actual": 0.944444, "required": 0.95}
    ]
