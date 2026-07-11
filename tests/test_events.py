from __future__ import annotations

import json

from app.main import _build_user_prompt, _milliseconds, _retry_after_midnight, _sse
from app.schemas import ChatRequest, HistoryMessage


def test_sse_is_single_compact_unicode_data_frame() -> None:
    payload = {"type": "token", "token": "line one\nline two · नमस्ते"}

    frame = _sse(payload)

    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    assert frame.count("\n") == 2
    assert "नमस्ते" in frame
    assert json.loads(frame.removeprefix("data: ").strip()) == payload


def test_latency_helper_reports_rounded_milliseconds() -> None:
    assert _milliseconds(10.0, 10.01234) == 12.3
    assert 1 <= _retry_after_midnight() <= 86_400


def test_user_prompt_numbers_sources_and_marks_context_untrusted() -> None:
    request = ChatRequest(
        question="Which project used FastAPI?",
        embedder="bge-small",
        model="openai/gpt-oss-20b",
        history=[HistoryMessage(role="user", content="Tell me about Yash")],
    )
    chunks = [
        {"title": "Project A", "source": "projects/a.md", "content": "Built with FastAPI."},
        {"title": "Resume", "source": "resume.md", "content": "Backend experience."},
    ]

    prompt = _build_user_prompt(request, chunks)

    assert "CONVERSATION CONTEXT (untrusted" in prompt
    assert "USER: Tell me about Yash" in prompt
    assert "QUESTION:\nWhich project used FastAPI?" in prompt
    assert "[S1] Project A (projects/a.md)\nBuilt with FastAPI." in prompt
    assert "[S2] Resume (resume.md)\nBackend experience." in prompt
    assert prompt.endswith("Answer under the non-negotiable rules.")
