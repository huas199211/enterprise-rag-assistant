from typing import Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    rerank: bool | None = None
    min_score: float | None = Field(default=None, ge=0, le=1)


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str = Field(pattern="^(up|down)$")
    comment: str = ""


class ConfigUpdate(BaseModel):
    chunk_size: int | None = Field(default=None, ge=100, le=3000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=800)
    top_k: int | None = Field(default=None, ge=1, le=20)
    rerank: bool | None = None
    min_score: float | None = Field(default=None, ge=0, le=1)
    llm_provider: str | None = None
    chat_model: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = Field(default=None, ge=64, le=4096)

    def clean(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}
