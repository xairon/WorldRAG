# Full SOTA Chat Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade WorldRAG's chat pipeline to full SOTA with local-first model stack, 6-route adaptive agent, HyDE + multi-query retrieval, NLI faithfulness, conversation memory, feedback system, and frontend UX improvements.

**Architecture:** Extend the existing 9-node LangGraph chat graph into a ~17-node adaptive agent with 6 intent routes. Local models (Ollama for aux LLM, sentence-transformers CrossEncoder for reranker + NLI) handle fast/cheap tasks. API models (Gemini free / OpenRouter) handle generation. PostgreSQL stores feedback. Frontend gets source streaming, citations, feedback buttons, thread sidebar, and confidence badges.

**Tech Stack:** LangGraph, Ollama (Qwen3.5-4B), sentence-transformers (zerank-1-small, DeBERTa-v3-large), langchain-ollama, Gemini 2.5 Flash-Lite, OpenRouter (DeepSeek V3.2), PostgreSQL, React/Next.js, Zustand, Tailwind/shadcn

**Spec:** `docs/superpowers/specs/2026-03-14-full-sota-chat-pipeline-design.md`

---

## Codebase Conventions (read before implementing)

- **Logging:** Always use `from app.core.logging import get_logger` then `logger = get_logger(__name__)`. Never `structlog.get_logger()` directly.
- **LLM factory:** `get_langchain_llm(spec)` in `providers.py` has NO `@lru_cache` — no `.cache_clear()` needed.
- **Retrieve function:** `hybrid_retrieve()` in `retrieve.py` is a standalone function (NOT a LangGraph node). Signature: `hybrid_retrieve(repo, query_text, query_embedding, book_id, *, extra_bm25_queries, ...)`. The actual node wrapper is built inside `build_chat_graph()` in `graph.py`.
- **KG search function:** The function is called `kg_search()` (not `kg_query`). Located in `nodes/kg_query.py`.
- **Router:** Current `classify_intent()` parses raw text (`response.content.strip().lower()`), NOT JSON. The upgrade must add JSON parsing.
- **Auth imports:** Use `from app.api.auth import require_auth` (NOT `from app.api.dependencies`).
- **Frontend API:** `apiFetch()` already prepends `API_BASE="/api"`. Never do `${API_BASE}/api/...`.
- **Route names change:** Old routes (`kg_query`, `hybrid_rag`, `direct`) → new routes (`factual_lookup`, `entity_qa`, `relationship_qa`, `timeline_qa`, `analytical`, `conversational`). This affects: `router.py`, `generate.py` (checks `route == "direct"`), `kg_query.py` (falls back to `"hybrid_rag"`), `graph.py` (all routing functions), and ~5 test files.

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `backend/app/llm/local_models.py` | Lazy-loaded singletons for zerank-1-small + DeBERTa NLI CrossEncoder models |
| `backend/app/agents/chat/nodes/load_memory.py` | Load conversation summary + entity memory from checkpointer state |
| `backend/app/agents/chat/nodes/hyde_expand.py` | Generate hypothetical document via local aux LLM, embed it |
| `backend/app/agents/chat/nodes/deduplicate_chunks.py` | Remove >80% cosine-similar chunks after reranking |
| `backend/app/agents/chat/nodes/temporal_sort.py` | Sort chunks by (chapter, position) for timeline route |
| `backend/app/agents/chat/nodes/generate_cot.py` | Chain-of-thought generation for analytical/timeline routes |
| `backend/app/agents/chat/nodes/nli_check.py` | DeBERTa NLI faithfulness check (replaces LLM-as-judge) |
| `backend/app/agents/chat/nodes/summarize_memory.py` | Compress conversation every 5 turns via local aux LLM |
| `backend/app/schemas/feedback.py` | Pydantic models for chat feedback request/response |
| `backend/app/api/routes/feedback.py` | POST + GET endpoints for chat feedback |
| `scripts/init_postgres.sql` | DDL for chat_feedback table |
| `frontend/components/chat/source-panel.tsx` | Collapsible sources panel during streaming |
| `frontend/components/chat/citation-highlight.tsx` | Parse + render [Ch.N, §P] citations |
| `frontend/components/chat/feedback-buttons.tsx` | Thumbs up/down per message |
| `frontend/components/chat/thread-sidebar.tsx` | Thread history list in left sidebar |
| `frontend/components/chat/confidence-badge.tsx` | Green/yellow/red badge from NLI score |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `transformers>=4.40`, `accelerate>=0.30`, `langchain-ollama>=0.3` |
| `backend/app/config.py` | Add `llm_generation`, `llm_auxiliary`, `openrouter_api_key`, `local_llm_backend`, `ollama_base_url` |
| `backend/app/llm/providers.py` | Add `openrouter:` and `local:` branches to `get_langchain_llm()` |
| `backend/app/llm/embeddings.py` | Add `get_embedder()` module-level factory function |
| `backend/app/agents/chat/state.py` | Add `conversation_summary`, `entity_memory`, `hyde_document`, `deduplicated_chunks`, `turn_count`, `sub_questions`, `generation_output`, `faithfulness_passed` |
| `backend/app/agents/chat/prompts.py` | Add 6-route intent prompt, HyDE prompt, CoT prompt, fiction-tuned generation prompt, memory summarization prompt |
| `backend/app/agents/chat/nodes/router.py` | 6 routes with JSON parsing instead of raw text |
| `backend/app/agents/chat/nodes/retrieve.py` | Multi-dense search across all query variants + HyDE doc |
| `backend/app/agents/chat/nodes/kg_query.py` | Composite scoring formula, entity_memory enrichment |
| `backend/app/agents/chat/nodes/rerank.py` | Replace Cohere with local zerank-1-small CrossEncoder + SSE source streaming |
| `backend/app/agents/chat/nodes/context_assembly.py` | Temporal ordering, entity enrichment from memory |
| `backend/app/agents/chat/nodes/generate.py` | Structured GenerationOutput, fiction-tuned prompts, route check `"conversational"` |
| `backend/app/agents/chat/graph.py` | 6-route conditional edges, new nodes wired in |
| `backend/app/agents/chat/nodes/__init__.py` | Export new nodes |
| `backend/app/services/chat_service.py` | Map generation_output → ChatResponse |
| `backend/app/schemas/chat.py` | Add confidence, claim-level citations to ChatResponse |
| `backend/app/main.py` | Register feedback routes |
| `frontend/hooks/use-chat-stream.ts` | Handle sources SSE event with confidence |
| `frontend/lib/api/chat.ts` | Add feedback API calls via `apiFetch` |
| `frontend/app/(reader)/chat/page.tsx` | Integrate new components |
| `frontend/stores/chat-store.ts` | Thread management (title, delete) |

---

## Chunk 1: LLM Infrastructure (Tasks 1-4)

### Task 1: Add new dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current pyproject.toml**

Read `pyproject.toml` to find the `[project.dependencies]` section.

- [ ] **Step 2: Add new dependencies**

Add these lines to the dependencies array:

```toml
"transformers>=4.40",
"accelerate>=0.30",
"langchain-ollama>=0.3",
```

Do NOT add `bitsandbytes` — it's optional and not needed for Phase 1 (Ollama is the primary backend).

- [ ] **Step 3: Run uv lock to update lockfile**

Run: `python -m uv lock`
Expected: lockfile updated without errors.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add transformers, accelerate, langchain-ollama deps"
```

---

### Task 2: Add new config fields to Settings

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config_new_fields.py`

- [ ] **Step 1: Write failing test for new config fields**

```python
"""Tests for new SOTA config fields."""
from app.config import Settings


class TestNewConfigFields:
    def test_defaults(self):
        s = Settings(
            neo4j_uri="bolt://x:7687",
            neo4j_password="x",
        )
        assert s.llm_generation == "gemini:gemini-2.5-flash-lite"
        assert s.llm_auxiliary == "local:Qwen/Qwen3.5-4B"
        assert s.openrouter_api_key == ""
        assert s.local_llm_backend == "ollama"
        assert s.ollama_base_url == "http://localhost:11434"

    def test_overrides(self):
        s = Settings(
            neo4j_uri="bolt://x:7687",
            neo4j_password="x",
            llm_generation="openrouter:deepseek/deepseek-v3.2",
            openrouter_api_key="sk-or-test",
            local_llm_backend="transformers",
        )
        assert s.llm_generation == "openrouter:deepseek/deepseek-v3.2"
        assert s.openrouter_api_key == "sk-or-test"
        assert s.local_llm_backend == "transformers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_config_new_fields.py -v`
Expected: FAIL — fields don't exist yet.

- [ ] **Step 3: Add fields to Settings class**

In `backend/app/config.py`, add to the `Settings` class after the existing `llm_chat` field:

```python
llm_generation: str = "gemini:gemini-2.5-flash-lite"
llm_auxiliary: str = "local:Qwen/Qwen3.5-4B"
openrouter_api_key: str = ""
local_llm_backend: str = "ollama"  # ollama|transformers
ollama_base_url: str = "http://localhost:11434"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_config_new_fields.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config_new_fields.py
git commit -m "feat(config): add SOTA chat fields (generation, auxiliary, OpenRouter, Ollama)"
```

---

### Task 3: Extend providers.py with OpenRouter and local branches

**Files:**
- Modify: `backend/app/llm/providers.py`
- Test: `backend/tests/test_providers_new_branches.py`

- [ ] **Step 1: Write failing tests for new provider branches**

```python
"""Tests for openrouter and local provider branches."""
from unittest.mock import patch

import pytest


class TestOpenRouterBranch:
    def test_openrouter_returns_chatopenai(self):
        with patch("app.llm.providers.settings") as mock_settings:
            mock_settings.openrouter_api_key = "sk-or-test"
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm("openrouter:deepseek/deepseek-v3.2")
            assert llm is not None

    def test_openrouter_raises_without_key(self):
        with patch("app.llm.providers.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            from app.llm.providers import get_langchain_llm

            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                get_langchain_llm("openrouter:deepseek/deepseek-v3.2")


class TestLocalBranch:
    def test_local_returns_chatollama(self):
        with patch("app.llm.providers.settings") as mock_settings:
            mock_settings.local_llm_backend = "ollama"
            mock_settings.ollama_base_url = "http://localhost:11434"
            from app.llm.providers import get_langchain_llm

            llm = get_langchain_llm("local:Qwen/Qwen3.5-4B")
            assert llm is not None
```

