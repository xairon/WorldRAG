"""Retry wrapper for LangExtract calls.

LangExtract calls to Gemini can fail with transient 503 errors
("model currently experiencing high demand"). This module provides
an async retry wrapper with exponential backoff.
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import langextract as lx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


def _is_transient_error(exc: BaseException) -> bool:
    """Check if a LangExtract exception is transient (retryable).

    Matches 503/429 errors from Gemini and generic InferenceRuntimeError.
    """
    msg = str(exc).lower()
    return any(
        keyword in msg
        for keyword in ("503", "unavailable", "429", "rate", "overloaded", "high demand", "resource_exhausted")
    )


class _RetryableExtractionError(Exception):
    """Wrapper to signal a retryable extraction failure."""


@retry(
    retry=retry_if_exception_type(_RetryableExtractionError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    reraise=True,
)
async def extract_with_retry(
    *,
    text_or_documents: str,
    prompt_description: str,
    examples: list[Any],
    model_id: str,
    api_key: str | None,
    extraction_passes: int,
    max_workers: int,
    show_progress: bool = False,
    pass_name: str = "",
    book_id: str = "",
    chapter: int = 0,
) -> Any:
    """Call lx.extract with automatic retry on transient Gemini errors.

    Wraps the blocking lx.extract call in asyncio.to_thread and retries
    up to 3 times with exponential backoff (5s, 10s, 20s) on 503/429 errors.

    Returns:
        The LangExtract result object.

    Raises:
        _RetryableExtractionError: On transient failures (triggers retry).
        Exception: On non-transient failures (propagated immediately).
    """
    try:
        result = await asyncio.to_thread(
            partial(
                lx.extract,
                text_or_documents=text_or_documents,
                prompt_description=prompt_description,
                examples=examples,
                model_id=model_id,
                api_key=api_key,
                extraction_passes=extraction_passes,
                max_workers=max_workers,
                show_progress=show_progress,
            )
        )
        return result
    except Exception as exc:
        if _is_transient_error(exc):
            logger.warning(
                "extraction_transient_error_retrying",
                pass_name=pass_name,
                book_id=book_id,
                chapter=chapter,
                error=type(exc).__name__,
                message=str(exc)[:200],
            )
            raise _RetryableExtractionError(str(exc)) from exc
        # Non-transient error — propagate immediately
        raise
