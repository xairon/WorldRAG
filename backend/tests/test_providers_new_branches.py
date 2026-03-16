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


class TestInstructorForExtraction:
    def test_local_prefix_returns_ollama_client_and_model_name(self):
        """'local:' prefix routes to Ollama endpoint and strips the prefix from model name."""
        with patch("app.llm.providers.settings") as mock_s:
            mock_s.ollama_base_url = "http://localhost:11434"
            from app.llm.providers import get_instructor_for_extraction

            client, model_name = get_instructor_for_extraction("local:qwen3:32b")

        assert model_name == "qwen3:32b"
        assert client is not None

    def test_default_returns_gemini_client_and_langextract_model(self):
        """No override uses Gemini and returns settings.langextract_model."""
        from unittest.mock import MagicMock

        mock_instructor_client = MagicMock()
        with patch("app.llm.providers.settings") as mock_s:
            mock_s.gemini_api_key = "test-api-key"
            mock_s.langextract_model = "gemini-2.5-flash"
            with patch("app.llm.providers.get_gemini_client") as mock_gemini:
                mock_gemini.return_value = MagicMock()
                with patch("app.llm.providers.instructor") as mock_instructor:
                    mock_instructor.from_genai.return_value = mock_instructor_client
                    mock_instructor.Mode.GENAI_STRUCTURED_OUTPUTS = "genai_structured_outputs"
                    from app.llm.providers import get_instructor_for_extraction

                    client, model_name = get_instructor_for_extraction()

        assert model_name == "gemini-2.5-flash"
        assert client is mock_instructor_client

    def test_no_override_uses_none_by_default(self):
        """model_override defaults to None, selecting the Gemini path."""
        from unittest.mock import MagicMock

        mock_instructor_client = MagicMock()
        with patch("app.llm.providers.settings") as mock_s:
            mock_s.gemini_api_key = "test-api-key"
            mock_s.langextract_model = "gemini-2.5-flash"
            with patch("app.llm.providers.get_gemini_client") as mock_gemini:
                mock_gemini.return_value = MagicMock()
                with patch("app.llm.providers.instructor") as mock_instructor:
                    mock_instructor.from_genai.return_value = mock_instructor_client
                    mock_instructor.Mode.GENAI_STRUCTURED_OUTPUTS = "genai_structured_outputs"
                    from app.llm.providers import get_instructor_for_extraction

                    result = get_instructor_for_extraction(model_override=None)

        assert isinstance(result, tuple)
        assert len(result) == 2
