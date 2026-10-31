from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = "sk-not-set"
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    chunk_size: int = 500
    chunk_overlap: int = 80
    top_k: int = 4
    prompt_version: str = "rag-answer-v1"
    chroma_path: str = "./data/chroma"
    corpus_path: str = "./corpus"
    collection_name: str = "ai_eng_lab"

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600
    semantic_cache_threshold: float = 0.92
    cache_enabled: bool = True

    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"
    langfuse_host: str = "http://localhost:3000"
    langfuse_enabled: bool = True

    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
