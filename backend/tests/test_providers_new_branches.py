"""Tests for openrouter and local provider branches."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings


def _make_mock_settings(**overrides):
    """Create a mock settings object with real parse_llm_spec."""
    mock_s = MagicMock(spec=Settings)
    # Wire parse_llm_spec to the real implementation
    mock_s.parse_llm_spec = Settings.parse_llm_spec.__get__(mock_s, Settings)
    # Apply overrides
    for k, v in overrides.items():
        setattr(mock_s, k, v)
    return mock_s


class TestOpenRouterBranch:
    def test_openrouter_returns_chat_model(self):
        mock_s = _make_mock_settings(openrouter_api_key="sk-or-test")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm("openrouter:deepseek/deepseek-v3.2")
            assert llm is not None

    def test_openrouter_raises_without_key(self):
        mock_s = _make_mock_settings(openrouter_api_key="")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_langchain_llm

            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                get_langchain_llm("openrouter:deepseek/deepseek-v3.2")


class TestInstructorOpenRouter:
    def test_openrouter_returns_instructor_client(self):
        """get_instructor_client('openrouter') returns JSON-mode Instructor client."""
        mock_s = _make_mock_settings(openrouter_api_key="sk-or-test")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_instructor_client

            client = get_instructor_client(provider="openrouter")
            assert client is not None

    def test_openrouter_raises_without_key(self):
        """get_instructor_client('openrouter') raises without API key."""
        mock_s = _make_mock_settings(openrouter_api_key="")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_instructor_client

            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                get_instructor_client(provider="openrouter")


class TestLocalBranch:
    def test_local_returns_chat_model(self):
        mock_s = _make_mock_settings(
            ollama_base_url="http://localhost:11434",
        )
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm("local:Qwen/Qwen3.5-4B")
            assert llm is not None


class TestInstructorForExtraction:
    def test_local_prefix_returns_ollama_client_and_model_name(self):
        """'local:' prefix routes to Ollama endpoint and strips the prefix."""
        mock_s = _make_mock_settings(ollama_base_url="http://localhost:11434")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_instructor_for_extraction

            client, model_name = get_instructor_for_extraction("local:qwen3:32b")

        assert model_name == "qwen3:32b"
        assert client is not None

    def test_openrouter_prefix_returns_client_and_model_name(self):
        """'openrouter:' prefix routes to OpenRouter and strips the prefix."""
        mock_s = _make_mock_settings(openrouter_api_key="sk-or-test")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_instructor_for_extraction

            client, model_name = get_instructor_for_extraction(
                "openrouter:deepseek/deepseek-chat-v3-0324"
            )

        assert model_name == "deepseek/deepseek-chat-v3-0324"
        assert client is not None

    def test_openrouter_prefix_raises_without_key(self):
        """'openrouter:' prefix raises ValueError if API key is missing."""
        mock_s = _make_mock_settings(openrouter_api_key="")
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_instructor_for_extraction

            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                get_instructor_for_extraction("openrouter:deepseek/deepseek-chat-v3-0324")

    def test_default_uses_langextract_model_config(self):
        """No override falls back to settings.langextract_model (OpenRouter default)."""
        mock_s = _make_mock_settings(
            langextract_model="openrouter:deepseek/deepseek-chat-v3-0324",
            openrouter_api_key="sk-or-test",
        )
        with patch("app.llm.providers.settings", mock_s):
            from app.llm.providers import get_instructor_for_extraction

            client, model_name = get_instructor_for_extraction()

        assert model_name == "deepseek/deepseek-chat-v3-0324"
        assert client is not None

    def test_default_gemini_fallback(self):
        """langextract_model without provider prefix falls back to Gemini via OpenAI compat."""
        mock_instructor_client = MagicMock()
        mock_s = _make_mock_settings(
            langextract_model="gemini-2.5-flash",
            gemini_api_key="test-api-key",
        )
        with (
            patch("app.llm.providers.settings", mock_s),
            patch("app.llm.providers.instructor") as mock_instr,
            patch("app.llm.providers.AsyncOpenAI"),
        ):
            mock_instr.from_openai.return_value = mock_instructor_client
            mock_instr.Mode.JSON = "json"
            from app.llm.providers import get_instructor_for_extraction

            client, model_name = get_instructor_for_extraction()

        assert model_name == "gemini-2.5-flash"
        assert client is mock_instructor_client
