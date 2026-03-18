"""Application configuration via Pydantic Settings.

Loads from .env file and environment variables.
All settings are validated at startup.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from project root (two levels up from this file)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """WorldRAG application settings."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Neo4j ---
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "worldrag"

    # --- Redis ---
    redis_url: str = "redis://:worldrag@127.0.0.1:6379"

    # --- PostgreSQL ---
    postgres_uri: str = "postgresql://worldrag:worldrag@127.0.0.1:5432/worldrag"

    # --- LLM Providers ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # --- Extraction (V4 Instructor pipeline — default: DeepSeek V3 via OpenRouter) ---
    langextract_model: str = "openrouter:deepseek/deepseek-v3.2"
    langextract_passes: int = 2  # V3 legacy only
    langextract_max_workers: int = 20  # V3 legacy only
    langextract_batch_chapters: int = 10
    langextract_max_char_buffer: int = 2000

    # --- Instructor (reconciliation, classification) ---
    llm_reconciliation: str = "openrouter:deepseek/deepseek-v3.2"
    llm_classification: str = "openrouter:deepseek/deepseek-v3.2"
    llm_dedup: str = "openrouter:deepseek/deepseek-v3.2"
    llm_cypher: str = "openrouter:deepseek/deepseek-v3.2"
    use_batch_api: bool = True

    # --- User-facing ---
    llm_chat: str = "gemini:gemini-2.5-flash"
    llm_generation: str = "gemini:gemini-2.5-flash-lite"
    llm_auxiliary: str = "local:Qwen/Qwen3.5-4B"

    # --- OpenRouter (provider:model spec, e.g. "openrouter:deepseek/deepseek-v3.2") ---
    openrouter_api_key: str = ""  # OPENROUTER_API_KEY env var

    # --- Local (Ollama) ---
    local_llm_backend: str = "ollama"  # ollama|transformers
    ollama_base_url: str = "http://localhost:11434"

    # --- Embeddings (local sentence-transformers) ---
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cuda"
    embedding_batch_size: int = 64

    # --- Reranking (optional) ---
    cohere_api_key: str = ""

    # --- LangFuse ---
    langfuse_host: str = ""
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

    # --- V3 Extraction Pipeline ---
    use_v3_pipeline: bool = False  # V4 (Instructor) is now the default
    extraction_language: str = "en"
    ontology_version: str = "3.0.0"
    default_genre: str = "litrpg"

    # --- KG v2 (Graphiti) ---
    graphiti_enabled: bool = False  # Toggle Graphiti pipeline

    # --- Projects ---
    project_data_dir: str = "/data/projects"

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
