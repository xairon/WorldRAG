# Remaining Features Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire PostgreSQL checkpointing for multi-turn chat, build the Reader LangGraph agent for guided chapter Q&A, connect the chat frontend to the backend with thread persistence, and ensure the Cohere reranker is production-ready.

**Architecture:** LangGraph `AsyncPostgresSaver` wired through FastAPI lifespan into `ChatService.compile()` enables real multi-turn conversations. The Reader agent is a lightweight LangGraph graph that answers within-chapter questions using entity annotations + paragraph context. The frontend adds `thread_id` management via Zustand store and localStorage persistence.

**Tech Stack:** LangGraph 0.3+, langgraph-checkpoint-postgres, asyncpg, psycopg, FastAPI lifespan, Next.js 16, React 19, Zustand, shadcn/ui, Tailwind CSS.

---

## Chunk 1: PostgreSQL Checkpointing

### Task 1: Wire AsyncPostgresSaver into FastAPI Lifespan

**Files:**
- Modify: `backend/app/main.py:109-120` (pg_pool section)
- Create: `backend/app/core/checkpointer.py`
- Test: `backend/tests/test_checkpointer.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_checkpointer.py
"""Tests for the LangGraph checkpointer factory."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_create_checkpointer_returns_saver():
    """Factory returns an AsyncPostgresSaver when given a valid URI."""
    with patch(
        "app.core.checkpointer.AsyncPostgresSaver.from_conn_string",
        new_callable=AsyncMock,
    ) as mock_from_conn:
        mock_saver = MagicMock()
        mock_from_conn.return_value = mock_saver

        from app.core.checkpointer import create_checkpointer

        saver = await create_checkpointer("postgresql://u:p@localhost:5432/db")
        mock_from_conn.assert_called_once_with("postgresql://u:p@localhost:5432/db")
        assert saver is mock_saver


@pytest.mark.asyncio
async def test_create_checkpointer_returns_none_on_empty_uri():
    """Factory returns None when URI is empty."""
    from app.core.checkpointer import create_checkpointer

    saver = await create_checkpointer("")
    assert saver is None


@pytest.mark.asyncio
async def test_create_checkpointer_returns_none_on_failure():
    """Factory returns None and logs warning on connection error."""
    with patch(
        "app.core.checkpointer.AsyncPostgresSaver.from_conn_string",
        new_callable=AsyncMock,
        side_effect=ConnectionError("refused"),
    ):
        from app.core.checkpointer import create_checkpointer

        saver = await create_checkpointer("postgresql://bad:bad@nowhere:5432/db")
        assert saver is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_checkpointer.py -x -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.checkpointer'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/core/checkpointer.py
"""LangGraph checkpointer factory for PostgreSQL persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as _Saver

from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_checkpointer(postgres_uri: str) -> _Saver | None:
    """Create and set up an AsyncPostgresSaver, or None on failure.

    Calls ``await saver.setup()`` to ensure the checkpoint tables exist.
    Returns None (with a warning log) if the URI is empty or connection fails.
    """
    if not postgres_uri:
        return None

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver.from_conn_string(postgres_uri)
        await saver.setup()
        logger.info("checkpointer_ready")
        return saver
    except Exception as exc:
        logger.warning("checkpointer_creation_failed", error=type(exc).__name__)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_checkpointer.py -x -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/checkpointer.py backend/tests/test_checkpointer.py
git commit -m "feat(checkpointer): add factory for AsyncPostgresSaver"
```

### Task 2: Integrate Checkpointer into Lifespan and ChatService

**Files:**
- Modify: `backend/app/main.py:109-120,173`
- Modify: `backend/app/services/chat_service.py:112-141`
- Modify: `backend/app/agents/chat/graph.py:64-68`
- Test: `backend/tests/test_chat_service.py` (add checkpointer test)

- [ ] **Step 1: Write the failing test**

```python
# Add to backend/tests/test_chat_service.py

@pytest.mark.asyncio
async def test_graph_compiled_with_checkpointer(mock_driver, mock_build_graph):
    """When a checkpointer is provided, graph.compile() receives it."""
    from unittest.mock import MagicMock

    ChatService._compiled_graph = None
    ChatService._shared_repo = None
    ChatService._shared_embedder = None
    ChatService._shared_driver = None

    mock_checkpointer = MagicMock()

    svc = ChatService(mock_driver, checkpointer=mock_checkpointer)
    # The builder returned by build_chat_graph has .compile() called
    mock_build_graph.return_value.compile.assert_called_once_with(
        checkpointer=mock_checkpointer
    )
    assert svc._graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_chat_service.py::test_graph_compiled_with_checkpointer -x -v`