Note: `get_langchain_llm` has NO `@lru_cache` — do NOT call `.cache_clear()`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_providers_new_branches.py -v`
Expected: FAIL — no openrouter/local handling.

- [ ] **Step 3: Implement OpenRouter branch**

In `get_langchain_llm()` in `backend/app/llm/providers.py`, add a branch for the `openrouter` provider:

```python
if provider == "openrouter":
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY required for openrouter provider")
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
    )
```

This reuses `ChatOpenAI` since OpenRouter is OpenAI-compatible.

- [ ] **Step 4: Implement local (Ollama) branch**

Add import at top: `from langchain_ollama import ChatOllama`

Add branch:

```python
if provider == "local":
    return ChatOllama(
        model=model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_providers_new_branches.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm/providers.py backend/tests/test_providers_new_branches.py
git commit -m "feat(providers): add OpenRouter and local/Ollama branches to get_langchain_llm"
```

---

### Task 4: Create local_models.py for zerank + DeBERTa singletons

**Files:**
- Create: `backend/app/llm/local_models.py`
- Test: `backend/tests/test_local_models.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for local model singletons (zerank, DeBERTa NLI)."""
from unittest.mock import patch, MagicMock


class TestLocalReranker:
    def test_get_reranker_returns_crossencoder(self):
        mock_ce = MagicMock()
        with patch(
            "app.llm.local_models.CrossEncoder", return_value=mock_ce,
        ):
            from app.llm.local_models import get_local_reranker

            model = get_local_reranker()
            assert model is mock_ce

    def test_reranker_is_singleton(self):
        mock_ce = MagicMock()
        with patch(
            "app.llm.local_models.CrossEncoder", return_value=mock_ce,
        ):
            from app.llm.local_models import get_local_reranker

            a = get_local_reranker()
            b = get_local_reranker()
            assert a is b


class TestLocalNLI:
    def test_get_nli_model_returns_crossencoder(self):
        mock_ce = MagicMock()
        with patch(
            "app.llm.local_models.CrossEncoder", return_value=mock_ce,
        ):
            from app.llm.local_models import get_nli_model

            model = get_nli_model()
            assert model is mock_ce
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_local_models.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create local_models.py**

```python
"""Lazy-loaded local model singletons for reranking and NLI."""
from __future__ import annotations

from sentence_transformers import CrossEncoder

from app.core.logging import get_logger

logger = get_logger(__name__)

_reranker: CrossEncoder | None = None
_nli_model: CrossEncoder | None = None

RERANKER_MODEL = "zeroentropy/zerank-1-small"
NLI_MODEL = "cross-encoder/nli-deberta-v3-large"


def get_local_reranker() -> CrossEncoder:
    """Return the zerank-1-small reranker (lazy-loaded singleton)."""
    global _reranker
    if _reranker is None:
        logger.info("loading_local_reranker", model=RERANKER_MODEL)
        _reranker = CrossEncoder(RERANKER_MODEL, trust_remote_code=True)
        logger.info("local_reranker_loaded", model=RERANKER_MODEL)
    return _reranker


def get_nli_model() -> CrossEncoder:
    """Return the DeBERTa-v3-large NLI model (lazy-loaded singleton)."""
    global _nli_model
    if _nli_model is None:
        logger.info("loading_nli_model", model=NLI_MODEL)
        _nli_model = CrossEncoder(NLI_MODEL)
        logger.info("nli_model_loaded", model=NLI_MODEL)
    return _nli_model
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_local_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/local_models.py backend/tests/test_local_models.py
git commit -m "feat(llm): add lazy-loaded zerank reranker and DeBERTa NLI singletons"
```

---

### Task 4b: Add get_embedder() factory to embeddings.py

**Files:**
- Modify: `backend/app/llm/embeddings.py`

The codebase currently has `LocalEmbedder` class but no factory function. New nodes need a simple `get_embedder()` import.

- [ ] **Step 1: Add factory function at the end of embeddings.py**

Read `backend/app/llm/embeddings.py` first, then append:

```python
# Module-level factory for convenience
_embedder_instance: LocalEmbedder | None = None


def get_embedder() -> LocalEmbedder:
    """Return a module-level LocalEmbedder singleton."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = LocalEmbedder()
    return _embedder_instance
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/llm/embeddings.py
git commit -m "feat(embeddings): add get_embedder() factory function"
```

---

## Chunk 2: Chat Agent State & Memory (Tasks 5-6, 17)

### Task 5: Add new state fields to ChatAgentState

**Files:**
- Modify: `backend/app/agents/chat/state.py`
- Modify: `backend/tests/test_chat_state.py`

Note: `import operator` is already present in state.py. Do NOT add a duplicate.

- [ ] **Step 1: Write test for new state fields**

Add a new test class to `backend/tests/test_chat_state.py`:

```python
class TestNewStateFields:
    def test_state_accepts_new_fields(self):
        state: ChatAgentState = {
            "conversation_summary": "They discussed chapter 3.",
            "entity_memory": ["ent-1", "ent-2"],
            "hyde_document": "A hypothetical passage...",
            "deduplicated_chunks": [{"text": "chunk"}],
            "turn_count": 0,
            "sub_questions": ["Q1", "Q2"],
            "generation_output": {"answer": "yes", "citations": []},
            "faithfulness_passed": True,
        }
        assert state["turn_count"] == 0
        assert state["faithfulness_passed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_state.py::TestNewStateFields -v`
Expected: FAIL — fields not in TypedDict.

- [ ] **Step 3: Add fields to ChatAgentState**

In `backend/app/agents/chat/state.py`, add these fields to the TypedDict (after existing fields). `operator` is already imported:

```python
# -- Memory --
conversation_summary: str
entity_memory: list[str]

# -- HyDE --
hyde_document: str

# -- Post-rerank --
deduplicated_chunks: list[dict[str, Any]]

# -- Turn tracking --
turn_count: Annotated[int, operator.add]

# -- Decomposition (Phase 2) --
sub_questions: list[str]

# -- Structured generation --
generation_output: dict[str, Any]

# -- Faithfulness --
faithfulness_passed: bool
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_chat_state.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/state.py backend/tests/test_chat_state.py
git commit -m "feat(state): add SOTA fields (memory, HyDE, dedup, turn_count, generation_output)"
```

---

### Task 6: Implement load_memory node

**Files:**
- Create: `backend/app/agents/chat/nodes/load_memory.py`
- Test: `backend/tests/test_load_memory_node.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for load_memory node."""
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage


class TestLoadMemory:
    @pytest.mark.asyncio
    async def test_loads_summary_from_state(self):
        from app.agents.chat.nodes.load_memory import load_memory

        state: dict[str, Any] = {
            "messages": [
                HumanMessage(content="Hi"),
                AIMessage(content="Hello!"),
            ] * 5,  # 10 messages
            "conversation_summary": "User asked about chapter 3.",
            "entity_memory": ["ent-1"],
        }
        result = await load_memory(state)
        assert len(result["messages"]) <= 6
        assert result["conversation_summary"] == "User asked about chapter 3."

    @pytest.mark.asyncio
    async def test_no_truncation_under_window(self):
        from app.agents.chat.nodes.load_memory import load_memory

        state: dict[str, Any] = {
            "messages": [HumanMessage(content="Hi")],
        }
        result = await load_memory(state)
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_empty_state_returns_defaults(self):
        from app.agents.chat.nodes.load_memory import load_memory

        state: dict[str, Any] = {}
        result = await load_memory(state)
        assert result["conversation_summary"] == ""
        assert result["entity_memory"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_load_memory_node.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement load_memory node**

```python
"""Load conversation memory from checkpointer state."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

MESSAGE_WINDOW = 6


async def load_memory(state: dict[str, Any]) -> dict[str, Any]:
    """Load conversation summary and trim message window."""
    messages = state.get("messages", [])
    summary = state.get("conversation_summary", "")
    entity_mem = state.get("entity_memory", [])

    if len(messages) > MESSAGE_WINDOW:
        messages = messages[-MESSAGE_WINDOW:]

    logger.debug(
        "memory_loaded",
        message_count=len(messages),
        has_summary=bool(summary),
        entity_count=len(entity_mem),
    )

    return {
        "messages": messages,
        "conversation_summary": summary,
        "entity_memory": entity_mem,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_load_memory_node.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/load_memory.py backend/tests/test_load_memory_node.py
git commit -m "feat(chat): implement load_memory node with sliding window"
```

---

### Task 17: Implement summarize_memory node

**Files:**
- Create: `backend/app/agents/chat/nodes/summarize_memory.py`
- Modify: `backend/app/agents/chat/prompts.py`
- Test: `backend/tests/test_summarize_memory_node.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for summarize_memory node."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

PATCH_TARGET = "app.agents.chat.nodes.summarize_memory.get_langchain_llm"


class TestSummarizeMemory:
    @pytest.mark.asyncio
    async def test_summarizes_conversation(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"summary": "User asked about Jake in chapter 3."}',
        )
        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.summarize_memory import (
                summarize_memory,
            )

            state: dict[str, Any] = {
                "messages": [
                    HumanMessage(content="Who is Jake?"),
                    AIMessage(content="Jake is a warrior."),
                ],
                "conversation_summary": "",
            }
            result = await summarize_memory(state)
            assert len(result["conversation_summary"]) > 0
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_incorporates_prior_summary(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"summary": "Extended conversation about Jake."}',
        )
        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.summarize_memory import (
                summarize_memory,
            )

            state: dict[str, Any] = {
                "messages": [
                    HumanMessage(content="What level is he?"),
                    AIMessage(content="Level 42."),
                ],
                "conversation_summary": "Prior: User asked about Jake.",
            }
            result = await summarize_memory(state)
            assert len(result["conversation_summary"]) > 0
            call_args = mock_llm.ainvoke.call_args[0][0]
            prompt_text = " ".join(m.content for m in call_args)
            assert "Prior" in prompt_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_summarize_memory_node.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Add summarization prompt to prompts.py**

Read `backend/app/agents/chat/prompts.py` first, then append:

```python
SUMMARIZE_MEMORY_SYSTEM = """\
Summarize the conversation so far into a concise JSON object.
Include: key topics discussed, entities mentioned, questions asked, answers given.
If a prior summary exists, incorporate it.

Prior summary: {prior_summary}

Return JSON: {{"summary": "<concise summary of the full conversation>"}}
"""
```

- [ ] **Step 4: Implement summarize_memory node**

```python
"""Summarize conversation memory via local aux LLM."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import SUMMARIZE_MEMORY_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def summarize_memory(state: dict[str, Any]) -> dict[str, Any]:
    """Compress conversation into a summary using the auxiliary LLM."""
    messages = state.get("messages", [])
    prior = state.get("conversation_summary", "")

    llm = get_langchain_llm(settings.llm_auxiliary)

    conv_text = "\n".join(
        f"{m.type}: {m.content}" for m in messages if hasattr(m, "content")
    )

    prompt = [
        SystemMessage(content=SUMMARIZE_MEMORY_SYSTEM.format(
            prior_summary=prior or "None",
        )),
        HumanMessage(content=f"Conversation:\n{conv_text}"),
    ]

    response = await llm.ainvoke(prompt)

    try:
        parsed = json.loads(response.content)
        summary = parsed.get("summary", response.content)
    except (json.JSONDecodeError, AttributeError):
        summary = response.content

    logger.info("memory_summarized", summary_length=len(summary))
    return {"conversation_summary": summary}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_summarize_memory_node.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/chat/nodes/summarize_memory.py backend/tests/test_summarize_memory_node.py backend/app/agents/chat/prompts.py
git commit -m "feat(chat): implement summarize_memory node with aux LLM"
```

---

## Chunk 3: Intent & Query Expansion (Tasks 7-8)

### Task 7: Upgrade intent_analyzer to 6 routes with JSON parsing

**Files:**
- Modify: `backend/app/agents/chat/nodes/router.py`
- Modify: `backend/app/agents/chat/prompts.py`
- Test: `backend/tests/test_router_6routes.py`

**IMPORTANT:** This task changes the route names from `kg_query/hybrid_rag/direct` to 6 new routes. This will temporarily break existing tests until Task 18 (graph rewiring) updates them. Run only the new test file until then.

- [ ] **Step 1: Write failing tests for new routes**

```python
"""Tests for 6-route intent analyzer."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROUTER_PATCH = "app.agents.chat.nodes.router.get_langchain_llm"

ROUTES = [
    "factual_lookup",
    "entity_qa",
    "relationship_qa",
    "timeline_qa",
    "analytical",
    "conversational",
]


class TestSixRouteAnalyzer:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", ROUTES)
    async def test_routes_all_types(self, route: str):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content=f'{{"route": "{route}"}}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.chat.nodes.router import classify_intent

            state: dict[str, Any] = {
                "query": "Test query",
                "messages": [],
                "original_query": "Test query",
            }
            result = await classify_intent(state)
            assert result["route"] == route

    @pytest.mark.asyncio
    async def test_unknown_route_defaults_to_entity_qa(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"route": "unknown_xyz"}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.chat.nodes.router import classify_intent

            state: dict[str, Any] = {
                "query": "Test",
                "messages": [],
                "original_query": "Test",
            }
            result = await classify_intent(state)
            assert result["route"] == "entity_qa"

    @pytest.mark.asyncio
    async def test_invalid_json_defaults_to_entity_qa(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="not json")
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.chat.nodes.router import classify_intent

            state: dict[str, Any] = {
                "query": "Test",
                "messages": [],
                "original_query": "Test",
            }
            result = await classify_intent(state)
            assert result["route"] == "entity_qa"

    @pytest.mark.asyncio
    async def test_raw_text_route_also_works(self):
        """Backward compat: if LLM returns just 'entity_qa' without JSON."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(content="entity_qa")
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.chat.nodes.router import classify_intent

            state: dict[str, Any] = {
                "query": "Test",
                "messages": [],
                "original_query": "Test",
            }
            result = await classify_intent(state)
            assert result["route"] == "entity_qa"

    @pytest.mark.asyncio
    async def test_includes_summary_in_prompt(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"route": "entity_qa"}',
        )
        with patch(ROUTER_PATCH, return_value=mock_llm):
            from app.agents.chat.nodes.router import classify_intent

            state: dict[str, Any] = {
                "query": "Who?",
                "messages": [],
                "original_query": "Who?",
                "conversation_summary": "They talked about Jake.",
            }
            result = await classify_intent(state)
            call_args = mock_llm.ainvoke.call_args[0][0]
            text = " ".join(m.content for m in call_args)
            assert "Jake" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_router_6routes.py -v`
Expected: FAIL — only 3 routes, no JSON parsing.

- [ ] **Step 3: Update ROUTER_SYSTEM prompt in prompts.py**

Replace `ROUTER_SYSTEM` in `backend/app/agents/chat/prompts.py`:

```python
ROUTER_SYSTEM = """\
You are a query intent classifier for a fiction novel Q&A system.
Classify the user's question into exactly one of these routes:

- "factual_lookup": Direct KG lookup — entity stats, class, level, skills \
(e.g. "What class is Jake?", "What level is he?")
- "entity_qa": Questions about a specific character, item, or entity that need \
both KG and text context (e.g. "Tell me about Jake's personality")
- "relationship_qa": Questions about relationships between entities \
(e.g. "How do Jake and Mira know each other?")
- "timeline_qa": Questions about event ordering, timelines, or chapter progression \
(e.g. "What happened after the dungeon?", "When did Jake level up?")
- "analytical": Complex multi-part or comparative questions \
(e.g. "Compare Jake and Mira's growth", "Why did the guild split?")
- "conversational": Greetings, meta questions, or follow-ups that don't need retrieval \
(e.g. "Hello", "Thanks", "Can you explain more?")

{summary_context}

Return JSON: {{"route": "<category>"}}
"""
```

- [ ] **Step 4: Rewrite classify_intent with JSON parsing**

Replace the body of `classify_intent` in `backend/app/agents/chat/nodes/router.py`:

```python
import json

VALID_ROUTES = {
    "factual_lookup", "entity_qa", "relationship_qa",
    "timeline_qa", "analytical", "conversational",
}
DEFAULT_ROUTE = "entity_qa"

async def classify_intent(state: dict[str, Any]) -> dict[str, Any]:
    llm = get_langchain_llm(settings.llm_auxiliary)

    # Build summary context
    summary = state.get("conversation_summary", "")
    summary_context = f"Conversation summary: {summary}" if summary else ""

    messages: list = [
        SystemMessage(content=ROUTER_SYSTEM.format(summary_context=summary_context)),
    ]

    # Include recent conversation history for multi-turn context
    history = state.get("messages", [])
    if len(history) > 2:
        for msg in history[-5:-1]:
            messages.append(msg)

    messages.append(HumanMessage(content=state["query"]))

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    # Try JSON parsing first, fall back to raw text
    try:
        parsed = json.loads(raw)
        route = parsed.get("route", "").lower()
    except (json.JSONDecodeError, AttributeError):
        route = raw.lower()

    if route not in VALID_ROUTES:
        logger.warning("router_unknown_route", raw=raw, defaulting=DEFAULT_ROUTE)
        route = DEFAULT_ROUTE

    logger.info("router_classified", route=route, query_len=len(state["query"]))
    return {"route": route}
```

- [ ] **Step 5: Run new tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_router_6routes.py -v`
Expected: PASS

- [ ] **Step 6: Commit (existing tests may fail until Task 18)**

```bash
git add backend/app/agents/chat/nodes/router.py backend/app/agents/chat/prompts.py backend/tests/test_router_6routes.py
git commit -m "feat(chat): upgrade intent analyzer to 6 routes with JSON parsing"
```

---

### Task 8: Implement hyde_expand node

**Files:**
- Create: `backend/app/agents/chat/nodes/hyde_expand.py`
- Modify: `backend/app/agents/chat/prompts.py`
- Test: `backend/tests/test_hyde_node.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for HyDE expand node."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PATCH_TARGET = "app.agents.chat.nodes.hyde_expand.get_langchain_llm"


class TestHydeExpand:
    @pytest.mark.asyncio
    async def test_generates_hypothetical_document(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="Jake drew his sword and charged into the dungeon.",
        )
        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.hyde_expand import hyde_expand

            state: dict[str, Any] = {
                "query": "What happened in the dungeon?",
                "route": "entity_qa",
            }
            result = await hyde_expand(state)
            assert len(result["hyde_document"]) > 0
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_skipped_for_conversational(self):
        from app.agents.chat.nodes.hyde_expand import hyde_expand

        state: dict[str, Any] = {
            "query": "Hello!",
            "route": "conversational",
        }
        result = await hyde_expand(state)
        assert result["hyde_document"] == ""

    @pytest.mark.asyncio
    async def test_skipped_for_factual_lookup(self):
        from app.agents.chat.nodes.hyde_expand import hyde_expand

        state: dict[str, Any] = {
            "query": "What level is Jake?",
            "route": "factual_lookup",
        }
        result = await hyde_expand(state)
        assert result["hyde_document"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_hyde_node.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Add HyDE prompt to prompts.py**

Append to `backend/app/agents/chat/prompts.py`:

```python
HYDE_SYSTEM = """\
You are a fiction novel assistant. Given a question, write a short passage \
(2-3 sentences, ~100 tokens) that would be a plausible answer found in the novel. \
Do NOT answer the question — write text that would appear in the source material. \
Focus on narrative style matching the novel's genre.
"""
```

- [ ] **Step 4: Implement hyde_expand node**

```python
"""HyDE: generate a hypothetical document for improved retrieval."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import HYDE_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

SKIP_ROUTES = {"conversational", "factual_lookup"}


async def hyde_expand(state: dict[str, Any]) -> dict[str, Any]:
    """Generate a hypothetical document for embedding-based retrieval."""
    route = state.get("route", "")
    if route in SKIP_ROUTES:
        return {"hyde_document": ""}

    query = state.get("query", "")
    llm = get_langchain_llm(settings.llm_auxiliary)

    response = await llm.ainvoke([
        SystemMessage(content=HYDE_SYSTEM),
        HumanMessage(content=query),
    ])

    hyde_doc = response.content.strip()
    logger.debug("hyde_generated", length=len(hyde_doc))
    return {"hyde_document": hyde_doc}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_hyde_node.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/chat/nodes/hyde_expand.py backend/tests/test_hyde_node.py backend/app/agents/chat/prompts.py
git commit -m "feat(chat): implement HyDE expand node for improved retrieval"
```

---

## Chunk 4: Retrieval & Reranking (Tasks 9-13)

### Task 9: Upgrade retrieve to multi-dense search

**Files:**
- Modify: `backend/app/agents/chat/nodes/retrieve.py`
- Test: `backend/tests/test_retrieve_multi_dense.py`

**IMPORTANT:** `hybrid_retrieve()` is NOT a LangGraph node — it's a standalone function with signature `hybrid_retrieve(repo, query_text, query_embedding, book_id, *, extra_bm25_queries, ...)`. The node wrapper is built inside `build_chat_graph()`. Tests must call the function directly with proper args.

The current code only does ONE dense search with `query_embedding`. We need to support multiple dense searches (one per query variant + HyDE doc). The approach: add an `extra_dense_embeddings` parameter to `hybrid_retrieve()`.

- [ ] **Step 1: Write failing test for multi-dense retrieval**

```python
"""Tests for multi-dense retrieval."""
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agents.chat.nodes.retrieve import hybrid_retrieve


class TestMultiDenseRetrieval:
    @pytest.mark.asyncio
    async def test_runs_dense_for_each_extra_embedding(self):
        repo = AsyncMock()
        repo.execute_read = AsyncMock(return_value=[])

        await hybrid_retrieve(
            repo=repo,
            query_text="Who is Jake?",
            query_embedding=[0.1] * 768,
            book_id="book-1",
            extra_dense_embeddings=[[0.2] * 768, [0.3] * 768],
        )

        # Should have called execute_read for:
        # 3 dense (1 original + 2 extra) + 1 sparse + 1 graph = 5 calls minimum
        assert repo.execute_read.call_count >= 5

    @pytest.mark.asyncio
    async def test_no_extra_embeddings_unchanged(self):
        repo = AsyncMock()
        repo.execute_read = AsyncMock(return_value=[])

        await hybrid_retrieve(
            repo=repo,
            query_text="Who is Jake?",
            query_embedding=[0.1] * 768,
            book_id="book-1",
        )

        # Original behavior: 1 dense + 1 sparse + 1 graph = 3 calls
        assert repo.execute_read.call_count == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_retrieve_multi_dense.py -v`
Expected: FAIL — no `extra_dense_embeddings` parameter.

- [ ] **Step 3: Add extra_dense_embeddings parameter**

In `backend/app/agents/chat/nodes/retrieve.py`, modify `hybrid_retrieve`:

1. Add parameter: `extra_dense_embeddings: list[list[float]] | None = None`
2. Build extra dense search tasks for each extra embedding
3. Collect all dense results, deduplicate by `node_id` (keep highest score)
4. Feed into RRF fusion as before

```python
async def hybrid_retrieve(
    repo,
    query_text: str,
    query_embedding: list[float],
    book_id: str,
    *,
    extra_bm25_queries: list[str] | None = None,
    extra_dense_embeddings: list[list[float]] | None = None,  # NEW
    top_k_per_arm: int = 30,
    final_top_k: int = 15,
    max_chapter: int | None = None,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    graph_weight: float = 0.5,
) -> list[dict[str, Any]]:
    # ... existing sparse setup ...

    # Dense: primary + extra embeddings
    dense_tasks = [
        _dense_search(repo, query_embedding, book_id, top_k_per_arm, max_chapter),
    ]
    for emb in extra_dense_embeddings or []:
        dense_tasks.append(
            _dense_search(repo, emb, book_id, top_k_per_arm, max_chapter),
        )

    all_tasks = [*dense_tasks, *sparse_tasks, _graph_search(...)]
    results = await asyncio.gather(*all_tasks)

    # Merge all dense results, dedup by node_id
    all_dense = []
    for r in results[:len(dense_tasks)]:
        all_dense.extend(r)
    seen = {}
    for item in all_dense:
        nid = item["node_id"]
        if nid not in seen or item.get("score", 0) > seen[nid].get("score", 0):
            seen[nid] = item
    dense_results = list(seen.values())

    # ... rest unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_retrieve_multi_dense.py -v`
Expected: PASS

- [ ] **Step 5: Run existing retrieval tests**

Run: `cd backend && python -m pytest tests/ -k "retrieve" -v`
Expected: All PASS (backward compatible — extra_dense_embeddings defaults to None).

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/chat/nodes/retrieve.py backend/tests/test_retrieve_multi_dense.py
git commit -m "feat(chat): add multi-dense search to hybrid_retrieve"
```

---

### Task 10: Add composite scoring to kg_search

**Files:**
- Modify: `backend/app/agents/chat/nodes/kg_query.py`
- Test: `backend/tests/test_kg_scoring.py`

**IMPORTANT:** The function is `kg_search()` (not `kg_query`). It takes `(state, *, repo)`.

- [ ] **Step 1: Write failing test for composite scoring**

```python
"""Tests for KG composite scoring."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PATCH_TARGET = "app.agents.chat.nodes.kg_query.get_langchain_llm"


class TestKGCompositeScoring:
    @pytest.mark.asyncio
    async def test_grounded_chunks_have_composite_score(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"entities": ["Jake"], "query_type": "entity"}',
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                # Fulltext search result
                [{"name": "Jake", "labels": ["Character"], "score": 1.0,
                  "description": "A warrior", "book_id": "b1"}],
                # Relationship expansion
                [{"source": "Jake", "rel_type": "ALLIES_WITH",
                  "target_name": "Mira", "target_label": "Character"}],
                # Grounded chunks — now with composite score
                [{"node_id": "n1", "text": "Jake fought.", "chapter_number": 3,
                  "chapter_title": "Ch3", "score": 0.85}],
            ],
        )

        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.kg_query import kg_search

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "book_id": "book-1",
                "messages": [],
            }
            result = await kg_search(state, repo=mock_repo)
            assert len(result.get("reranked_chunks", [])) > 0

    @pytest.mark.asyncio
    async def test_appends_to_entity_memory(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"entities": ["Jake"], "query_type": "entity"}',
        )

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(
            side_effect=[
                [{"name": "Jake", "labels": ["Character"], "score": 1.0,
                  "description": "A warrior", "book_id": "b1"}],
                [],  # no relationships
                [],  # no chunks
            ],
        )

        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.kg_query import kg_search

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "book_id": "book-1",
                "messages": [],
                "entity_memory": [],
            }
            result = await kg_search(state, repo=mock_repo)
            assert "Jake" in result.get("entity_memory", [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_kg_scoring.py -v`
Expected: FAIL

- [ ] **Step 3: Update kg_search in kg_query.py**

1. Replace the grounded chunks Cypher `1.0 AS score` with composite formula:

```cypher
RETURN DISTINCT elementId(chunk) AS node_id,
       chunk.text AS text,
       chap.number AS chapter_number,
       chap.title AS chapter_title,
       (toFloat(SIZE([(entity)-[]-() | 1])) / 10.0) * 0.4 +
       CASE WHEN entity.description IS NOT NULL THEN 0.3 ELSE 0.0 END +
       0.3 AS score
ORDER BY score DESC
LIMIT 10
```

2. Add entity memory enrichment — append found entity names to `entity_memory`:

```python
# After entities are found:
entity_names_found = [e["name"] for e in entities]
return {
    ...existing fields...,
    "entity_memory": entity_names_found,  # NEW: enriches state via list append
}
```

3. Update fallback route from `"hybrid_rag"` to `"entity_qa"`:

```python
return {"route": "entity_qa", "kg_cypher_result": [], "kg_entities": []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_kg_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/kg_query.py backend/tests/test_kg_scoring.py
git commit -m "feat(chat): add composite scoring and entity memory to kg_search"
```

---

### Task 11: Replace rerank with zerank + SSE source streaming

**Files:**
- Modify: `backend/app/agents/chat/nodes/rerank.py`
- Test: `backend/tests/test_rerank_zerank.py`

This task combines the reranker replacement AND the SSE source emission (previously separate Task 19) to avoid touching rerank.py twice.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for zerank local reranker with SSE emission."""
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


class TestRerankZerank:
    @pytest.mark.asyncio
    async def test_reranks_with_local_crossencoder(self):
        mock_model = MagicMock()
        mock_model.rank.return_value = [
            {"corpus_id": 1, "score": 0.95},
            {"corpus_id": 0, "score": 0.72},
        ]

        with patch(
            "app.agents.chat.nodes.rerank.get_local_reranker",
            return_value=mock_model,
        ):
            from app.agents.chat.nodes.rerank import rerank_results

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "fused_results": [
                    {"text": "Low relevance.", "chunk_id": "c0"},
                    {"text": "Jake is a warrior.", "chunk_id": "c1"},
                ],
            }
            result = await rerank_results(state)
            assert result["reranked_chunks"][0]["chunk_id"] == "c1"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self):
        from app.agents.chat.nodes.rerank import rerank_results

        state: dict[str, Any] = {
            "query": "Test",
            "fused_results": [],
        }
        result = await rerank_results(state)
        assert result["reranked_chunks"] == []

    @pytest.mark.asyncio
    async def test_emits_sources_sse_event(self):
        mock_model = MagicMock()
        mock_model.rank.return_value = [
            {"corpus_id": 0, "score": 0.9},
        ]
        mock_writer = MagicMock()

        with (
            patch(
                "app.agents.chat.nodes.rerank.get_local_reranker",
                return_value=mock_model,
            ),
            patch(
                "app.agents.chat.nodes.rerank.get_stream_writer",
                return_value=mock_writer,
            ),
        ):
            from app.agents.chat.nodes.rerank import rerank_results

            state: dict[str, Any] = {
                "query": "Test",
                "fused_results": [
                    {"text": "Jake fights.", "chapter_number": 3,
                     "position": 1, "relevance_score": 0.9},
                ],
            }
            await rerank_results(state)
            mock_writer.assert_called_once()
            event = mock_writer.call_args[0][0]
            assert event["event"] == "sources"
            assert len(event["sources"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_rerank_zerank.py -v`
Expected: FAIL — still using Cohere.

- [ ] **Step 3: Rewrite rerank.py**

```python
"""Rerank retrieved chunks using local zerank-1-small CrossEncoder."""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.llm.local_models import get_local_reranker

logger = get_logger(__name__)

RERANK_TOP_N = 5
MIN_RELEVANCE = 0.1


def _try_emit_sources(reranked: list[dict[str, Any]]) -> None:
    """Emit sources SSE event if inside a streaming context."""
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        writer({
            "event": "sources",
            "sources": [
                {
                    "text": c.get("text", ""),
                    "chapter_number": c.get("chapter_number"),
                    "chapter_title": c.get("chapter_title", ""),
                    "position": c.get("position"),
                    "relevance_score": c.get("relevance_score", 0),
                }
                for c in reranked
            ],
            "chunks_retrieved": len(reranked),
            "chunks_after_rerank": len(reranked),
        })
    except Exception:
        pass  # Not in streaming context


async def rerank_results(state: dict[str, Any]) -> dict[str, Any]:
    """Rerank fused results using local zerank-1-small CrossEncoder."""
    query = state.get("query", "")
    chunks = state.get("fused_results", [])

    if not chunks:
        return {"reranked_chunks": []}

    documents = [c.get("text", "") for c in chunks]
    model = get_local_reranker()

    results = await asyncio.to_thread(model.rank, query, documents)

    reranked = []
    for r in results[:RERANK_TOP_N]:
        idx = r["corpus_id"]
        score = r["score"]
        if score < MIN_RELEVANCE:
            continue
        chunk = {**chunks[idx], "relevance_score": score}
        reranked.append(chunk)

    logger.info(
        "reranked",
        input_count=len(chunks),
        output_count=len(reranked),
        top_score=reranked[0]["relevance_score"] if reranked else 0,
    )

    _try_emit_sources(reranked)

    return {"reranked_chunks": reranked}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_rerank_zerank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/rerank.py backend/tests/test_rerank_zerank.py
git commit -m "feat(chat): replace Cohere with zerank-1-small + SSE source emission"
```

---

### Task 12: Implement deduplicate_chunks node

**Files:**
- Create: `backend/app/agents/chat/nodes/deduplicate_chunks.py`
- Test: `backend/tests/test_deduplicate_chunks.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for chunk deduplication."""
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


class TestDeduplicateChunks:
    @pytest.mark.asyncio
    async def test_removes_near_duplicates(self):
        mock_embedder = AsyncMock()
        mock_embedder.embed_texts.return_value = [
            [1.0, 0.0, 0.0],
            [0.99, 0.01, 0.0],  # >0.80 sim with first
            [0.0, 1.0, 0.0],    # different
        ]

        with patch(
            "app.agents.chat.nodes.deduplicate_chunks.get_embedder",
            return_value=mock_embedder,
        ):
            from app.agents.chat.nodes.deduplicate_chunks import (
                deduplicate_chunks,
            )

            state: dict[str, Any] = {
                "reranked_chunks": [
                    {"text": "Jake fights.", "relevance_score": 0.9},
                    {"text": "Jake is fighting.", "relevance_score": 0.8},
                    {"text": "Mira heals.", "relevance_score": 0.7},
                ],
            }
            result = await deduplicate_chunks(state)
            assert len(result["deduplicated_chunks"]) == 2

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        from app.agents.chat.nodes.deduplicate_chunks import (
            deduplicate_chunks,
        )

        state: dict[str, Any] = {"reranked_chunks": []}
        result = await deduplicate_chunks(state)
        assert result["deduplicated_chunks"] == []

    @pytest.mark.asyncio
    async def test_single_chunk_passes_through(self):
        mock_embedder = AsyncMock()
        mock_embedder.embed_texts.return_value = [[1.0, 0.0]]

        with patch(
            "app.agents.chat.nodes.deduplicate_chunks.get_embedder",
            return_value=mock_embedder,
        ):
            from app.agents.chat.nodes.deduplicate_chunks import (
                deduplicate_chunks,
            )

            state: dict[str, Any] = {
                "reranked_chunks": [
                    {"text": "Jake fights.", "relevance_score": 0.9},
                ],
            }
            result = await deduplicate_chunks(state)
            assert len(result["deduplicated_chunks"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_deduplicate_chunks.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement deduplicate_chunks node**

```python
"""Remove near-duplicate chunks via cosine similarity."""
from __future__ import annotations

from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.llm.embeddings import get_embedder

logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.80


async def deduplicate_chunks(state: dict[str, Any]) -> dict[str, Any]:
    """Remove chunks with >80% cosine similarity, keeping higher-scored."""
    chunks = state.get("reranked_chunks", [])
    if len(chunks) <= 1:
        return {"deduplicated_chunks": list(chunks)}

    embedder = get_embedder()
    texts = [c.get("text", "") for c in chunks]
    embeddings = await embedder.embed_texts(texts)
    vecs = np.array(embeddings)

    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    vecs = vecs / norms

    keep = []
    kept_vecs = []
    for i, chunk in enumerate(chunks):
        if kept_vecs:
            sims = vecs[i] @ np.array(kept_vecs).T
            if np.max(sims) > SIMILARITY_THRESHOLD:
                continue
        keep.append(chunk)
        kept_vecs.append(vecs[i])

    removed = len(chunks) - len(keep)
    if removed:
        logger.info("chunks_deduplicated", removed=removed, kept=len(keep))

    return {"deduplicated_chunks": keep}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_deduplicate_chunks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/deduplicate_chunks.py backend/tests/test_deduplicate_chunks.py
git commit -m "feat(chat): implement chunk deduplication via cosine similarity"
```

---

### Task 13: Implement temporal_sort node

**Files:**
- Create: `backend/app/agents/chat/nodes/temporal_sort.py`
- Test: `backend/tests/test_temporal_sort.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for temporal sort node."""
from typing import Any

import pytest


class TestTemporalSort:
    @pytest.mark.asyncio
    async def test_sorts_by_chapter_then_position(self):
        from app.agents.chat.nodes.temporal_sort import temporal_sort

        state: dict[str, Any] = {
            "deduplicated_chunks": [
                {"text": "c", "chapter_number": 5, "position": 1},
                {"text": "a", "chapter_number": 3, "position": 2},
                {"text": "b", "chapter_number": 3, "position": 5},
            ],
        }
        result = await temporal_sort(state)
        chunks = result["deduplicated_chunks"]
        assert chunks[0]["text"] == "a"
        assert chunks[1]["text"] == "b"
        assert chunks[2]["text"] == "c"

    @pytest.mark.asyncio
    async def test_handles_missing_position(self):
        from app.agents.chat.nodes.temporal_sort import temporal_sort

        state: dict[str, Any] = {
            "deduplicated_chunks": [
                {"text": "b", "chapter_number": 5},
                {"text": "a", "chapter_number": 3},
            ],
        }
        result = await temporal_sort(state)
        assert result["deduplicated_chunks"][0]["text"] == "a"

    @pytest.mark.asyncio
    async def test_empty_chunks(self):
        from app.agents.chat.nodes.temporal_sort import temporal_sort

        state: dict[str, Any] = {"deduplicated_chunks": []}
        result = await temporal_sort(state)
        assert result["deduplicated_chunks"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_temporal_sort.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement temporal_sort node**

```python
"""Sort chunks by (chapter_number, position) for timeline queries."""
from __future__ import annotations

from typing import Any


async def temporal_sort(state: dict[str, Any]) -> dict[str, Any]:
    """Sort deduplicated chunks in chronological order."""
    chunks = state.get("deduplicated_chunks", [])
    sorted_chunks = sorted(
        chunks,
        key=lambda c: (c.get("chapter_number", 0), c.get("position", 0)),
    )
    return {"deduplicated_chunks": sorted_chunks}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_temporal_sort.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/temporal_sort.py backend/tests/test_temporal_sort.py
git commit -m "feat(chat): implement temporal_sort node for timeline queries"
```

---

## Chunk 5: Generation & Faithfulness (Tasks 14-16)

### Task 14: Upgrade generate with structured output + fiction-tuned prompts

**Files:**
- Modify: `backend/app/agents/chat/nodes/generate.py`
- Modify: `backend/app/agents/chat/prompts.py`
- Modify: `backend/app/schemas/chat.py`
- Test: `backend/tests/test_generate_structured.py`

- [ ] **Step 1: Add GenerationOutput and ClaimCitation schemas**

In `backend/app/schemas/chat.py`, read the file first, then add (keep existing schemas):

```python
class ClaimCitation(BaseModel):
    """A claim-level citation linking answer text to source."""
    chapter: int
    position: int | None = None
    claim: str
    source_span: str = ""


class GenerationOutput(BaseModel):
    """Structured generation output."""
    answer: str
    citations: list[ClaimCitation] = []
    entities_mentioned: list[str] = []
    confidence: float = 0.0
```

Also add to existing `ChatResponse`:

```python
confidence: float = 0.0
claim_citations: list[ClaimCitation] = []
```

- [ ] **Step 2: Write failing test for structured generation**

```python
"""Tests for structured generation output."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PATCH_TARGET = "app.agents.chat.nodes.generate.get_langchain_llm"


class TestStructuredGenerate:
    @pytest.mark.asyncio
    async def test_returns_generation_output_dict(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="""{
                "answer": "Jake is a level 42 warrior.",
                "citations": [{"chapter": 3, "claim": "Jake is a warrior", "source_span": "Jake drew his sword"}],
                "entities_mentioned": ["Jake"]
            }""",
        )
        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.generate import generate_answer

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "route": "entity_qa",
                "context": "Chapter 3: Jake drew his sword.",
                "book_id": "book-1",
                "deduplicated_chunks": [
                    {"text": "Jake drew his sword.", "chapter_number": 3},
                ],
            }
            result = await generate_answer(state)
            assert "generation_output" in result
            output = result["generation_output"]
            assert output["answer"] == "Jake is a level 42 warrior."
            assert len(output["citations"]) == 1
            assert result["generation"] == output["answer"]
            assert result["turn_count"] == 1

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="Jake is a warrior from chapter 3.",
        )
        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.generate import generate_answer

            state: dict[str, Any] = {
                "query": "Who is Jake?",
                "route": "entity_qa",
                "context": "Context here.",
                "book_id": "book-1",
                "deduplicated_chunks": [],
            }
            result = await generate_answer(state)
            assert result["generation"] == "Jake is a warrior from chapter 3."
            assert result["generation_output"]["answer"] == result["generation"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_generate_structured.py -v`
Expected: FAIL — no generation_output in return.

- [ ] **Step 4: Update fiction-tuned generation prompt in prompts.py**

Read `backend/app/agents/chat/prompts.py`, then replace `GENERATOR_SYSTEM`:

```python
GENERATOR_SYSTEM = """\
You are an expert fiction novel Q&A assistant. Answer using ONLY the provided context.

Rules:
- Cite sources as [Ch.N, §P] where N=chapter, P=paragraph position
- Be aware of character aliases and nicknames
- Understand magic system mechanics (stats, skills, classes, levels)
- Handle timeline ambiguity (flashbacks, time skips)
- For LitRPG: interpret blue boxes, stat changes, level progression
- Never reveal information beyond the reader's current chapter
{spoiler_guard}

Return a JSON object:
{{
  "answer": "<your answer with [Ch.N, §P] citations>",
  "citations": [{{"chapter": N, "position": P, "claim": "<claim>", "source_span": "<exact source text>"}}],
  "entities_mentioned": ["<entity names mentioned in your answer>"]
}}

If you cannot produce valid JSON, just return your answer as plain text.
"""
```

- [ ] **Step 5: Modify generate_answer**

In `backend/app/agents/chat/nodes/generate.py`:
- Use `settings.llm_generation` instead of `settings.llm_chat`
- Change `route == "direct"` check to `route == "conversational"`
- Parse response as JSON into `GenerationOutput` model
- Fallback to plain text if JSON parse fails
- Return both `generation_output` dict and `generation` string
- Add `turn_count: 1` to return dict

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_generate_structured.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/chat/nodes/generate.py backend/app/agents/chat/prompts.py backend/app/schemas/chat.py backend/tests/test_generate_structured.py
git commit -m "feat(chat): structured generation output with fiction-tuned prompts"
```

---

### Task 15: Implement generate_cot node

**Files:**
- Create: `backend/app/agents/chat/nodes/generate_cot.py`
- Modify: `backend/app/agents/chat/prompts.py`
- Test: `backend/tests/test_generate_cot.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for chain-of-thought generation."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PATCH_TARGET = "app.agents.chat.nodes.generate_cot.get_langchain_llm"


class TestGenerateCoT:
    @pytest.mark.asyncio
    async def test_generates_with_cot_prompt(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="""{
                "reasoning": "Step 1: Jake leveled up.",
                "answer": "Jake progressed from level 10 to 42.",
                "citations": [],
                "entities_mentioned": ["Jake"]
            }""",
        )
        with patch(PATCH_TARGET, return_value=mock_llm):
            from app.agents.chat.nodes.generate_cot import generate_cot

            state: dict[str, Any] = {
                "query": "How did Jake progress?",
                "route": "timeline_qa",
                "context": "Context here.",
                "book_id": "book-1",
                "deduplicated_chunks": [],
            }
            result = await generate_cot(state)
            assert "generation_output" in result
            assert result["generation"] == "Jake progressed from level 10 to 42."
            assert result["turn_count"] == 1  # Must increment!
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_generate_cot.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Add CoT prompt to prompts.py**

Append to prompts.py:

```python
GENERATOR_COT_SYSTEM = """\
You are an expert fiction novel analyst. Answer complex questions using step-by-step reasoning.

Rules:
- Think through the problem step by step before giving your final answer
- Cite sources as [Ch.N, §P]
- For timeline questions: establish chronological order first
- For analytical questions: identify relevant factors, then synthesize
{spoiler_guard}

Return a JSON object:
{{
  "reasoning": "<your step-by-step reasoning>",
  "answer": "<your final answer with [Ch.N, §P] citations>",
  "citations": [{{"chapter": N, "position": P, "claim": "<claim>", "source_span": "<source>"}}],
  "entities_mentioned": ["<entity names>"]
}}
"""
```

- [ ] **Step 4: Implement generate_cot node**

Mirror `generate_answer` structure but use `GENERATOR_COT_SYSTEM` prompt. **IMPORTANT:** Include `"turn_count": 1` in the return dict so the `Annotated[int, operator.add]` field increments.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_generate_cot.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/chat/nodes/generate_cot.py backend/tests/test_generate_cot.py backend/app/agents/chat/prompts.py
git commit -m "feat(chat): implement chain-of-thought generation for complex queries"
```

---

### Task 16: Implement nli_check (DeBERTa NLI faithfulness)

**Files:**
- Create: `backend/app/agents/chat/nodes/nli_check.py`
- Test: `backend/tests/test_nli_check.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for NLI-based faithfulness check."""
import re
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestNLICheck:
    @pytest.mark.asyncio
    async def test_entailed_claims_pass(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.1, 0.8, 0.1]])

        with patch(
            "app.agents.chat.nodes.nli_check.get_nli_model",
            return_value=mock_model,
        ):
            from app.agents.chat.nodes.nli_check import nli_check

            state: dict[str, Any] = {
                "generation": "Jake is a warrior of great skill.",
                "context": "Jake drew his sword. He was a warrior.",
                "route": "entity_qa",
            }
            result = await nli_check(state)
            assert result["faithfulness_score"] > 0.6
            assert result["faithfulness_passed"] is True

    @pytest.mark.asyncio
    async def test_contradicted_claims_fail(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.8, 0.1, 0.1]])

        with patch(
            "app.agents.chat.nodes.nli_check.get_nli_model",
            return_value=mock_model,
        ):
            from app.agents.chat.nodes.nli_check import nli_check

            state: dict[str, Any] = {
                "generation": "Jake is a mage who uses fire spells.",
                "context": "Jake is a warrior.",
                "route": "entity_qa",
            }
            result = await nli_check(state)
            assert result["faithfulness_passed"] is False

    @pytest.mark.asyncio
    async def test_adaptive_threshold_factual_strict(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[0.1, 0.1, 0.8]])

        with patch(
            "app.agents.chat.nodes.nli_check.get_nli_model",
            return_value=mock_model,
        ):
            from app.agents.chat.nodes.nli_check import nli_check

            state: dict[str, Any] = {
                "generation": "Level 42 warrior with fire skills.",
                "context": "Context.",
                "route": "factual_lookup",
            }
            result = await nli_check(state)
            assert result["faithfulness_passed"] is False  # 0.5 < 0.8 threshold

    @pytest.mark.asyncio
    async def test_conversational_skips_check(self):
        from app.agents.chat.nodes.nli_check import nli_check

        state: dict[str, Any] = {
            "generation": "Hello! How can I help?",
            "context": "",
            "route": "conversational",
        }
        result = await nli_check(state)
        assert result["faithfulness_passed"] is True
        assert result["faithfulness_score"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_nli_check.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement nli_check node**

```python
"""NLI-based faithfulness check using DeBERTa-v3-large."""
from __future__ import annotations

import asyncio
import re
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.llm.local_models import get_nli_model

logger = get_logger(__name__)

ROUTE_THRESHOLDS = {
    "factual_lookup": 0.8,
    "entity_qa": 0.7,
    "relationship_qa": 0.7,
    "timeline_qa": 0.6,
    "analytical": 0.5,
    "conversational": 0.0,
}


def _split_claims(text: str) -> list[str]:
    """Split answer into claims (sentences), stripping citation markers."""
    clean = re.sub(r'\[Ch\.\d+(?:,\s*§\d+)?\]', '', text)
    sentences = re.split(r'(?<=[.!?])\s+', clean.strip())
    return [s for s in sentences if len(s) > 10]


def _score_claim(logits: np.ndarray) -> float:
    """Convert NLI logits [contradiction, entailment, neutral] to score."""
    probs = np.exp(logits) / np.sum(np.exp(logits))
    return float(probs[1] * 1.0 + probs[2] * 0.5 + probs[0] * 0.0)


async def nli_check(state: dict[str, Any]) -> dict[str, Any]:
    """Check faithfulness via NLI entailment per claim."""
    route = state.get("route", "entity_qa")
    generation = state.get("generation", "")
    context = state.get("context", "")

    if route == "conversational" or not context:
        return {"faithfulness_score": 1.0, "faithfulness_passed": True}

    claims = _split_claims(generation)
    if not claims:
        return {"faithfulness_score": 1.0, "faithfulness_passed": True}

    model = get_nli_model()
    pairs = [(claim, context) for claim in claims]
    logits = await asyncio.to_thread(model.predict, pairs)

    scores = [_score_claim(l) for l in logits]
    avg_score = float(np.mean(scores))
    has_contradiction = any(np.argmax(l) == 0 for l in logits)

    threshold = ROUTE_THRESHOLDS.get(route, 0.7)
    passed = avg_score >= threshold and not has_contradiction

    logger.info(
        "nli_check",
        score=round(avg_score, 3),
        claims=len(claims),
        threshold=threshold,
        passed=passed,
        route=route,
    )

    return {"faithfulness_score": avg_score, "faithfulness_passed": passed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_nli_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/nli_check.py backend/tests/test_nli_check.py
git commit -m "feat(chat): implement NLI-based faithfulness check with DeBERTa"
```

---

## Chunk 6: Graph Wiring & Service (Tasks 18-20)

### Task 18: Rewire graph with 6-route topology + migrate old tests

**Files:**
- Modify: `backend/app/agents/chat/graph.py`
- Modify: `backend/app/agents/chat/nodes/__init__.py`
- Test: `backend/tests/test_graph_6routes.py`
- Modify (migration): `backend/tests/test_chat_graph.py`, `backend/tests/test_chat_data_driven.py`, `backend/tests/test_chat_nodes.py`, `backend/tests/test_rerank_kg_nodes.py`, `backend/tests/test_chat_service_refactored.py`

**CRITICAL:** This task must update ALL files referencing old routes (`kg_query`, `hybrid_rag`, `direct`). Run a grep first: `grep -rn "hybrid_rag\|\"direct\"\|kg_query" backend/tests/ backend/app/agents/chat/`

- [ ] **Step 1: Write test for new graph structure**

```python
"""Tests for 6-route graph topology."""
from unittest.mock import MagicMock


class TestGraphTopology:
    def test_graph_has_all_new_nodes(self):
        from app.agents.chat.graph import build_chat_graph

        repo = MagicMock()
        embedder = MagicMock()
        builder = build_chat_graph(repo=repo, embedder=embedder)

        expected_nodes = [
            "load_memory", "router", "query_transform", "hyde_expand",
            "retrieve", "rerank", "deduplicate_chunks",
            "context_assembly", "generate", "generate_cot",
            "nli_check", "rewrite", "kg_query",
            "temporal_sort", "summarize_memory",
        ]
        for node in expected_nodes:
            assert node in builder.nodes, f"Missing node: {node}"

    def test_graph_compiles(self):
        from app.agents.chat.graph import build_chat_graph

        repo = MagicMock()
        embedder = MagicMock()
        builder = build_chat_graph(repo=repo, embedder=embedder)
        compiled = builder.compile()
        assert compiled is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_6routes.py -v`
Expected: FAIL — old graph has 9 nodes.

- [ ] **Step 3: Update __init__.py exports**

In `backend/app/agents/chat/nodes/__init__.py`, add all new node exports.

- [ ] **Step 4: Rewrite graph.py with 6-route topology**

Implement the topology from the spec. Key routing functions:

```python
def _route_after_router(state):
    route = state.get("route", "entity_qa")
    if route == "factual_lookup":
        return "kg_query"
    if route == "conversational":
        return "generate"
    return "query_transform"

def _route_after_dedup(state):
    if state.get("route") == "timeline_qa":
        return "temporal_sort"
    return "context_assembly"

def _route_to_generator(state):
    if state.get("route") in ("timeline_qa", "analytical"):
        return "generate_cot"
    return "generate"

def _route_after_nli(state):
    if state.get("faithfulness_passed", True):
        tc = state.get("turn_count", 0)
        if tc > 0 and tc % 5 == 0:
            return "summarize_memory"
        return END
    if state.get("retries", 0) >= MAX_RETRIES:
        return END
    return "rewrite"
```

The node wrapper for `hybrid_retrieve` must now batch-embed all query variants + HyDE:

```python
async def _retrieve_node(state):
    queries = state.get("transformed_queries", [state["query"]])
    hyde = state.get("hyde_document", "")
    embed_texts = list(queries)
    if hyde:
        embed_texts.append(hyde)
    embeddings = await embedder.embed_texts(embed_texts)

    # First embedding is the primary, rest are extras
    primary = embeddings[0]
    extras = embeddings[1:] if len(embeddings) > 1 else None

    results = await hybrid_retrieve(
        repo, state["query"], primary, state["book_id"],
        extra_bm25_queries=queries[1:] if len(queries) > 1 else None,
        extra_dense_embeddings=extras,
        max_chapter=state.get("max_chapter"),
    )
    return {"fused_results": results}
```

- [ ] **Step 5: Grep and migrate all old route references**

Search all test files for old routes and update:
- `"hybrid_rag"` → `"entity_qa"` (or appropriate new route)
- `"direct"` → `"conversational"`
- `"kg_query"` → `"factual_lookup"`

Files to update (run `grep -rn "hybrid_rag\|\"direct\"\|\"kg_query\"" backend/` to find all):
- `backend/tests/test_chat_graph.py`
- `backend/tests/test_chat_data_driven.py`
- `backend/tests/test_chat_nodes.py`
- `backend/tests/test_rerank_kg_nodes.py`
- `backend/tests/test_chat_service_refactored.py`
- `backend/app/agents/chat/nodes/kg_query.py` (fallback route)

- [ ] **Step 6: Run full test suite**

Run: `cd backend && python -m pytest tests/ -x -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/chat/ backend/tests/
git commit -m "feat(chat): rewire graph with 6-route adaptive topology + migrate tests"
```

---

### Task 20: Update ChatService to map generation_output to ChatResponse

**Files:**
- Modify: `backend/app/services/chat_service.py`
- Test: `backend/tests/test_chat_service_mapping.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for ChatService generation_output mapping."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestChatServiceMapping:
    @pytest.mark.asyncio
    async def test_maps_generation_output_to_response(self):
        from app.services.chat_service import ChatService

        ChatService._compiled_graph = None
        ChatService._shared_driver = None
        ChatService._shared_repo = None

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {
            "generation": "Jake is a warrior.",
            "generation_output": {
                "answer": "Jake is a warrior.",
                "citations": [
                    {"chapter": 3, "position": 1, "claim": "warrior",
                     "source_span": "Jake drew his sword"},
                ],
                "entities_mentioned": ["Jake"],
                "confidence": 0.0,
            },
            "faithfulness_score": 0.85,
            "reranked_chunks": [{"text": "Jake drew his sword."}],
            "kg_entities": [],
            "citations": [{"chapter": 3}],
        }

        mock_driver = MagicMock()

        with patch(
            "app.services.chat_service.build_chat_graph",
        ) as mock_build:
            mock_builder = MagicMock()
            mock_builder.compile.return_value = mock_graph
            mock_build.return_value = mock_builder

            service = ChatService(mock_driver)
            result = await service.query("Who is Jake?", "book-1")

        assert result.answer == "Jake is a warrior."
        assert result.confidence == 0.85
        assert len(result.claim_citations) == 1
        assert result.claim_citations[0].claim == "warrior"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_service_mapping.py -v`
Expected: FAIL

- [ ] **Step 3: Update ChatService.query() mapping**

Read `backend/app/services/chat_service.py`. Update the result mapping:
- Read `generation_output` dict from graph result
- Map `faithfulness_score` to `confidence`
- Map `generation_output["citations"]` to `claim_citations` (using ClaimCitation schema)
- Keep backward compatibility with existing fields

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_service_mapping.py -v`
Expected: PASS

- [ ] **Step 5: Run full chat test suite**

Run: `cd backend && python -m pytest tests/ -k "chat" -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/chat_service.py backend/app/schemas/chat.py backend/tests/test_chat_service_mapping.py
git commit -m "feat(chat): map generation_output and NLI confidence to ChatResponse"
```

---

## Chunk 7: Feedback System (Tasks 21-23)

### Task 21: Create chat_feedback PostgreSQL table

**Files:**
- Create: `scripts/init_postgres.sql`
- Modify: `scripts/init_postgres.sh`

- [ ] **Step 1: Create init_postgres.sql**

```sql
-- Chat feedback table for RLHF data collection
CREATE TABLE IF NOT EXISTS chat_feedback (
  id SERIAL PRIMARY KEY,
  message_id TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  book_id TEXT,
  query TEXT,
  answer TEXT,
  rating INTEGER CHECK (rating IN (-1, 1)),
  comment TEXT,
  faithfulness_score FLOAT,
  route TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_thread ON chat_feedback(thread_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON chat_feedback(created_at DESC);
```

- [ ] **Step 2: Update init_postgres.sh to run SQL file**

Read `scripts/init_postgres.sh` first, then add a line to execute the new SQL file.

- [ ] **Step 3: Commit**

```bash
git add scripts/init_postgres.sql scripts/init_postgres.sh
git commit -m "feat(db): add chat_feedback PostgreSQL table DDL"
```

---

### Task 22: Add feedback API endpoints

**Files:**
- Create: `backend/app/schemas/feedback.py`
- Create: `backend/app/api/routes/feedback.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_feedback_api.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for chat feedback API schemas and route registration."""
from typing import Literal

import pytest
from pydantic import ValidationError


class TestFeedbackSchemas:
    def test_request_valid(self):
        from app.schemas.feedback import FeedbackRequest

        req = FeedbackRequest(
            message_id="msg-1",
            thread_id="thread-1",
            rating=1,
        )
        assert req.rating == 1

    def test_request_valid_negative(self):
        from app.schemas.feedback import FeedbackRequest

        req = FeedbackRequest(
            message_id="msg-1",
            thread_id="thread-1",
            rating=-1,
        )
        assert req.rating == -1

    def test_request_rejects_zero_rating(self):
        from app.schemas.feedback import FeedbackRequest

        with pytest.raises(ValidationError):
            FeedbackRequest(
                message_id="msg-1",
                thread_id="thread-1",
                rating=0,
            )

    def test_request_rejects_invalid_rating(self):
        from app.schemas.feedback import FeedbackRequest

        with pytest.raises(ValidationError):
            FeedbackRequest(
                message_id="msg-1",
                thread_id="thread-1",
                rating=5,
            )

    def test_response_shape(self):
        from app.schemas.feedback import FeedbackResponse

        resp = FeedbackResponse(id=1, status="saved")
        assert resp.id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_feedback_api.py -v`
Expected: FAIL — schemas don't exist.

- [ ] **Step 3: Create feedback schemas**

```python
"""Pydantic schemas for chat feedback."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    """Chat feedback submission."""
    message_id: str
    thread_id: str
    book_id: str | None = None
    query: str | None = None
    answer: str | None = None
    rating: Literal[-1, 1]  # Only -1 or 1, matches DB constraint
    comment: str | None = None
    faithfulness_score: float | None = None
    route: str | None = None


class FeedbackResponse(BaseModel):
    """Feedback submission result."""
    id: int
    status: str = "saved"


class FeedbackListItem(BaseModel):
    """Single feedback item for admin listing."""
    id: int
    message_id: str
    thread_id: str
    rating: int
    route: str | None = None
    faithfulness_score: float | None = None
    created_at: str
```

- [ ] **Step 4: Create feedback route**

```python
"""Chat feedback API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.auth import require_admin, require_auth
from app.schemas.feedback import (
    FeedbackListItem,
    FeedbackRequest,
    FeedbackResponse,
)

router = APIRouter(prefix="/chat/feedback", tags=["feedback"])


@router.post("", dependencies=[Depends(require_auth)])
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
) -> FeedbackResponse:
    """Submit feedback (thumbs up/down) for a chat message."""
    pg_pool = request.app.state.pg_pool
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO chat_feedback
                (message_id, thread_id, book_id, query, answer,
                 rating, comment, faithfulness_score, route)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            body.message_id, body.thread_id, body.book_id,
            body.query, body.answer, body.rating, body.comment,
            body.faithfulness_score, body.route,
        )
    return FeedbackResponse(id=row["id"])


@router.get("", dependencies=[Depends(require_admin)])
async def list_feedback(
    request: Request,
    limit: int = 50,
) -> list[FeedbackListItem]:
    """List recent feedback (admin only)."""
    pg_pool = request.app.state.pg_pool
    async with pg_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, message_id, thread_id, rating, route,
                   faithfulness_score, created_at::text
            FROM chat_feedback
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [
        FeedbackListItem(
            id=r["id"], message_id=r["message_id"],
            thread_id=r["thread_id"], rating=r["rating"],
            route=r["route"], faithfulness_score=r["faithfulness_score"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
```

- [ ] **Step 5: Register route in main.py**

Read `backend/app/main.py`, then add:

```python
from app.api.routes.feedback import router as feedback_router
app.include_router(feedback_router, prefix="/api")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_feedback_api.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/feedback.py backend/app/api/routes/feedback.py backend/app/main.py backend/tests/test_feedback_api.py
git commit -m "feat(api): add chat feedback endpoints (POST + GET admin)"
```

---

## Chunk 8: Frontend (Tasks 24-28)

### Task 24: Source streaming display (collapsible panel)

**Files:**
- Create: `frontend/components/chat/source-panel.tsx`
- Modify: `frontend/hooks/use-chat-stream.ts`

- [ ] **Step 1: Create source-panel.tsx**

```tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface SourceChunk {
  text: string;
  chapter_number?: number;
  position?: number;
  relevance_score?: number;
}

interface SourcePanelProps {
  chunks: SourceChunk[];
}

export function SourcePanel({ chunks }: SourcePanelProps) {
  const [open, setOpen] = useState(false);

  if (!chunks.length) return null;

  return (
    <div className="mt-2 rounded-md border border-border/50 bg-muted/30">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {chunks.length} source{chunks.length > 1 ? "s" : ""} used
      </button>
      {open && (
        <div className="space-y-2 px-3 pb-3">
          {chunks.map((chunk, i) => (
            <div key={i} className="rounded bg-background p-2 text-xs">
              {chunk.chapter_number && (
                <span className="font-medium text-primary">
                  Ch.{chunk.chapter_number}
                  {chunk.position != null && `, §${chunk.position}`}
                </span>
              )}
              {chunk.relevance_score != null && (
                <span className="ml-2 text-muted-foreground">
                  ({(chunk.relevance_score * 100).toFixed(0)}%)
                </span>
              )}
              <p className="mt-1 text-muted-foreground line-clamp-3">{chunk.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update use-chat-stream.ts to handle sources event**

Read `frontend/hooks/use-chat-stream.ts`. Add `sources` and `confidence` to `ChatMessage` interface. Handle the `sources` SSE event to populate them.

- [ ] **Step 3: Integrate SourcePanel into chat page**

Render `<SourcePanel chunks={msg.sources ?? []} />` after assistant messages.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/chat/source-panel.tsx frontend/hooks/use-chat-stream.ts frontend/app/\(reader\)/chat/page.tsx
git commit -m "feat(frontend): add collapsible source panel for chat messages"
```

---

### Task 25: Citation highlight component

**Files:**
- Create: `frontend/components/chat/citation-highlight.tsx`

- [ ] **Step 1: Create citation-highlight.tsx**

```tsx
"use client";

interface CitationHighlightProps {
  text: string;
}

export function CitationHighlight({ text }: CitationHighlightProps) {
  const parts = text.split(/(\[Ch\.\d+(?:,\s*§\d+)?\])/g);

  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/^\[Ch\.(\d+)(?:,\s*§(\d+))?\]$/);
        if (match) {
          return (
            <span
              key={i}
              className="cursor-help rounded bg-primary/10 px-1 text-primary font-medium text-xs"
              title={`Chapter ${match[1]}${match[2] ? `, paragraph ${match[2]}` : ""}`}
            >
              {part}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
}
```

- [ ] **Step 2: Use CitationHighlight in assistant message rendering**

Replace plain text rendering of assistant messages with `<CitationHighlight text={msg.content} />`.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/chat/citation-highlight.tsx frontend/app/\(reader\)/chat/page.tsx
git commit -m "feat(frontend): add citation highlight component for [Ch.N, §P]"
```

---

### Task 26: Feedback thumbs up/down buttons

**Files:**
- Create: `frontend/components/chat/feedback-buttons.tsx`
- Modify: `frontend/lib/api/chat.ts`

- [ ] **Step 1: Add feedback API call to chat.ts**

Read `frontend/lib/api/chat.ts`. Use `apiFetch` (NOT raw `fetch` with `API_BASE`):

```typescript
export async function submitFeedback(data: {
  message_id: string;
  thread_id: string;
  rating: 1 | -1;
  book_id?: string;
  query?: string;
  answer?: string;
  comment?: string;
}): Promise<{ id: number; status: string }> {
  return apiFetch("/chat/feedback", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
```

- [ ] **Step 2: Create feedback-buttons.tsx**

```tsx
"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { submitFeedback } from "@/lib/api/chat";

interface FeedbackButtonsProps {
  messageId: string;
  threadId: string;
  bookId?: string;
}

export function FeedbackButtons({ messageId, threadId, bookId }: FeedbackButtonsProps) {
  const [rating, setRating] = useState<1 | -1 | null>(null);

  const handleFeedback = async (value: 1 | -1) => {
    if (rating !== null) return;
    setRating(value);
    try {
      await submitFeedback({
        message_id: messageId,
        thread_id: threadId,
        rating: value,
        book_id: bookId,
      });
    } catch {
      setRating(null);
    }
  };

  return (
    <div className="flex items-center gap-1 mt-1">
      <button
        onClick={() => handleFeedback(1)}
        className={`p-1 rounded hover:bg-muted ${rating === 1 ? "text-green-500" : "text-muted-foreground"}`}
        disabled={rating !== null}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => handleFeedback(-1)}
        className={`p-1 rounded hover:bg-muted ${rating === -1 ? "text-red-500" : "text-muted-foreground"}`}
        disabled={rating !== null}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Integrate into chat page**

Add `<FeedbackButtons>` after each assistant message.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/chat/feedback-buttons.tsx frontend/lib/api/chat.ts frontend/app/\(reader\)/chat/page.tsx
git commit -m "feat(frontend): add feedback thumbs up/down buttons"
```

---

### Task 27: Thread history sidebar

**Files:**
- Create: `frontend/components/chat/thread-sidebar.tsx`
- Modify: `frontend/stores/chat-store.ts`

- [ ] **Step 1: Update chat-store.ts with updateThreadTitle**

Read `frontend/stores/chat-store.ts`, then add:

```typescript
updateThreadTitle: (id: string, title: string) => void;
```

- [ ] **Step 2: Create thread-sidebar.tsx**

```tsx
"use client";

import { useChatStore } from "@/stores/chat-store";
import { Trash2, MessageSquare } from "lucide-react";

export function ThreadSidebar() {
  const { threads, threadId, setThreadId, removeThread } = useChatStore();

  return (
    <div className="flex h-full w-64 flex-col border-r bg-muted/20">
      <div className="flex items-center justify-between p-3 border-b">
        <h3 className="text-sm font-medium">Conversations</h3>
        <button
          onClick={() => setThreadId(null)}
          className="text-xs text-primary hover:underline"
        >
          New
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads.map((t) => (
          <div
            key={t.id}
            className={`flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-muted/50 ${
              t.id === threadId ? "bg-muted" : ""
            }`}
            onClick={() => setThreadId(t.id)}
          >
            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="flex-1 min-w-0">
              <p className="text-sm truncate">{t.title || "Untitled"}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(t.updatedAt).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeThread(t.id);
              }}
              className="p-1 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Integrate into chat page layout**

Add `<ThreadSidebar />` to the left side of the chat page.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/chat/thread-sidebar.tsx frontend/stores/chat-store.ts frontend/app/\(reader\)/chat/page.tsx
git commit -m "feat(frontend): add thread history sidebar"
```

---

### Task 28: Confidence indicator badge

**Files:**
- Create: `frontend/components/chat/confidence-badge.tsx`

- [ ] **Step 1: Create confidence-badge.tsx**

```tsx
interface ConfidenceBadgeProps {
  score: number;
}

export function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  let color: string;
  let label: string;

  if (score >= 0.8) {
    color = "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
    label = "High confidence";
  } else if (score >= 0.5) {
    color = "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400";
    label = "Medium confidence";
  } else {
    color = "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";
    label = "Low confidence";
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
      title={`Faithfulness score: ${(score * 100).toFixed(0)}%`}
    >
      {label}
    </span>
  );
}
```

- [ ] **Step 2: Integrate into assistant message rendering**

Show `<ConfidenceBadge score={msg.confidence} />` next to assistant messages when confidence is available.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/chat/confidence-badge.tsx frontend/app/\(reader\)/chat/page.tsx
git commit -m "feat(frontend): add confidence indicator badge"
```

---

## Final Verification

- [x] **Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -x -v
```
Expected: All tests pass.

- [x] **Step 2: Run ruff linter**

```bash
cd backend && python -m ruff check . --fix && python -m ruff format .
```
Expected: Clean.

- [x] **Step 3: Run frontend build**

```bash
cd frontend && npm run build
```
Expected: Build succeeds.

- [x] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "chore: fix lint and build issues from SOTA chat pipeline"
```
