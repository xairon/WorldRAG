"""LangFuse monitoring integration helpers.

Provides convenience functions for creating traces, spans, and generations
in LangFuse for all LLM operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from langfuse import Langfuse

logger = get_logger(__name__)


class MonitoringService:
    """Centralized monitoring service wrapping LangFuse.

    Provides a consistent interface for:
    - Creating traces for pipeline operations
    - Recording LLM generations with token counts and costs
    - Creating spans for non-LLM operations
    - Scoring extraction quality
    """

    def __init__(self, langfuse: Langfuse | None = None) -> None:
        self.langfuse = langfuse
        self._enabled = langfuse is not None

    def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        user_id: str | None = None,
    ):
        """Create a new trace for a pipeline operation.

        Args:
            name: Trace name (e.g., "extraction-ch42", "chat-query").
            metadata: Additional metadata (book_id, chapter, etc.).
            tags: Tags for filtering in LangFuse dashboard.
            user_id: Optional user identifier.

        Returns:
            LangFuse trace object or None if monitoring is disabled.
        """
        if not self._enabled:
            return None

        return self.langfuse.trace(
            name=name,
            metadata=metadata or {},
            tags=tags or [],
            user_id=user_id,
        )

    def span(self, trace, name: str, metadata: dict[str, Any] | None = None):
        """Create a span within a trace.

        Args:
            trace: Parent trace object.
            name: Span name.
            metadata: Additional metadata.

        Returns:
            LangFuse span object or None.
        """
        if trace is None or not self._enabled:
            return None

        return trace.span(name=name, metadata=metadata or {})

    def generation(
        self,
        trace_or_span,
        name: str,
        model: str,
        input_text: str | None = None,
        output_text: str | None = None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Record an LLM generation.

        Args:
            trace_or_span: Parent trace or span.
            name: Generation name (e.g., "extract-characters").
            model: Model name.
            input_text: Input prompt (truncated for large inputs).
            output_text: Model response.
            usage: Token usage dict {input, output, total}.
            metadata: Additional metadata.

        Returns:
            LangFuse generation object or None.
        """
        if trace_or_span is None or not self._enabled:
            return None

        return trace_or_span.generation(
            name=name,
            model=model,
            input=input_text[:2000] if input_text else None,
            output=output_text[:2000] if output_text else None,
            usage=usage or {},
            metadata=metadata or {},
        )

    def score(
        self,
        trace,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """Record a quality score on a trace.

        Args:
            trace: Trace to score.
            name: Score name (e.g., "extraction_quality", "entity_count").
            value: Score value (0.0 - 1.0 for quality, or integer for counts).
            comment: Optional comment.
        """
        if trace is None or not self._enabled:
            return

        trace.score(name=name, value=value, comment=comment)

    def get_langraph_callback(
        self,
        tags: list[str] | None = None,
    ):
        """Get a LangFuse callback handler for LangGraph integration.

        Args:
            tags: Tags for the callback.

        Returns:
            LangFuse CallbackHandler or None.
        """
        if not self._enabled:
            return None

        try:
            from langfuse.callback import CallbackHandler

            return CallbackHandler(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                tags=tags or [],
            )
        except ImportError:
            logger.warning("langfuse_callback_import_failed")
            return None

    def flush(self) -> None:
        """Flush pending events to LangFuse."""
        if self._enabled and self.langfuse:
            self.langfuse.flush()
