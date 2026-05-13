from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "企业知识库智能助手"
    database_path: str = "storage/app_nojournal.sqlite3"
    database_url: str = "postgresql+psycopg://rag:rag_password@127.0.0.1:5432/rag"
    upload_dir: str = "uploads"
    vector_store_path: str = "storage/vector_store.json"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "enterprise_knowledge_bge_m3_chunks"

    llm_provider: str = "local"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    chat_model: str = "gpt-4.1-mini"
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimensions: int = 1024

    default_chunk_size: int = 800
    default_chunk_overlap: int = 120
    default_top_k: int = 5
    default_rerank: bool = False
    default_min_score: float = 0.18

    vector_candidate_multiplier: int = 4
    hybrid_vector_weight: float = 0.7
    hybrid_bm25_weight: float = 0.3
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    rerank_original_score_weight: float = 0.7
    rerank_term_coverage_weight: float = 0.3

    local_answer_min_score: float = 0.08
    local_answer_relative_score: float = 0.55
    local_answer_max_contexts: int = 3
    local_answer_snippet_length: int = 260
    conversation_history_limit: int = 12
    conversation_title_length: int = 40
    error_message_max_length: int = 2000
    dedupe_key_length: int = 500

    llm_timeout_seconds: int = 60
    llm_temperature: float = 0.2
    embedding_timeout_seconds: int = 60
    local_no_proxy_hosts: str = "127.0.0.1,localhost,::1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
