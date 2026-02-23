---
paths:
  - "backend/**"
---

# Python Backend Rules

## Language & Runtime
- Python 3.12+ with full type annotations
- async/await for all IO operations (DB, HTTP, LLM calls)
- Never use synchronous IO in async contexts

## Data Models
- Pydantic v2 BaseModel for all schemas (not dataclass, not TypedDict for API)
- Use `model_validator` for cross-field validation
- All API responses use Pydantic models

## Imports
- Absolute imports only: `from app.config import settings`
- Group: stdlib → third-party → local (enforced by ruff isort)

## Async Patterns
- Use `asyncio.gather()` for parallel independent operations
- Use `asyncio.Semaphore` for concurrency limits
- Never `await` in a loop when operations are independent

## Error Handling
- Use `tenacity` for retries on external services (LLM, DB)
- Custom exceptions in `app/core/exceptions.py`
- Never catch bare `Exception` — be specific
- All LLM errors → structured log + LangFuse span

## Logging
- Use `structlog` (never `print()` or `logging.getLogger()`)
- Always include context: `logger.info("event", entity_count=5, chapter=42)`
- Bind pipeline context via middleware (request_id, book_id, chapter)

## Neo4j
- Always use parameterized queries: `$param_name`
- MERGE for entity creation (with uniqueness constraints)
- All writes carry `batch_id` for rollback capability
- Close sessions/transactions properly (use async context managers)

## Testing
- pytest-asyncio for all async tests
- Mock LLM calls in unit tests (never call real APIs)
- Use fixtures from `tests/fixtures/` for golden tests
