from __future__ import annotations

import pytest

from evaluation.eval_lib import EvaluationDataError
from scripts.compare_answer_runs import (
    _quality_exclusion_reason,
    align_answer_rows,
    provider_failure_reason,
    summarize_answer_pairs,
)


def _row(
    case_id: str,
    *,
    passed: bool,
    completion: bool = True,
    stream_error: str | None = None,
    claims: tuple[bool, ...] = (True,),
) -> dict:
    return {
        "caseId": case_id,
        "category": "test",
        "run": 1,
        "request": {
            "question": f"question-{case_id}",
            "embedder": "embedder",
            "model": "model",
        },
        "response": {
            "httpStatus": 200,
            "httpError": None,
            "streamError": stream_error,
            "done": {"latencies": {"totalMs": 100.0}},
            "model": {
                "requestedModel": "model",
                "servedModel": "model",
                "fallbackUsed": False,
            },
            "usage": [{"total_tokens": 100, "cost": 0.001}],
        },
        "evaluation": {
            "passed": passed,
            "gates": {
                "completion": completion,
                "groundedClaim": passed,
                "refusal": True,
                "forbiddenClaim": True,
                "citation": passed,
            },
            "claimGroups": [
                {"label": f"claim-{index}", "matched": matched}
                for index, matched in enumerate(claims)
            ],
            "evidenceGroupRanks": [1],
            "citation": {
                "allReferencesValid": True,
                "evidenceGroupCitationSupport": [passed],
            },
        },
    }


def test_provider_failures_are_not_quality_outcomes() -> None:
    row = _row("a", passed=False, stream_error="provider_unavailable")

    assert provider_failure_reason(row) == "stream-error"


def test_answer_alignment_rejects_missing_pairs() -> None:
    with pytest.raises(EvaluationDataError, match="same case/run/model pairs"):
        align_answer_rows([_row("a", passed=True)], [_row("b", passed=True)])


def test_answer_alignment_rejects_request_payload_mismatch() -> None:
    automatic = _row("a", passed=True)
    manual = _row("a", passed=True)
    manual["request"]["history"] = [{"role": "user", "content": "different"}]

    with pytest.raises(EvaluationDataError, match="request payload"):
        align_answer_rows([automatic], [manual])


def test_completed_local_refusal_is_a_quality_outcome() -> None:
    row = _row("a", passed=True)
    row["response"]["model"] = None
    row["response"]["done"]["localRefusal"] = True

    assert _quality_exclusion_reason(row) is None


def test_answer_summary_excludes_failures_and_counts_pass_changes() -> None:
    automatic = [
        _row("a", passed=False, claims=(True, False)),
        _row("b", passed=True),
        _row("c", passed=False, stream_error="provider_unavailable"),
    ]
    manual = [
        _row("a", passed=True, claims=(True, True)),
        _row("b", passed=True),
        _row("c", passed=True),
    ]

    summary = summarize_answer_pairs(
        align_answer_rows(automatic, manual),
        bootstrap_samples=1000,
        seed=7,
    )

    assert summary["sample"]["alignedPairs"] == 3
    assert summary["sample"]["qualityEligiblePairs"] == 2
    assert summary["sample"]["providerExcludedPairs"] == 1
    assert summary["qualityChanges"]["passGains"] == [{"caseId": "a", "category": "test", "run": 1}]
    assert summary["qualityChanges"]["passLosses"] == []
    assert summary["metrics"]["qualityPassRate"]["automatic"] == 0.5
    assert summary["metrics"]["qualityPassRate"]["manual"] == 1.0
    assert summary["metrics"]["claimCoverage"]["delta"] == 0.25
