"""Application configuration via Pydantic Settings.

Loads from .env file and environment variables.
All settings are validated at startup.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """WorldRAG application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "worldrag"

    # --- Redis ---
    redis_url: str = "redis://:worldrag@localhost:6379"

    # --- PostgreSQL ---
    postgres_uri: str = "postgresql://worldrag:worldrag@localhost:5432/worldrag"

    # --- LLM Providers ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # --- LangExtract ---
    langextract_model: str = "gemini-2.5-flash"
    langextract_passes: int = 2
    langextract_max_workers: int = 20
    langextract_batch_chapters: int = 10

    # --- Instructor (reconciliation, classification) ---
    llm_reconciliation: str = "gemini:gemini-2.5-flash"
    llm_classification: str = "gemini:gemini-2.5-flash"
    llm_dedup: str = "gemini:gemini-2.5-flash"
    llm_cypher: str = "gemini:gemini-2.5-flash"
    use_batch_api: bool = True

    # --- User-facing ---
    llm_chat: str = "gemini:gemini-2.5-flash"

    # --- Embeddings & Reranking ---
    embedding_provider: str = "local"  # "local" (BGE-M3, free) or "voyage" (API)
    embedding_model: str = "BAAI/bge-m3"  # HuggingFace model ID for local provider
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3.5"
    cohere_api_key: str = ""

    # --- LangFuse ---
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # --- Authentication ---
    api_key: str = ""  # WORLDRAG_API_KEY — empty = dev mode (no auth)
    admin_api_key: str = ""  # WORLDRAG_ADMIN_API_KEY — empty = dev mode

    # --- App ---
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    log_level: str = "INFO"
    log_format: str = "json"
    cost_ceiling_per_chapter: float = 0.50
    cost_ceiling_per_book: float = 50.00

    # --- Task Queue (arq) ---
    arq_max_jobs: int = 5
    arq_job_timeout: int = 3600  # 1 hour per job (full book extraction)
    arq_keep_result: int = 86400  # keep job results for 24h

    # --- Derived ---
    debug: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    def parse_llm_spec(self, spec: str) -> tuple[str, str]:
        """Parse 'provider:model' spec into (provider, model) tuple."""
        if ":" not in spec:
            return ("openai", spec)
        provider, model = spec.split(":", 1)
        return (provider, model)


settings = Settings()
