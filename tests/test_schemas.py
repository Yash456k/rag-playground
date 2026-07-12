from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, HistoryMessage

BASE = {"embedder": "bge-small", "model": "openai/gpt-oss-20b"}


def test_question_is_normalized_and_exact_cap_is_accepted() -> None:
    normalized = ChatRequest(question="  What\n did   Yash build?  ", **BASE)
    capped = ChatRequest(question="q" * 500, **BASE)

    assert normalized.question == "What did Yash build?"
    assert len(capped.question) == 500
    assert normalized.top_k == 7
    assert normalized.use_history is True


def test_public_optimization_controls_use_bounded_aliases() -> None:
    request = ChatRequest(question="What did Yash build?", topK=3, useHistory=False, **BASE)

    assert request.top_k == 3
    assert request.use_history is False

    assert ChatRequest(question="What did Yash build?", topK=7, **BASE).top_k == 7

    with pytest.raises(ValidationError):
        ChatRequest(question="What did Yash build?", topK=12, **BASE)


@pytest.mark.parametrize(
    "override",
    [
        {"question": "q" * 501},
        {"question": " \n\t "},
        {"question": "ok", "embedder": "e" * 81},
        {"question": "ok", "model": "m" * 101},
    ],
)
def test_request_field_caps_reject_oversized_or_empty_values(override: dict) -> None:
    values = {"question": "ok", **BASE, **override}
    with pytest.raises(ValidationError):
        ChatRequest(**values)


def test_history_count_and_content_caps() -> None:
    six = [HistoryMessage(role="user", content="h" * 700) for _ in range(6)]
    assert len(ChatRequest(question="ok", history=six, **BASE).history) == 6

    with pytest.raises(ValidationError):
        ChatRequest(
            question="ok",
            history=[*six, HistoryMessage(role="assistant", content="extra")],
            **BASE,
        )
    with pytest.raises(ValidationError):
        HistoryMessage(role="assistant", content="h" * 701)


def test_history_content_cannot_become_empty_after_trimming() -> None:
    with pytest.raises(ValidationError):
        HistoryMessage(role="user", content=" \n\t ")
