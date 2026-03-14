"""Ingestion services — Discovery and Guided modes via Graphiti.

Also re-exports legacy file-parsing utilities for backwards compatibility
with existing routes that import from app.services.ingestion.
"""

from app.services.ingestion.file_parser import extract_epub_metadata, ingest_file, parse_epub

__all__ = ["extract_epub_metadata", "ingest_file", "parse_epub"]