Expected: FAIL — ChatService.__init__ does not accept `checkpointer` parameter

- [ ] **Step 3: Implement changes**

**graph.py** — no change needed (builder is compiled externally in ChatService)

**chat_service.py** — accept optional checkpointer:

```python
# Change __init__ signature and compile() call:

class ChatService:
    _compiled_graph: Any = None
    _shared_repo: Any = None
    _shared_embedder: Any = None
    _shared_driver: Any = None
    _shared_checkpointer: Any = None  # LangGraph checkpointer

    def __init__(
        self,
        driver: AsyncDriver,
        checkpointer: Any = None,
    ) -> None:
        self.repo = Neo4jRepository(driver)

        # Invalidate cached graph if driver changed (N5 fix)
        if ChatService._shared_driver is not None and ChatService._shared_driver is not driver:
            logger.info("chat_service_driver_changed_recompiling")
            ChatService._compiled_graph = None
            ChatService._shared_repo = None
            ChatService._shared_embedder = None

        if ChatService._compiled_graph is None:
            self.embedder = LocalEmbedder()
            ChatService._shared_repo = self.repo
            ChatService._shared_embedder = self.embedder
            ChatService._shared_driver = driver
            ChatService._shared_checkpointer = checkpointer
            builder = build_chat_graph(
                repo=self.repo,
                embedder=self.embedder,
            )
            ChatService._compiled_graph = builder.compile(
                checkpointer=checkpointer,
            )
        else:
            self.embedder = ChatService._shared_embedder

        self._graph = ChatService._compiled_graph
```

**main.py** — create checkpointer in lifespan, store on app.state:

```python
# After pg_pool creation (line ~120), add:
from app.core.checkpointer import create_checkpointer

checkpointer = None
if pg_pool is not None:
    checkpointer = await create_checkpointer(settings.postgres_uri)
app.state.checkpointer = checkpointer

# In shutdown (after pg_pool.close), add:
# Checkpointer cleanup is handled by pg_pool.close()
```

**dependencies.py** — expose checkpointer:

```python
def get_checkpointer(request: Request):
    return getattr(request.app.state, "checkpointer", None)
```

**routes/chat.py** — pass checkpointer to ChatService:

```python
# In query() and query_stream():
checkpointer = getattr(request.app.state, "checkpointer", None)
svc = ChatService(driver, checkpointer=checkpointer)
```

- [ ] **Step 4: Run tests**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_chat_service.py -x -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/services/chat_service.py backend/app/api/routes/chat.py backend/app/api/dependencies.py
git commit -m "feat(checkpoint): wire AsyncPostgresSaver into ChatService graph compilation"
```

### Task 3: Add PostgreSQL init migration for checkpoint tables

**Files:**
- Modify: `scripts/init_postgres.sh`
- Test: Manual verification (Docker Compose up)

- [ ] **Step 1: Verify current init_postgres.sh**

Read `scripts/init_postgres.sh` to understand existing setup.

- [ ] **Step 2: Note that AsyncPostgresSaver.setup() auto-creates tables**

The `create_checkpointer()` factory calls `await saver.setup()` which auto-creates
the `checkpoints` and `checkpoint_writes` tables. No manual migration needed.

- [ ] **Step 3: Verify by running Docker Compose**

Run: `docker compose up -d && sleep 5 && docker compose logs backend | tail -20`
Expected: See "checkpointer_ready" in backend logs

- [ ] **Step 4: Commit**

No code change needed for this task — the setup() call in create_checkpointer handles it.

---

## Chunk 2: Chat Frontend — Thread Persistence and Multi-Turn

### Task 4: Add Chat Store with Thread Management

**Files:**
- Create: `frontend/stores/chat-store.ts`
- Test: Manual (browser dev tools)

- [ ] **Step 1: Create chat store with Zustand**

```typescript
// frontend/stores/chat-store.ts
import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface ChatThread {
  id: string
  bookId: string
  title: string // First user message, truncated
  createdAt: string
  updatedAt: string
}

interface ChatState {
  threadId: string | null
  threads: ChatThread[]

  setThreadId: (id: string | null) => void
  addThread: (thread: ChatThread) => void
  removeThread: (id: string) => void
  clearThreads: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      threadId: null,
      threads: [],

