"""Tests for new SOTA config fields."""

from app.config import Settings


class TestNewConfigFields:
    def test_defaults(self):
        # _env_file=None prevents loading the project .env so we test code defaults
        s = Settings(
            _env_file=None,
            neo4j_uri="bolt://x:7687",
            neo4j_password="x",
        )
        assert s.llm_generation == "gemini:gemini-2.5-flash-lite"
        assert s.llm_auxiliary == "local:Qwen/Qwen3.5-4B"
        assert s.openrouter_api_key == ""
        assert s.local_llm_backend == "ollama"
        assert s.ollama_base_url == "http://localhost:11434"

    def test_overrides(self):
        s = Settings(
            _env_file=None,
            neo4j_uri="bolt://x:7687",
            neo4j_password="x",
            llm_generation="openrouter:deepseek/deepseek-v3.2",
            openrouter_api_key="sk-or-test",
            local_llm_backend="transformers",
        )
        assert s.llm_generation == "openrouter:deepseek/deepseek-v3.2"
        assert s.openrouter_api_key == "sk-or-test"
        assert s.local_llm_backend == "transformers"
