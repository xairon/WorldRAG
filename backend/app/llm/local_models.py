"""Lazy-loaded local model singletons for reranking and NLI."""
from __future__ import annotations

from sentence_transformers import CrossEncoder

from app.core.logging import get_logger

logger = get_logger(__name__)

_reranker: CrossEncoder | None = None
_nli_model: CrossEncoder | None = None

RERANKER_MODEL = "zeroentropy/zerank-1-small"
NLI_MODEL = "cross-encoder/nli-deberta-v3-large"


def get_local_reranker() -> CrossEncoder:
    """Return the zerank-1-small reranker (lazy-loaded singleton)."""
    global _reranker  # noqa: PLW0603
    if _reranker is None:
        logger.info("loading_local_reranker", model=RERANKER_MODEL)
        _reranker = CrossEncoder(RERANKER_MODEL, trust_remote_code=True)
        logger.info("local_reranker_loaded", model=RERANKER_MODEL)
    return _reranker


def get_nli_model() -> CrossEncoder:
    """Return the DeBERTa-v3-large NLI model (lazy-loaded singleton)."""
    global _nli_model  # noqa: PLW0603
    if _nli_model is None:
        logger.info("loading_nli_model", model=NLI_MODEL)
        _nli_model = CrossEncoder(NLI_MODEL)
        logger.info("nli_model_loaded", model=NLI_MODEL)
    return _nli_model