      setThreadId: (id) => set({ threadId: id }),
      addThread: (thread) =>
        set((s) => ({ threads: [thread, ...s.threads].slice(0, 50) })),
      removeThread: (id) =>
        set((s) => ({
          threads: s.threads.filter((t) => t.id !== id),
          threadId: s.threadId === id ? null : s.threadId,
        })),
      clearThreads: () => set({ threads: [], threadId: null }),
    }),
    { name: "worldrag-chat" },
  ),
)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/stores/chat-store.ts
git commit -m "feat(frontend): add Zustand chat store with thread persistence"
```

### Task 5: Wire thread_id Through useChatStream Hook

**Files:**
- Modify: `frontend/hooks/use-chat-stream.ts`
- Modify: `frontend/lib/api/chat.ts`

- [ ] **Step 1: Update chatStream to accept threadId**

In `frontend/lib/api/chat.ts`, add `threadId` parameter to `chatStream()`:

```typescript
export function chatStream(
  query: string,
  bookId: string,
  callbacks: ChatStreamCallbacks,
  maxChapter?: number,
  threadId?: string,
): AbortController {
  // ... existing code ...
  const params = new URLSearchParams({ q: query, book_id: bookId })
  if (maxChapter != null) params.set("max_chapter", String(maxChapter))
  if (threadId) params.set("thread_id", threadId)
  // ... rest unchanged ...
```

- [ ] **Step 2: Update useChatStream to accept and pass threadId**

In `frontend/hooks/use-chat-stream.ts`, update `send` signature:

```typescript
send: (query: string, bookId: string, maxChapter?: number, threadId?: string) => void
```

And in the send callback, pass threadId to chatStream:

```typescript
const controller = chatStream(query, bookId, callbacks, maxChapter, threadId)
```

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/use-chat-stream.ts frontend/lib/api/chat.ts
git commit -m "feat(frontend): pass thread_id through chat stream for multi-turn"
```

### Task 6: Update Chat Page with Thread Management

**Files:**
- Modify: `frontend/app/(reader)/chat/page.tsx`

- [ ] **Step 1: Wire chat store into page**

```typescript
// Add to imports:
import { useChatStore } from "@/stores/chat-store"

// In ChatPage component:
const { threadId, setThreadId, addThread } = useChatStore()

// Generate thread_id on first message of a conversation:
function handleSend(e: React.FormEvent) {
  e.preventDefault()
  if (!input.trim() || isStreaming || !bookId) return

  let currentThreadId = threadId
  if (!currentThreadId) {
    currentThreadId = crypto.randomUUID()
    setThreadId(currentThreadId)
    addThread({
      id: currentThreadId,
      bookId,
      title: input.trim().slice(0, 80),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    })
  }

  send(input.trim(), bookId, spoilerChapter ?? undefined, currentThreadId)
  setInput("")
}

// Update clearMessages to also reset thread:
function handleClear() {
  clearMessages()
  setThreadId(null)
}
```

Replace the existing `clearMessages` onClick with `handleClear`.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(reader\)/chat/page.tsx
git commit -m "feat(frontend): wire thread_id into chat page for multi-turn conversations"
```

---

## Chunk 3: Reader LangGraph Agent

### Task 7: Define Reader Agent State

**Files:**
- Create: `backend/app/agents/reader/__init__.py`
- Create: `backend/app/agents/reader/state.py`
- Test: `backend/tests/test_reader_state.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reader_state.py
"""Tests for the Reader agent state schema."""

def test_reader_state_has_required_keys():
    """ReaderAgentState has all expected keys."""
    from app.agents.reader.state import ReaderAgentState

    hints = ReaderAgentState.__annotations__
    required = {
        "messages", "query", "book_id", "chapter_number",
        "paragraph_context", "entity_annotations", "generation",
        "route",
    }
    assert required.issubset(hints.keys()), f"Missing: {required - hints.keys()}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_state.py -x -v`
Expected: FAIL — no module

- [ ] **Step 3: Write implementation**

```python
# backend/app/agents/reader/__init__.py
"""Reader LangGraph agent — chapter-scoped Q&A with entity annotations."""

from app.agents.reader.graph import build_reader_graph

__all__ = ["build_reader_graph"]
```

```python
# backend/app/agents/reader/state.py
"""LangGraph state definition for the reader agent.

NOTE: No `from __future__ import annotations` — LangGraph requires
runtime type hints resolution.
"""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ReaderAgentState(TypedDict, total=False):
    """Shared state for the reader LangGraph pipeline.

    The reader agent is scoped to a single chapter. It answers questions
    about the current reading position using paragraph text and entity
    annotations as grounding context.
    """

    # -- Conversation --
    messages: Annotated[list[BaseMessage], add_messages]

    # -- Query --
    query: str
    route: str  # context_qa | entity_lookup | summarize

    # -- Chapter scope --
    book_id: str
    chapter_number: int
    max_chapter: int | None  # spoiler guard

    # -- Retrieved context --
    paragraph_context: list[dict[str, Any]]
    entity_annotations: list[dict[str, Any]]
    kg_context: str

    # -- Generation --
    generation: str
    citations: list[dict[str, Any]]
```

- [ ] **Step 4: Run test**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_state.py -x -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/reader/ backend/tests/test_reader_state.py
git commit -m "feat(reader): define ReaderAgentState and package structure"
```

### Task 8: Implement Reader Agent Nodes

**Files:**
- Create: `backend/app/agents/reader/prompts.py`
- Create: `backend/app/agents/reader/nodes/__init__.py`
- Create: `backend/app/agents/reader/nodes/reader_router.py`
- Create: `backend/app/agents/reader/nodes/reader_retrieve.py`
- Create: `backend/app/agents/reader/nodes/reader_generate.py`
- Test: `backend/tests/test_reader_nodes.py`

- [ ] **Step 1: Write failing tests for all 3 nodes**

```python
# backend/tests/test_reader_nodes.py
"""Tests for reader agent nodes."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from langchain_core.messages import HumanMessage, AIMessage


@pytest.mark.asyncio
async def test_reader_router_classifies_entity_lookup():
    """Router classifies 'Who is Jake?' as entity_lookup."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content='{"route": "entity_lookup"}')

    with patch("app.agents.reader.nodes.reader_router.get_langchain_llm", return_value=mock_llm):
        from app.agents.reader.nodes.reader_router import classify_reader_intent

        result = await classify_reader_intent({
            "messages": [HumanMessage(content="Who is Jake?")],
            "query": "Who is Jake?",
            "book_id": "book-1",
            "chapter_number": 5,
        })
        assert result["route"] == "entity_lookup"


@pytest.mark.asyncio
async def test_reader_router_defaults_to_context_qa():
    """Router defaults to context_qa on parse failure."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content="invalid json")

    with patch("app.agents.reader.nodes.reader_router.get_langchain_llm", return_value=mock_llm):
        from app.agents.reader.nodes.reader_router import classify_reader_intent

        result = await classify_reader_intent({
            "messages": [HumanMessage(content="What happened?")],
            "query": "What happened?",
            "book_id": "book-1",
            "chapter_number": 5,
        })
        assert result["route"] == "context_qa"


@pytest.mark.asyncio
async def test_reader_retrieve_fetches_paragraphs_and_entities():
    """Retrieve node queries paragraphs and entity annotations."""
    mock_repo = MagicMock()
    mock_repo.execute_read = AsyncMock(side_effect=[
        # First call: paragraphs
        [
            {"index": 0, "type": "narration", "text": "Jake walked into the cave.", "char_start": 0, "char_end": 25},
        ],
        # Second call: entity annotations
        [
            {"name": "Jake", "labels": ["Character"], "char_start": 0, "char_end": 4, "mention_text": "Jake"},
        ],
    ])

    from app.agents.reader.nodes.reader_retrieve import retrieve_chapter_context

    result = await retrieve_chapter_context(
        {"book_id": "book-1", "chapter_number": 5, "query": "What happened?", "max_chapter": 5},
        repo=mock_repo,
    )
    assert len(result["paragraph_context"]) == 1
    assert len(result["entity_annotations"]) == 1
    assert mock_repo.execute_read.call_count == 2


@pytest.mark.asyncio
async def test_reader_generate_produces_answer():
    """Generate node produces an answer from paragraph context."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(content="Jake entered a dark cave in [Para.1].")

    with patch("app.agents.reader.nodes.reader_generate.get_langchain_llm", return_value=mock_llm):
        from app.agents.reader.nodes.reader_generate import generate_reader_answer

        result = await generate_reader_answer({
            "query": "What happened?",
            "book_id": "book-1",
            "chapter_number": 5,
            "route": "context_qa",
            "paragraph_context": [
                {"index": 0, "type": "narration", "text": "Jake walked into the cave."},
            ],
            "entity_annotations": [
                {"name": "Jake", "labels": ["Character"]},
            ],
            "kg_context": "",
        })
        assert "Jake" in result["generation"]


@pytest.mark.asyncio
async def test_reader_generate_entity_lookup():
    """Generate handles entity_lookup route with KG context."""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = AIMessage(
        content="Jake is a level 42 Human Archer."
    )

    with patch("app.agents.reader.nodes.reader_generate.get_langchain_llm", return_value=mock_llm):
        from app.agents.reader.nodes.reader_generate import generate_reader_answer

        result = await generate_reader_answer({
            "query": "Who is Jake?",
            "book_id": "book-1",
            "chapter_number": 5,
            "route": "entity_lookup",
            "paragraph_context": [],
            "entity_annotations": [
                {"name": "Jake", "labels": ["Character"], "description": "Human Archer, level 42"},
            ],
            "kg_context": "Jake (Character): Human Archer, level 42\n  - HAS_CLASS -> Archer",
        })
        assert "Jake" in result["generation"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_nodes.py -x -v`
Expected: FAIL — no modules

- [ ] **Step 3: Implement prompts**

```python
# backend/app/agents/reader/prompts.py
"""Prompt templates for the Reader agent."""

READER_ROUTER_SYSTEM = """\
You are a reading assistant router. Classify the user's question into one of these categories:

- "context_qa": Questions about what is happening in the current chapter (events, dialogue, plot)
- "entity_lookup": Questions about a specific character, item, skill, or entity ("Who is X?", "What is Y?")
- "summarize": Requests to summarize the chapter or a section

Return JSON: {"route": "<category>"}
"""

READER_GENERATE_SYSTEM = """\
You are a reading assistant for a fiction novel. Answer the reader's question using ONLY the provided chapter paragraphs and entity information.

Rules:
- Only use information from the provided context
- Reference specific paragraphs with [Para.N] citations where N is the paragraph index
- If entity KG context is provided, use it to enrich your answer
- Keep answers concise (2-4 sentences for simple questions, more for summaries)
- Respect the spoiler guard: never reveal information beyond the current chapter
- If you cannot answer from the provided context, say so honestly

{spoiler_guard}
"""

READER_ENTITY_SYSTEM = """\
You are a reading assistant focused on entity information. Answer using the provided Knowledge Graph context about the entity.

Rules:
- Use the entity description and relationships from the KG
- Reference which chapter/paragraph the entity appears in if available
- Do not reveal information beyond the reader's current chapter
- Keep answers factual and grounded in the provided data

{spoiler_guard}
"""
```

- [ ] **Step 4: Implement nodes**

```python
# backend/app/agents/reader/nodes/__init__.py
"""Reader agent nodes."""

from app.agents.reader.nodes.reader_generate import generate_reader_answer
from app.agents.reader.nodes.reader_retrieve import retrieve_chapter_context
from app.agents.reader.nodes.reader_router import classify_reader_intent

__all__ = ["classify_reader_intent", "retrieve_chapter_context", "generate_reader_answer"]
```

```python
# backend/app/agents/reader/nodes/reader_router.py
"""Reader agent router: classifies question intent."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.reader.prompts import READER_ROUTER_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def classify_reader_intent(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the reader's question into a route."""
    llm = get_langchain_llm(settings.llm_chat)
    query = state.get("query") or state["messages"][-1].content

    response = await llm.ainvoke([
        SystemMessage(content=READER_ROUTER_SYSTEM),
        HumanMessage(content=query),
    ])

    try:
        parsed = json.loads(response.content)
        route = parsed.get("route", "context_qa")
        if route not in ("context_qa", "entity_lookup", "summarize"):
            route = "context_qa"
    except (json.JSONDecodeError, KeyError):
        logger.warning("reader_router_parse_failed", raw=str(response.content)[:200])
        route = "context_qa"

    logger.info("reader_route_classified", route=route, chapter=state.get("chapter_number"))
    return {"route": route, "query": query}
```

```python
# backend/app/agents/reader/nodes/reader_retrieve.py
"""Reader agent retrieve: fetch chapter paragraphs and entity annotations."""

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def retrieve_chapter_context(
    state: dict[str, Any],
    *,
    repo,
) -> dict[str, Any]:
    """Retrieve paragraphs and entity annotations for the current chapter."""
    book_id = state["book_id"]
    chapter_number = state["chapter_number"]
    max_chapter = state.get("max_chapter")

    # Fetch paragraphs for the chapter
    paragraphs = await repo.execute_read(
        """
        MATCH (c:Chapter {book_id: $book_id, number: $chapter_number})
              -[:HAS_PARAGRAPH]->(p:Paragraph)
        RETURN p.index AS index, p.type AS type, p.text AS text,
               p.char_start AS char_start, p.char_end AS char_end,
               p.speaker AS speaker
        ORDER BY p.index
        """,
        {"book_id": book_id, "chapter_number": chapter_number},
    )

    # Fetch entity annotations grounded in this chapter
    entities = await repo.execute_read(
        """
        MATCH (entity)-[m:MENTIONED_IN]->(c:Chapter {book_id: $book_id, number: $chapter_number})
        WHERE $max_chapter IS NULL
              OR NOT exists(entity.valid_from_chapter)
              OR entity.valid_from_chapter <= $max_chapter
        RETURN DISTINCT entity.name AS name,
               labels(entity) AS labels,
               entity.description AS description,
               m.char_start AS char_start,
               m.char_end AS char_end,
               m.mention_text AS mention_text
        ORDER BY m.char_start
        """,
        {"book_id": book_id, "chapter_number": chapter_number, "max_chapter": max_chapter},
    )

    # Build KG context for entity_lookup route
    kg_lines = []
    for e in entities:
        label = next(
            (l for l in e.get("labels", []) if l not in ("Entity", "Node", "_Entity")),
            "Entity",
        )
        desc = e.get("description", "")
        kg_lines.append(f"{e['name']} ({label}): {desc}")

    logger.info(
        "reader_context_retrieved",
        chapter=chapter_number,
        paragraphs=len(paragraphs),
        entities=len(entities),
    )

    return {
        "paragraph_context": paragraphs,
        "entity_annotations": entities,
        "kg_context": "\n".join(kg_lines),
    }
```

```python
# backend/app/agents/reader/nodes/reader_generate.py
"""Reader agent generate: produce answer from chapter context."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.reader.prompts import READER_ENTITY_SYSTEM, READER_GENERATE_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def generate_reader_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Generate an answer using chapter paragraphs and entity context."""
    llm = get_langchain_llm(settings.llm_chat)
    query = state["query"]
    route = state.get("route", "context_qa")
    paragraphs = state.get("paragraph_context", [])
    entities = state.get("entity_annotations", [])
    kg_context = state.get("kg_context", "")
    max_chapter = state.get("max_chapter")
    chapter_number = state.get("chapter_number", 0)

    # Build spoiler guard instruction
    spoiler_guard = ""
    if max_chapter is not None:
        spoiler_guard = (
            f"SPOILER GUARD: The reader has read up to chapter {max_chapter}. "
            f"Do NOT reveal any information from chapters after {max_chapter}."
        )

    # Build context based on route
    if route == "entity_lookup" and kg_context:
        system_prompt = READER_ENTITY_SYSTEM.format(spoiler_guard=spoiler_guard)
        context_text = f"## Entity Knowledge Graph\n\n{kg_context}"
    else:
        system_prompt = READER_GENERATE_SYSTEM.format(spoiler_guard=spoiler_guard)
        para_lines = []
        for p in paragraphs:
            idx = p.get("index", 0)
            ptype = p.get("type", "narration")
            text = p.get("text", "")
            speaker = p.get("speaker")
            prefix = f"[Para.{idx}] ({ptype})"
            if speaker:
                prefix += f" [{speaker}]"
            para_lines.append(f"{prefix}: {text}")
        context_text = f"## Chapter {chapter_number} Paragraphs\n\n" + "\n\n".join(para_lines)

        if kg_context:
            context_text += f"\n\n## Entity Context\n\n{kg_context}"

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{context_text}\n\n---\n\nQuestion: {query}"),
    ])

    generation = response.content if isinstance(response.content, str) else str(response.content)

    logger.info(
        "reader_answer_generated",
        route=route,
        chapter=chapter_number,
        answer_len=len(generation),
    )

    return {"generation": generation}
