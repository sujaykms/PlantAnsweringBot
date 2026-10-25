from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    router_model: str = "qwen/qwen-2.5-7b-instruct"
    extract_model: str = "openai/gpt-4.1-mini"
    answer_model: str = "anthropic/claude-sonnet-5.5"

    database_url: str = "postgresql://plant:plant@localhost:5433/plantdocs"
    analytics_database_url: str = (
        "postgresql://analytics_reader:analytics_reader@localhost:5433/plantdocs"
    )

    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 20
    top_k: int = 6
    min_rerank_score: float = -8.5


@lru_cache
def get_settings() -> Settings:
    return Settings()
