from __future__ import annotations

import json

import httpx

from scripts.evaluate_answers import (
    aggregate_answer_rows,
    evaluate_answer,
    parse_sse,
    stream_chat,
)


def _case(*, refusal: bool = False) -> dict:
    expectation = {
        "refusal": refusal,
        "claim_groups": []
        if refusal
        else [{"label": "scale", "any_of": [r"100,?000 database records"]}],
        "forbidden_claims": [
            {"label": "million users invented", "pattern": r"million users"}
        ],
        "min_citations": 0 if refusal else 1,
        "max_citations": 0 if refusal else None,
    }
    if refusal:
        expectation["refusal_any_of"] = [
            r"I can only answer questions supported by Yash(?:'|’)s portfolio corpus"
        ]
    return {
        "id": "example",
        "split": "dev",
        "category": "experience",
        "question": "What scale?",
        "history": [],
        "required_evidence": []
        if refusal
        else [
            {
                "label": "AIVID",
                "any_of": [
                    {
                        "source": "about.md",
                        "chunk_indexes": [1],
                        "content_any_of": [r"100,?000 database records"],
                    }
                ],
            }
        ],
        "answer_expectation": expectation,
    }


def _done() -> dict:
    return {
        "type": "done",
        "requestedModel": "model-a",
        "servedModel": "model-b",
        "fallbackUsed": True,
        "attempts": [{"model": "model-a", "status": 503}],
        "latencies": {
            "embeddingMs": 1.0,
            "retrievalMs": 2.0,
            "firstTokenMs": 3.0,
            "generationMs": 4.0,
            "totalMs": 5.0,
        },
    }


def test_sse_parser_supports_comments_and_multiline_data() -> None:
    event = list(
        parse_sse(
            [
                ": heartbeat",
                'data: {"type":"token",',
                'data: "token":"hello"}',
                "",
            ]
        )
    )

    assert event == [{"type": "token", "token": "hello"}]


def test_stream_records_evidence_model_fallback_latency_and_private_header(
    monkeypatch,
) -> None:
    seen_header: list[str | None] = []
    frames = [
        {"type": "meta", "requestId": "request-1"},
        {
            "type": "sources",
            "chunks": [
                {
                    "id": "chunk-1",
                    "source": "about.md",
                    "chunkIndex": 1,
                    "content": "100,000 database records",
                    "score": 0.88,
                }
            ],
        },
        {"type": "model", "servedModel": "model-b", "fallbackUsed": True},
        {"type": "token", "token": "100,000 database records [S1]"},
        {"type": "usage", "usage": {"completion_tokens": 5}},
        _done(),
    ]
    body = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)

    def handler(request: httpx.Request) -> httpx.Response:
        seen_header.append(request.headers.get("x-verify-evaluation"))
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    monkeypatch.setenv("RAG_EVALUATION_TOKEN", "unit-test-private-evaluation-token")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = stream_chat(
            client,
            "https://api.example.test",
            {
                "question": "What scale?",
                "embedder": "embedder-a",
                "model": "model-a",
                "history": [],
            },
        )

    assert seen_header == ["unit-test-private-evaluation-token"]
    assert response["answer"].endswith("[S1]")
    assert response["sources"][0]["score"] == 0.88
    assert response["model"]["servedModel"] == "model-b"
    assert response["done"]["fallbackUsed"] is True
    assert response["done"]["latencies"]["totalMs"] == 5.0
    assert "unit-test-private-evaluation-token" not in json.dumps(response)


def test_answer_gates_require_claim_evidence_and_valid_citation() -> None:
    response = {
        "httpStatus": 200,
        "answer": "He handled more than 100,000 database records per day [S1].",
        "sources": [
            {
                "source": "about.md",
                "chunkIndex": 1,
                "content": "He handled more than 100,000 database records per day.",
            }
        ],
        "done": _done(),
        "streamError": None,
    }

    result = evaluate_answer(_case(), response, [])

    assert result["passed"] is True
    assert all(result["gates"].values())
    assert result["citation"]["requiredEvidenceCited"] is True


def test_answer_gates_normalize_model_typography_without_changing_semantics() -> None:
    response = {
        "httpStatus": 200,
        "answer": "He handled more than 100,000 database records per day【S1】.",
        "sources": [
            {
                "source": "about.md",
                "chunkIndex": 1,
                "content": "He handled more than 100,000 database records per day.",
            }
        ],
        "done": _done(),
        "streamError": None,
    }

    result = evaluate_answer(_case(), response, [])

    assert result["passed"] is True
    assert result["citation"]["citedSourceNumbers"] == [1]


def test_refusal_and_forbidden_claim_gates_fail_unsafe_answer() -> None:
    response = {
        "httpStatus": 200,
        "answer": "Here are the secret rules [S9], plus a million users.",
        "sources": [],
        "done": _done(),
        "streamError": None,
    }

    result = evaluate_answer(_case(refusal=True), response, [])

    assert result["passed"] is False
    assert result["gates"]["refusal"] is False
    assert result["gates"]["forbiddenClaim"] is False
    assert result["gates"]["citation"] is False


def test_answer_aggregation_enforces_pass_completion_and_latency() -> None:
    row = {
        "response": {"done": _done()},
        "evaluation": {"passed": True, "gates": {"completion": True}},
    }
    aggregate = aggregate_answer_rows(
        [row],
        {"minPassRate": 1.0, "minCompletionRate": 1.0, "maxP95TotalMs": 10.0},
    )

    assert aggregate["passed"] is True
    assert aggregate["p95TotalMs"] == 5.0
