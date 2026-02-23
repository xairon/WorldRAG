---
paths:
  - "**/tests/**"
---

# Testing Rules

## Framework
- pytest + pytest-asyncio (asyncio_mode = "auto")
- Fixtures in `conftest.py` and `tests/fixtures/`

## Test Levels
1. **Unit tests** (fast, mocked): All LLM calls mocked, no external services
2. **Golden tests** (fixtures): Use pre-recorded LLM responses from `fixtures/`
3. **E2E tests** (slow, marked): `@pytest.mark.slow` + `@pytest.mark.llm`

## Conventions
- Test files: `test_<module>.py`
- Test classes: `Test<Feature>`
- Test functions: `test_<behavior>` or `test_<input>_<expected>`
- Use `async def` for all tests involving async code

## Markers
- `@pytest.mark.slow` — skip in CI fast lane
- `@pytest.mark.llm` — requires LLM API keys

## Mocking
- Mock Neo4j with in-memory driver or fixture data
- Mock LLM responses with fixture JSON files
- Mock Redis with fakeredis
- Never mock the code under test, only external dependencies