```

- [ ] **Step 5: Run tests**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_nodes.py -x -v`
Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/reader/
git commit -m "feat(reader): implement router, retrieve, and generate nodes"
```

### Task 9: Build Reader Graph and Service

**Files:**
- Create: `backend/app/agents/reader/graph.py`
- Create: `backend/app/services/reader_service.py`
- Test: `backend/tests/test_reader_graph.py`

- [ ] **Step 1: Write failing test for graph structure**

```python
# backend/tests/test_reader_graph.py
"""Tests for the reader agent graph structure."""

import pytest
from unittest.mock import MagicMock


def test_reader_graph_has_expected_nodes():
    """Graph contains router, retrieve, generate nodes."""
    from app.agents.reader.graph import build_reader_graph

    repo = MagicMock()
    builder = build_reader_graph(repo=repo)
    graph = builder.compile()

    node_names = set(graph.get_graph().nodes.keys())
    expected = {"router", "retrieve", "generate", "__start__", "__end__"}
    assert expected.issubset(node_names), f"Missing: {expected - node_names}"


def test_reader_graph_compiles():
    """Graph compiles without errors."""
    from app.agents.reader.graph import build_reader_graph

    repo = MagicMock()
    builder = build_reader_graph(repo=repo)
    graph = builder.compile()
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_graph.py -x -v`

- [ ] **Step 3: Implement graph**

```python
# backend/app/agents/reader/graph.py
"""Reader LangGraph: compiles the StateGraph for chapter-scoped Q&A."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.reader.state import ReaderAgentState
from app.core.logging import get_logger

from .nodes.reader_generate import generate_reader_answer
from .nodes.reader_retrieve import retrieve_chapter_context
from .nodes.reader_router import classify_reader_intent

logger = get_logger(__name__)


def _route_after_reader_router(state: dict[str, Any]) -> str:
    """Route: all paths go through retrieve then generate."""
    return "retrieve"


def build_reader_graph(*, repo) -> StateGraph:
    """Build the reader agent StateGraph (uncompiled).

    Simple 3-node pipeline: router -> retrieve -> generate.
    All routes go through retrieve since we always need chapter context.
    """
    async def _retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
        return await retrieve_chapter_context(state, repo=repo)

    builder = StateGraph(ReaderAgentState)

    builder.add_node("router", classify_reader_intent)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("generate", generate_reader_answer)

    builder.add_edge(START, "router")
    builder.add_edge("router", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    return builder
```

- [ ] **Step 4: Implement service**

```python
# backend/app/services/reader_service.py
"""Reader agent service — chapter-scoped Q&A."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from neo4j import AsyncDriver

