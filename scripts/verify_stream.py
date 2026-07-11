from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify one live RAG SSE stream")
    parser.add_argument("--url", required=True)
    parser.add_argument("--embedder", default="bge-small")
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument("--question", default="What projects has Yash built?")
    parser.add_argument("--force-fallback", action="store_true")
    args = parser.parse_args()

    headers = {"Accept": "text/event-stream"}
    if args.force_fallback:
        token = os.environ.get("VERIFY_FALLBACK_TOKEN")
        if not token:
            raise SystemExit("VERIFY_FALLBACK_TOKEN is required for --force-fallback")
        headers["X-Verify-Fallback"] = token

    event_types: Counter[str] = Counter()
    answer: list[str] = []
    sources: list[dict] = []
    done: dict | None = None
    error: dict | None = None
    endpoint = f"{args.url.rstrip('/')}/v1/chat"
    payload = {
        "question": args.question,
        "embedder": args.embedder,
        "model": args.model,
        "history": [],
    }

    with httpx.Client(timeout=180) as client:
        with client.stream("POST", endpoint, headers=headers, json=payload) as response:
            if response.status_code != 200:
                body = response.read().decode(errors="replace")[:500]
                print(json.dumps({"status": response.status_code, "body": body}))
                raise SystemExit(1)
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:].strip())
                event_types[event["type"]] += 1
                if event["type"] == "token":
                    answer.append(event["token"])
                elif event["type"] == "sources":
                    sources = event["chunks"]
                elif event["type"] == "done":
                    done = event
                elif event["type"] == "error":
                    error = event

    summary = {
        "status": 200,
        "embedder": args.embedder,
        "requestedModel": args.model,
        "eventTypes": dict(event_types),
        "sourceCount": len(sources),
        "topScore": sources[0]["score"] if sources else None,
        "answer": "".join(answer).strip(),
        "done": done,
        "error": error,
    }
    print(json.dumps(summary, ensure_ascii=False))
    if error or not done or event_types["token"] < 2:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(json.dumps({"transportError": type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1) from exc
