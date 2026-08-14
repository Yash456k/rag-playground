from __future__ import annotations

from collections.abc import Sequence


def build_retrieval_query(
    question: str,
    history: Sequence[tuple[str, str]] = (),
    *,
    use_history: bool = True,
) -> str:
    """Resolve short follow-ups using recent user text, never assistant output."""
    if not use_history:
        return question
    prior_user_messages = [content for role, content in history[-4:] if role == "user"]
    if not prior_user_messages:
        return question
    context = "\n".join(prior_user_messages)
    return f"Previous user context:\n{context}\n\nCurrent question:\n{question}"
