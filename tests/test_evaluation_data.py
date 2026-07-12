from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingest import chunk_document, discover_documents
from evaluation.eval_lib import (
    EVALUATION_ROOT,
    EvaluationDataError,
    evidence_group_ranks,
    load_cases,
    verify_heldout_lock,
)


def test_locked_heldout_and_required_robustness_cases_exist() -> None:
    digest = verify_heldout_lock()
    cases = load_cases(["dev", "heldout"])

    assert len(digest) == 64
    assert len(cases) >= 20
    assert any(case["category"] == "prompt-injection" for case in cases)
    assert any(case["category"] == "refusal" for case in cases)
    assert any(case["category"] == "robustness" for case in cases)
    assert any(case["history"] for case in cases)


def test_heldout_lock_fails_closed_after_mutation(tmp_path: Path) -> None:
    heldout = EVALUATION_ROOT / "heldout.json"
    lock = EVALUATION_ROOT / "heldout.sha256"
    (tmp_path / "heldout.json").write_bytes(heldout.read_bytes() + b"\n")
    (tmp_path / "heldout.sha256").write_bytes(lock.read_bytes())

    with pytest.raises(EvaluationDataError, match="heldout.json changed"):
        verify_heldout_lock(tmp_path)


def test_every_factual_qrel_matches_the_current_deterministic_corpus(pipeline) -> None:
    chunks = [
        {
            "source": chunk.source,
            "chunkIndex": chunk.index,
            "content": chunk.content,
        }
        for document in discover_documents(Path("corpus"))
        for chunk in chunk_document(document, pipeline)
    ]

    for case in load_cases(["dev", "heldout"]):
        ranks = evidence_group_ranks(case["required_evidence"], chunks)
        assert all(rank is not None for rank in ranks), json.dumps(
            {"case": case["id"], "ranks": ranks}
        )
