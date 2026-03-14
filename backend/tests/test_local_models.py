"""Tests for local model singletons."""
from unittest.mock import MagicMock, patch


class TestLocalReranker:
    def test_get_reranker_returns_crossencoder(self):
        import app.llm.local_models as mod
        mod._reranker = None  # reset singleton
        mock_ce = MagicMock()
        with patch.object(mod, "CrossEncoder", return_value=mock_ce):
            result = mod.get_local_reranker()
            assert result is mock_ce

    def test_reranker_is_singleton(self):
        import app.llm.local_models as mod
        mod._reranker = None
        mock_ce = MagicMock()
        with patch.object(mod, "CrossEncoder", return_value=mock_ce):
            a = mod.get_local_reranker()
            b = mod.get_local_reranker()
            assert a is b


class TestLocalNLI:
    def test_get_nli_model_returns_crossencoder(self):
        import app.llm.local_models as mod
        mod._nli_model = None
        mock_ce = MagicMock()
        with patch.object(mod, "CrossEncoder", return_value=mock_ce):
            result = mod.get_nli_model()
            assert result is mock_ce
