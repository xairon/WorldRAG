"""arq background task workers for WorldRAG.

Entry point:
    uv run arq app.workers.settings.WorkerSettings

Tasks:
    process_book_extraction  — Full KG extraction pipeline
    process_book_embeddings  — Voyage AI embedding pipeline
"""

from app.workers.settings import WorkerSettings
from app.workers.tasks import process_book_embeddings, process_book_extraction

__all__ = [
    "WorkerSettings",
    "process_book_embeddings",
    "process_book_extraction",
]
