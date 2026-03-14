"""Ingestion services — Discovery and Guided modes via Graphiti.

Also re-exports legacy file-parsing utilities for backwards compatibility
with existing routes that import from app.services.ingestion.
"""

from app.services.ingestion.file_parser import (  # noqa: F401 — re-export for backward compat
    _build_paragraphs_from_html,
    _classify_block_text,
    _parse_chapter_number,
    _split_text_into_chapters,
    extract_epub_metadata,
    ingest_file,
    parse_epub,
    parse_txt,
)

__all__ = [
    "_parse_chapter_number",
    "_split_text_into_chapters",
    "extract_epub_metadata",
    "ingest_file",
    "parse_epub",
    "parse_txt",
]
