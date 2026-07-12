from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=700)

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("history content is empty")
        return clean


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    question: str = Field(min_length=2, max_length=500)
    embedder: str = Field(min_length=2, max_length=80)
    model: str = Field(min_length=2, max_length=100)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=6)
    top_k: Literal[3, 5, 7] = Field(default=3, alias="topK")
    use_history: bool = Field(default=True, alias="useHistory")

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        clean = " ".join(value.split())
        if len(clean) < 2:
            raise ValueError("question is empty")
        return clean
