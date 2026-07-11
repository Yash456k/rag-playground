from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import PipelineConfig

logger = logging.getLogger(__name__)


class GroqStreamError(RuntimeError):
    def __init__(self, message: str, attempts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.attempts = attempts


class GroqClient:
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, pipeline: PipelineConfig) -> None:
        self.api_key = api_key
        self.pipeline = pipeline
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(pipeline.generation.request_timeout_seconds),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )

    async def close(self) -> None:
        await self.client.aclose()

    def candidates(self, selected: str, force_failure: bool) -> list[str]:
        normal = [selected, *self.pipeline.fallback_order]
        candidates = list(dict.fromkeys(normal))
        if force_failure:
            return ["verification/forced-provider-error", *candidates]
        return candidates

    def _payload(self, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.pipeline.generation.temperature,
            "max_completion_tokens": self.pipeline.generation.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if model.startswith("openai/gpt-oss-"):
            payload.update({"reasoning_effort": "low", "include_reasoning": False})
        elif model.startswith("qwen/"):
            payload["reasoning_effort"] = "none"
        return payload

    async def stream(
        self,
        *,
        selected_model: str,
        system_prompt: str,
        user_prompt: str,
        force_failure: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        candidates = self.candidates(selected_model, force_failure)

        for candidate in candidates:
            emitted_content = False
            saw_done = False
            try:
                async with self.client.stream(
                    "POST",
                    self.endpoint,
                    headers=headers,
                    json=self._payload(candidate, system_prompt, user_prompt),
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode(errors="replace")[:300]
                        attempt = {
                            "model": candidate,
                            "status": response.status_code,
                            "reason": _provider_error_message(body),
                        }
                        attempts.append(attempt)
                        can_fallback = (
                            candidate.startswith("verification/")
                            or response.status_code in {403, 404, 408, 409, 429}
                            or response.status_code >= 500
                        )
                        if response.status_code == 401 or not can_fallback:
                            raise GroqStreamError("Groq rejected the request", attempts)
                        logger.warning("Groq model %s failed; trying fallback", candidate)
                        continue

                    stream_failed = False
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            saw_done = True
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError as exc:
                            attempts.append(
                                {"model": candidate, "status": 200, "reason": "malformed_sse"}
                            )
                            if emitted_content:
                                raise GroqStreamError(
                                    "Provider stream stopped after output began", attempts
                                ) from exc
                            stream_failed = True
                            break
                        if chunk.get("error"):
                            provider_error = chunk["error"]
                            reason = (
                                provider_error.get("message", "stream_error")
                                if isinstance(provider_error, dict)
                                else str(provider_error)
                            )
                            attempts.append({"model": candidate, "status": 200, "reason": reason})
                            if emitted_content:
                                raise GroqStreamError(
                                    "Provider stream stopped after output began", attempts
                                )
                            stream_failed = True
                            break
                        choices = chunk.get("choices") or []
                        if choices:
                            token = (choices[0].get("delta") or {}).get("content")
                            if token:
                                if not emitted_content:
                                    yield {
                                        "type": "model",
                                        "requestedModel": selected_model,
                                        "servedModel": candidate,
                                        "fallbackUsed": (
                                            candidate != selected_model or bool(attempts)
                                        ),
                                        "attempts": attempts,
                                    }
                                emitted_content = True
                                yield {"type": "token", "token": token}
                        if chunk.get("usage"):
                            yield {"type": "usage", "usage": chunk["usage"]}
                    if emitted_content and saw_done:
                        return
                    if emitted_content:
                        attempts.append(
                            {"model": candidate, "status": 200, "reason": "truncated_stream"}
                        )
                        raise GroqStreamError(
                            "Provider stream stopped after output began", attempts
                        )
                    if not stream_failed:
                        attempts.append(
                            {"model": candidate, "status": 200, "reason": "empty_stream"}
                        )
                    logger.warning("Groq model %s returned no answer; trying fallback", candidate)
                    continue
            except GroqStreamError:
                raise
            except httpx.TransportError as exc:
                attempts.append({"model": candidate, "status": None, "reason": type(exc).__name__})
                if emitted_content:
                    raise GroqStreamError(
                        "Provider stream stopped after output began", attempts
                    ) from exc
                logger.warning("Groq network failure for %s; trying fallback", candidate)
                continue
        raise GroqStreamError("No configured Groq model was available", attempts)


def _provider_error_message(body: str) -> str:
    try:
        payload = json.loads(body)
        message = payload.get("error", {}).get("message")
        return str(message)[:180] if message else "provider_error"
    except (json.JSONDecodeError, AttributeError):
        return "provider_error"
