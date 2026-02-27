"""Multi-provider LLM factory with fallbacks.

Provides a unified interface to create LLM clients for different providers
(OpenAI, Anthropic, Gemini) with automatic fallback chains.
"""

from __future__ import annotations

from functools import lru_cache

import instructor
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import SecretStr

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=8)
def get_openai_client() -> AsyncOpenAI:
    """Get cached OpenAI async client."""
    return AsyncOpenAI(api_key=settings.openai_api_key)


@lru_cache(maxsize=4)
def get_anthropic_client() -> AsyncAnthropic:
    """Get cached Anthropic async client."""
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


@lru_cache(maxsize=4)
def get_gemini_client():
    """Get cached Google GenAI client for Gemini models.

    Returns:
        google.genai.Client configured with the Gemini API key.

    Raises:
        ValueError: If no Gemini API key is configured.
    """
    if not settings.gemini_api_key:
        raise ValueError("GOOGLE_API_KEY not configured — cannot create Gemini client")
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def get_instructor_client(
    provider: str = "openai",
    model: str | None = None,
) -> instructor.AsyncInstructor:
    """Get an Instructor client for structured extraction.

    Args:
        provider: LLM provider ("openai", "anthropic", "gemini").
        model: Model name override.

    Returns:
        Instructor-patched async client for Pydantic schema extraction.
    """
    if provider == "openai":
        client = get_openai_client()
        return instructor.from_openai(client)
    elif provider == "anthropic":
        client = get_anthropic_client()
        return instructor.from_anthropic(client)
    elif provider == "gemini":
        client = get_gemini_client()
        return instructor.from_gemini(client)
    else:
        logger.warning("instructor_unknown_provider", provider=provider, fallback="openai")
        client = get_openai_client()
        return instructor.from_openai(client)


def get_instructor_for_task(task: str) -> tuple[instructor.AsyncInstructor, str]:
    """Get instructor client and model for a specific task.

    Args:
        task: One of "reconciliation", "classification", "dedup", "cypher".

    Returns:
        Tuple of (instructor_client, model_name).
    """
    spec_map = {
        "reconciliation": settings.llm_reconciliation,
        "classification": settings.llm_classification,
        "dedup": settings.llm_dedup,
        "cypher": settings.llm_cypher,
        "chat": settings.llm_chat,
    }
    spec = spec_map.get(task, settings.llm_classification)
    provider, model = settings.parse_llm_spec(spec)
    client = get_instructor_client(provider=provider)
    return client, model


def get_langchain_llm(spec: str | None = None):
    """Get a LangChain ChatModel for LangGraph usage.

    Args:
        spec: Provider:model spec (e.g. "openai:gpt-4o"). Defaults to chat model.

    Returns:
        LangChain ChatModel instance with fallback configured.
    """
    if spec is None:
        spec = settings.llm_chat
    provider, model = settings.parse_llm_spec(spec)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        primary = ChatOpenAI(
            model=model,
            api_key=SecretStr(settings.openai_api_key),
            temperature=0,
        )
        # Fallback to Anthropic if available
        if settings.anthropic_api_key:
            from langchain_anthropic import ChatAnthropic

            fallback = ChatAnthropic(
                model="claude-3-5-haiku-latest",  # type: ignore[call-arg]
                api_key=SecretStr(settings.anthropic_api_key),
                temperature=0,
            )
            return primary.with_fallbacks([fallback])
        return primary

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        primary = ChatAnthropic(
            model=model,  # type: ignore[call-arg]
            api_key=SecretStr(settings.anthropic_api_key),
            temperature=0,
        )
        if settings.openai_api_key:
            from langchain_openai import ChatOpenAI

            fallback = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=SecretStr(settings.openai_api_key),
                temperature=0,
            )
            return primary.with_fallbacks([fallback])
        return primary

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        primary = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.gemini_api_key,
            temperature=0,
        )
        # Fallback to OpenAI if available
        if settings.openai_api_key:
            from langchain_openai import ChatOpenAI

            fallback = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=SecretStr(settings.openai_api_key),
                temperature=0,
            )
            return primary.with_fallbacks([fallback])
        return primary

    else:
        logger.warning("langchain_unknown_provider", provider=provider, fallback="openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(settings.openai_api_key),
            temperature=0,
        )
