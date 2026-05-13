from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Knowledge Assistant"
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
