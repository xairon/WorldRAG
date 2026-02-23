"""Structured logging setup with structlog.

Provides JSON-formatted, context-rich logging for the entire application.
Automatically binds request_id, book_id, chapter from middleware context.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

# Context variables for automatic log enrichment
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
book_id_var: ContextVar[str | None] = ContextVar("book_id", default=None)
chapter_var: ContextVar[int | None] = ContextVar("chapter", default=None)
pipeline_stage_var: ContextVar[str | None] = ContextVar("pipeline_stage", default=None)


def add_context_vars(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Processor that adds contextvars to every log entry."""
    if (request_id := request_id_var.get()) is not None:
        event_dict.setdefault("request_id", request_id)
    if (book_id := book_id_var.get()) is not None:
        event_dict.setdefault("book_id", book_id)
    if (chapter := chapter_var.get()) is not None:
        event_dict.setdefault("chapter", chapter)
    if (stage := pipeline_stage_var.get()) is not None:
        event_dict.setdefault("pipeline_stage", stage)
    return event_dict


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure structlog for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format - "json" for production, "console" for development.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_context_vars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Quiet noisy third-party loggers
    for noisy in ("neo4j", "httpx", "httpcore", "openai", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Bound structlog logger with automatic context enrichment.
    """
    return structlog.get_logger(name)
