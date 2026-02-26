"""Shared alignment validation for extraction passes.

Centralises the logic that checks LangExtract's alignment_status on
grounded entities and decides whether to skip or discount confidence.
"""

from __future__ import annotations

from typing import Any


def check_alignment(entity: Any, logger: Any) -> tuple[bool, float]:
    """Check alignment status of a LangExtract entity.

    Args:
        entity: A LangExtract extraction entity with optional
            ``alignment_status`` attribute.
        logger: structlog logger for debug output.

    Returns:
        Tuple of (should_skip, confidence).
        ``should_skip`` is True when the entity is UNALIGNED (unreliable spans).
        ``confidence`` is 0.7 for fuzzy alignment, 1.0 for exact.
    """
    alignment = getattr(entity, "alignment_status", None)
    alignment_str = str(alignment).lower() if alignment else "exact"

    if "unaligned" in alignment_str:
        logger.debug(
            "skip_unaligned_entity",
            entity=getattr(entity, "extraction_text", "?"),
        )
        return True, 0.0

    confidence = 0.7 if "fuzzy" in alignment_str else 1.0
    return False, confidence


def alignment_label(entity: Any) -> str:
    """Return the alignment label string for a LangExtract entity.

    Args:
        entity: A LangExtract extraction entity.

    Returns:
        ``"fuzzy"`` or ``"exact"``.
    """
    alignment = getattr(entity, "alignment_status", None)
    alignment_str = str(alignment).lower() if alignment else "exact"
    return "fuzzy" if "fuzzy" in alignment_str else "exact"
