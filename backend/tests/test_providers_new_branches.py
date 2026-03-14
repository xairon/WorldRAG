"""Tests for openrouter and local provider branches."""

from unittest.mock import patch

import pytest


class TestOpenRouterBranch:
    def test_openrouter_returns_chat_model(self):
        with patch("app.llm.providers.settings") as mock_s:
            mock_s.openrouter_api_key = "sk-or-test"
            mock_s.parse_llm_spec.return_value = ("openrouter", "deepseek/deepseek-v3.2")
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm("openrouter:deepseek/deepseek-v3.2")
            assert llm is not None

    def test_openrouter_raises_without_key(self):
        with patch("app.llm.providers.settings") as mock_s:
            mock_s.openrouter_api_key = ""
            mock_s.parse_llm_spec.return_value = ("openrouter", "deepseek/deepseek-v3.2")
            from app.llm.providers import get_langchain_llm

            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                get_langchain_llm("openrouter:deepseek/deepseek-v3.2")


class TestLocalBranch:
    def test_local_returns_chat_model(self):
        with patch("app.llm.providers.settings") as mock_s:
            mock_s.local_llm_backend = "ollama"
            mock_s.ollama_base_url = "http://localhost:11434"
            mock_s.parse_llm_spec.return_value = ("local", "Qwen/Qwen3.5-4B")
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm("local:Qwen/Qwen3.5-4B")
            assert llm is not None