from langchain_core.messages import HumanMessage

from app.agents.reader.graph import build_reader_graph
from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)


class ReaderService:
    """Chapter-scoped Q&A service using the Reader LangGraph agent."""

    _compiled_graph: Any = None
    _shared_repo: Any = None
    _shared_driver: Any = None

    def __init__(self, driver: AsyncDriver, checkpointer: Any = None) -> None:
        self.repo = Neo4jRepository(driver)

        if ReaderService._shared_driver is not None and ReaderService._shared_driver is not driver:
            logger.info("reader_service_driver_changed_recompiling")
            ReaderService._compiled_graph = None
            ReaderService._shared_repo = None

        if ReaderService._compiled_graph is None:
            ReaderService._shared_repo = self.repo
            ReaderService._shared_driver = driver
            builder = build_reader_graph(repo=self.repo)
            ReaderService._compiled_graph = builder.compile(checkpointer=checkpointer)

        self._graph = ReaderService._compiled_graph

    async def query(
        self,
        query: str,
        book_id: str,
        chapter_number: int,
        *,
        max_chapter: int | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the reader agent for a chapter-scoped question."""
        state_input: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "book_id": book_id,
            "chapter_number": chapter_number,
            "max_chapter": max_chapter or chapter_number,
        }

        config: dict[str, Any] = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        result = await self._graph.ainvoke(state_input, config=config)

        return {
            "answer": result.get("generation", ""),
            "route": result.get("route", "context_qa"),
            "paragraphs_used": len(result.get("paragraph_context", [])),
            "entities_found": len(result.get("entity_annotations", [])),
        }
```

- [ ] **Step 5: Run tests**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_graph.py -x -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/reader/graph.py backend/app/services/reader_service.py backend/tests/test_reader_graph.py
git commit -m "feat(reader): build graph, service, and graph structure tests"
```

### Task 10: Add Reader API Routes

**Files:**
- Modify: `backend/app/api/routes/reader.py` (add Q&A endpoints)
- Create: `backend/app/schemas/reader.py`
- Test: `backend/tests/test_reader_routes.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_reader_routes.py
"""Tests for reader Q&A API routes."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    from app.main import create_app

    app = create_app()
    app.state.neo4j_driver = MagicMock()
    app.state.checkpointer = None

    with TestClient(app) as c:
        yield c


def test_reader_query_endpoint_exists(client):
    """POST /api/reader/query returns 422 without body (route exists)."""
    resp = client.post("/api/reader/query")
    assert resp.status_code == 422  # Validation error = route exists


def test_reader_query_requires_book_and_chapter(client):
    """POST /api/reader/query validates required fields."""
    resp = client.post("/api/reader/query", json={"query": "What happened?"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Create schema**

```python
# backend/app/schemas/reader.py
"""Pydantic schemas for the Reader Q&A API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReaderQueryRequest(BaseModel):
    """Request schema for a reader question."""

    query: str = Field(..., min_length=1, max_length=2000)
    book_id: str = Field(..., min_length=1, max_length=200, pattern=r"^[\w\-.:]+$")
    chapter_number: int = Field(..., ge=1)
    max_chapter: int | None = Field(default=None, ge=1)
    thread_id: str | None = Field(
        default=None, max_length=200, pattern=r"^[\w\-.:]+$"
    )


class ReaderQueryResponse(BaseModel):
    """Response schema for a reader question."""

    answer: str
    route: str
    paragraphs_used: int = 0
    entities_found: int = 0
    thread_id: str | None = None
```

- [ ] **Step 3: Add route to reader.py**

Add to `backend/app/api/routes/reader.py`:

```python
from app.schemas.reader import ReaderQueryRequest, ReaderQueryResponse
from app.services.reader_service import ReaderService

@router.post("/query", dependencies=[Depends(require_auth)])
async def reader_query(
    request: ReaderQueryRequest,
    driver: AsyncDriver = Depends(get_neo4j),
) -> ReaderQueryResponse:
    """Ask a question about the current chapter."""
    from fastapi import Request as FastAPIRequest
    checkpointer = None  # Will be wired via app.state once available

    svc = ReaderService(driver, checkpointer=checkpointer)
    result = await svc.query(
        query=request.query,
        book_id=request.book_id,
        chapter_number=request.chapter_number,
        max_chapter=request.max_chapter,
        thread_id=request.thread_id,
    )

    return ReaderQueryResponse(
        answer=result["answer"],
        route=result["route"],
        paragraphs_used=result["paragraphs_used"],
        entities_found=result["entities_found"],
        thread_id=request.thread_id,
    )
```

- [ ] **Step 4: Run tests**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/test_reader_routes.py -x -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/reader.py backend/app/api/routes/reader.py backend/tests/test_reader_routes.py
git commit -m "feat(reader): add POST /reader/query API endpoint"
```

---

## Chunk 4: Cohere Reranker Production Readiness

### Task 11: Document Cohere API Key Setup

**Files:**
- Modify: `.env.example` (if exists) or `.env`

- [ ] **Step 1: Verify .env has COHERE_API_KEY placeholder**

Read `.env` to confirm `COHERE_API_KEY=` exists (empty).

- [ ] **Step 2: The reranker is already production-ready**

The code in `backend/app/agents/chat/nodes/rerank.py` already:
- Lazy-loads `CohereReranker` when `settings.cohere_api_key` is set
- Falls back to RRF order when no API key
- Has circuit breaker + rate limiter + retry logic
- Has full test coverage

No code changes needed. Just document in `.env`:

```env
# Cohere Reranker (optional — falls back to RRF order without it)
# Get your API key at https://dashboard.cohere.com/api-keys
COHERE_API_KEY=
```

- [ ] **Step 3: Commit**

```bash
git add .env
git commit -m "docs: document COHERE_API_KEY in .env"
```

---

## Chunk 5: Full Test Suite Verification

### Task 12: Run Full Test Suite and Lint

- [ ] **Step 1: Run ruff check**

Run: `cd /e/RAG && python -m uv run ruff check backend/ --fix`
Expected: No errors

- [ ] **Step 2: Run ruff format**

Run: `cd /e/RAG && python -m uv run ruff format backend/`
Expected: Files formatted

- [ ] **Step 3: Run full test suite**

Run: `cd /e/RAG && python -m uv run pytest backend/tests/ -x -v --tb=short`
Expected: ALL PASS (700+ tests)

- [ ] **Step 4: Run frontend build**

Run: `cd /e/RAG/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final lint and format pass"
```
