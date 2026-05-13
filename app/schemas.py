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
    vector_candidate_multiplier: int | None = Field(default=None, ge=1, le=20)
    hybrid_vector_weight: float | None = Field(default=None, ge=0, le=1)
    hybrid_bm25_weight: float | None = Field(default=None, ge=0, le=1)
    bm25_k1: float | None = Field(default=None, ge=0.1, le=5)
    bm25_b: float | None = Field(default=None, ge=0, le=1)
    rerank_original_score_weight: float | None = Field(default=None, ge=0, le=1)
    rerank_term_coverage_weight: float | None = Field(default=None, ge=0, le=1)
    local_answer_min_score: float | None = Field(default=None, ge=0, le=1)
    local_answer_relative_score: float | None = Field(default=None, ge=0, le=1)
    local_answer_max_contexts: int | None = Field(default=None, ge=1, le=20)
    local_answer_snippet_length: int | None = Field(default=None, ge=80, le=2000)
    conversation_history_limit: int | None = Field(default=None, ge=0, le=50)
    conversation_title_length: int | None = Field(default=None, ge=10, le=200)
    error_message_max_length: int | None = Field(default=None, ge=100, le=10000)
    dedupe_key_length: int | None = Field(default=None, ge=50, le=2000)
    llm_timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    embedding_timeout_seconds: int | None = Field(default=None, ge=5, le=300)

    def clean(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}
