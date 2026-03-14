# Full SOTA Chat Pipeline — Design Spec

Date: 2026-03-14
Status: Approved (post-review v2)

## Context

WorldRAG has a working chat pipeline (8-node LangGraph DAG) but falls short
of 2025-2026 SOTA on retrieval quality, generation faithfulness, agent
adaptivity, conversation memory, and frontend UX. This spec defines the
upgrades needed to reach full SOTA for fiction-novel Q&A.

Hardware: RTX 3090 24GB. Cost strategy: local models for fast/cheap tasks,
cheap API (Gemini free / DeepSeek V3.2 via OpenRouter) for generation.

## 1. Model Stack

### Local models (~10.5GB VRAM total)

| Role | Model | HuggingFace ID | VRAM | Latency |
|------|-------|----------------|------|---------|
| Auxiliary LLM | Qwen3.5-4B Q8 | `Qwen/Qwen3.5-4B` | ~5GB | ~200ms |
| Reranker | zerank-1-small (1.7B) | `zeroentropy/zerank-1-small` | ~2GB | ~100ms |
| NLI faithfulness | DeBERTa-v3-large (400M) | `cross-encoder/nli-deberta-v3-large` | ~1.5GB | ~50ms |
| Embeddings | BGE-M3 (568M) | `BAAI/bge-m3` (already in use) | ~0.5GB | ~20ms |
| ColBERT (Phase 2) | colbertv2.0 | `colbert-ir/colbertv2.0` | ~1.5GB | ~80ms |

Note: `Qwen/Qwen3.5-4B` was released 2026-03-02 on HuggingFace, Ollama,
and ModelScope under Apache 2.0. Verify model ID at implementation time —
if unavailable, fall back to `Qwen/Qwen3-4B` or equivalent.

### API models (generation)

| Provider | Model | Input/M | Output/M | Use |
|----------|-------|---------|----------|-----|
| Google AI Studio (free) | Gemini 2.5 Flash-Lite | $0 | $0 | Default, 30 RPM |
| OpenRouter | DeepSeek V3.2 | $0.26 | $0.38 | Upgrade tier |
| OpenRouter | Kimi K2.5 | $0.45 | $2.20 | Premium tier |
| Local fallback | Qwen3.5-4B | $0 | $0 | Offline mode |

### Provider abstraction

Extend the existing `get_langchain_llm(spec)` in `providers.py` with
two new provider branches: `openrouter` and `local`. Do NOT create a
separate `get_generation_llm()` — keep the single factory pattern.

The `spec` format remains `provider:model`, e.g.:
- `gemini:gemini-2.5-flash-lite` (uses existing `GEMINI_API_KEY`)
- `openrouter:deepseek/deepseek-v3.2` (new)
- `local:Qwen/Qwen3.5-4B` (new)

New fields in `config.py` Settings class:

```python
# In Settings(BaseSettings):
llm_generation: str = "gemini:gemini-2.5-flash-lite"  # generation model
llm_auxiliary: str = "local:Qwen/Qwen3.5-4B"          # router/HyDE/decompose
openrouter_api_key: str = ""                           # OPENROUTER_API_KEY
local_llm_backend: str = "ollama"                      # ollama|transformers
ollama_base_url: str = "http://localhost:11434"         # OLLAMA_BASE_URL
```

Note: `GEMINI_API_KEY` (existing field `gemini_api_key`) is reused for
Google AI Studio free tier. No new `GOOGLE_AI_API_KEY` env var — use the
existing one.

### Local LLM inference backend

**Primary: Ollama** (HTTP server, pre-quantized models, zero Python deps)
- Install: `curl -fsSL https://ollama.com/install.sh | sh`
- Pull model: `ollama pull qwen3.5:4b`
- LangChain integration: `langchain-ollama` package (`ChatOllama`)
- Already supports structured output via `format="json"`
- Runs as a separate process, no VRAM conflict with PyTorch models

**Fallback: transformers + bitsandbytes** (if Ollama unavailable)
- `AutoModelForCausalLM.from_pretrained(..., load_in_4bit=True)`
- Requires `transformers>=4.40`, `accelerate>=0.30`, `bitsandbytes`

The `local_llm_backend` setting controls which path is used.

### Reranker loading

zerank-1-small uses `sentence-transformers` CrossEncoder API:

```python
from sentence_transformers import CrossEncoder
model = CrossEncoder("zeroentropy/zerank-1-small", trust_remote_code=True)
results = model.rank(query, documents)
```

No new package needed — `sentence-transformers>=3.0` (already a dependency)
includes CrossEncoder support. The `trust_remote_code=True` flag is required
for zerank's custom architecture.

### NLI model loading

DeBERTa uses `sentence_transformers.CrossEncoder` as well:

```python
model = CrossEncoder("cross-encoder/nli-deberta-v3-large")
scores = model.predict([(claim, context)])  # returns [contradiction, entailment, neutral]
```

Same `sentence-transformers` dependency. Add `transformers>=4.40` as
explicit dependency (currently only transitive via sentence-transformers).

### New dependencies (pyproject.toml)

```toml
# Add to [project.dependencies]:
transformers = ">=4.40"
accelerate = ">=0.30"
langchain-ollama = ">=0.3"
# Optional for transformers backend:
bitsandbytes = {version = ">=0.43", optional = true}
```

## 2. Chat Agent Architecture (Agentic RAG)

Replace the current fixed DAG with an adaptive agent graph.

### New graph topology

```
START
  -> load_memory          (load conversation summary from checkpointer)
  -> intent_analyzer      (6-route classifier, Qwen3.5-4B local)
  -> [conditional edges based on route]:

     factual_lookup:
       -> kg_query_scored -> context_assembly -> generate -> nli_check -> END

     entity_qa / relationship_qa:
       -> query_transform (multi-query) -> hyde_expand
       -> retrieve_multi (parallel: vector x3 + sparse + graph_scored)
       -> rerank_zerank -> deduplicate_chunks
       -> context_assembly -> generate -> nli_check -> END

     timeline_qa:
       -> query_transform -> retrieve_multi -> rerank_zerank
       -> deduplicate_chunks -> temporal_sort
       -> context_assembly -> generate_cot -> nli_check -> END

     analytical (complex):
       -> decompose_query (split into sub-questions, Qwen3.5-4B)
       -> sequential_sub_retrieve (iterate sub-questions, retrieve+rerank each)
       -> merge_contexts -> generate_cot -> nli_check -> self_reflect
       -> [if insufficient: retry_different_strategy | END]

     conversational:
       -> generate_direct (use memory, skip retrieval) -> END

  nli_check:
     -> read state["route"] for adaptive threshold:
        factual_lookup: 0.8 | entity_qa/relationship_qa: 0.7
        timeline_qa: 0.6 | analytical: 0.5
     -> if score < threshold AND retries < 1:
          -> rewrite_query -> retrieve_multi (loop back)
     -> else: END

  [conditional after generate]: if turn_count % 5 == 0:
     -> summarize_memory (Qwen3.5-4B) -> persist to checkpointer
```

Note on the analytical route: "parallel sub-pipelines" from the initial
design is replaced with **sequential sub-question iteration** inside a
single `sequential_sub_retrieve` node. This node loops over decomposed
sub-questions, calling retrieve+rerank for each, and merges results.
This avoids LangGraph's lack of native dynamic fan-out (the `Send` API
could be used but adds significant complexity for Phase 1). Phase 2 can
upgrade to true parallel fan-out via `Send` or nested sub-graphs.

### New state fields in ChatAgentState

```python
# Add to ChatAgentState(TypedDict, total=False):
conversation_summary: str              # loaded from checkpointer
entity_memory: list[str]               # entity IDs from prior turns
hyde_document: str                     # hypothetical doc for HyDE
deduplicated_chunks: list[dict[str, Any]]  # post-dedup chunks
turn_count: Annotated[int, operator.add]   # incremented each turn
sub_questions: list[str]               # from decompose_query
```

### Node inventory (new or modified)

| Node | Status | Model | Change |
|------|--------|-------|--------|
| load_memory | NEW | None (DB read) | Load conversation summary + entity_memory |
| intent_analyzer | MODIFY router.py | local aux LLM | 6 routes instead of 3 |
| query_transform | MODIFY | local aux LLM | Keep multi-query, unchanged |
| hyde_expand | NEW | local aux LLM | Generate hypothetical doc, embed it |
| retrieve_multi | MODIFY retrieve.py | BGE-M3 local | Batch-embed ALL query variants via `embed_texts([q1,q2,q3,hyde])` |
| kg_query_scored | MODIFY kg_query.py | None | Score by relationship count/type/depth |
| rerank_zerank | MODIFY rerank.py | zerank-1-small local | Replace Cohere with local CrossEncoder |
| deduplicate_chunks | NEW | BGE-M3 local | Remove >80% cosine similarity overlaps |
| temporal_sort | NEW | None | Sort chunks by (chapter, position) |
| context_assembly | MODIFY | None | Add temporal ordering, entity enrichment |
| generate | MODIFY | API generation LLM | Structured JSON output, fiction-tuned prompt |
| generate_cot | NEW | API generation LLM | CoT prompt for complex/timeline Q |
| nli_check | REPLACE faithfulness.py | DeBERTa-v3-large local | NLI entailment per-claim |
| decompose_query | NEW (Phase 2) | local aux LLM | Split complex Q into sub-questions |
| sequential_sub_retrieve | NEW (Phase 2) | BGE-M3 + zerank | Loop over sub-questions |
| self_reflect | NEW (Phase 2) | local aux LLM | Evaluate if answer is complete |
| summarize_memory | NEW | local aux LLM | Conditional: only if turn_count % 5 == 0 |
| disambiguate_entity | NEW (Phase 2) | None | Requires `interrupt_before` at compile time |

### Source streaming mechanism

The `rerank_zerank` node emits a custom event via LangGraph's
`get_stream_writer()` API after reranking completes:

```python
from langgraph.config import get_stream_writer
writer = get_stream_writer()
writer({"event": "sources", "chunks": [...], "entities": [...]})
```

The `ChatService.query_stream()` method already handles `stream_type == "custom"`
events, so this emits naturally as an SSE event to the frontend.

## 3. Retrieval Upgrades

### 3.1 Multi-query dense retrieval

Current: only queries[0] is embedded for vector search.
New: all 3 variants + HyDE doc are batch-embedded in a single call:
`embeddings = await embedder.embed_texts([q1, q2, q3, hyde_doc])`

Each embedding produces top-K candidates (K=10 each).
RRF fusion across (3-4 dense + 1 sparse + 1 graph) = 5-6 result sets.

### 3.2 HyDE (Hypothetical Document Embeddings)

After query_transform, the local aux LLM generates a ~100-token
hypothetical answer passage. This passage is embedded and used as an
additional dense query vector in `retrieve_multi`.

Only used for entity_qa, relationship_qa, analytical, timeline_qa routes.
Skipped for factual_lookup and conversational.

### 3.3 Graph search scoring

Replace the current `1.0 AS score` with a composite score:

```cypher
RETURN entity.name AS name,
       (toFloat(rel_count) / 10.0) * 0.4 +
       CASE WHEN entity.description IS NOT NULL THEN 0.3 ELSE 0.0 END +
       (1.0 / (1.0 + path_depth)) * 0.3
       AS score
```

### 3.4 Chunk deduplication

After reranking, compute pairwise cosine similarity on chunk embeddings
(already available from the retrieval step). If sim > 0.80, keep only the
higher-scored chunk.

### 3.5 ColBERT (Phase 2)

Deferred. When implemented, BGE-M3's multi-vector output mode can be used
(`output_value="colbert_vecs"`) with a separate FAISS index for MaxSim.

## 4. Generation Upgrades

### 4.1 Structured output

Generation produces a Pydantic model:

```python
class GenerationOutput(BaseModel):
    answer: str
    citations: list[Citation]
    entities_mentioned: list[str]
    confidence: float = 0.0  # filled by nli_check post-generation

class Citation(BaseModel):
    chapter: int
    position: int | None = None
    claim: str           # the specific claim being cited
    source_span: str     # exact text from the chunk
```

The `generate` node stores `GenerationOutput.model_dump()` as a dict in
`state["generation_output"]`. The existing `state["generation"]` field is
kept as `generation_output["answer"]` for backward compatibility.

The `ChatService.query()` method is updated to read from
`result.get("generation_output", {})` and map to the existing
`ChatResponse` schema, adding new fields (claim-level citations,
confidence) while keeping the old fields working.

### 4.2 Chain-of-thought prompting

For analytical and timeline routes, the generation prompt includes explicit
step-by-step reasoning instructions. See Section 4.3 for full prompts.

### 4.3 Fiction-tuned prompts

Domain-specific prompt improvements:
- Awareness of character aliases and nicknames
- Understanding of magic system mechanics (stats, skills, classes)
- Handling of timeline ambiguity (flashbacks, time skips)
- LitRPG-specific: blue box interpretation, stat changes, level progression
- Spoiler guard enforcement in the system prompt

### 4.4 Span-level attribution (Phase 2)

Deferred. The `Citation.source_span` field is included in the schema now
so the LLM can start populating it, but verification of spans against
actual chunk text is a Phase 2 feature.

## 5. Faithfulness (NLI-based)

Replace the current LLM-as-judge with DeBERTa-v3-large NLI.

### Pipeline

1. Split generated answer into individual claims (sentence-level)
2. For each claim, run NLI via CrossEncoder against concatenated context:
   - entailment → supported (score 1.0)
   - neutral → partially supported (score 0.5)
   - contradiction → unsupported (score 0.0)
3. Aggregate: faithfulness_score = mean(claim_scores)
4. If any claim is contradiction → flag for rewrite
5. Adaptive threshold based on `state["route"]`:
   - factual_lookup: 0.8
   - entity_qa / relationship_qa: 0.7
   - timeline_qa: 0.6
   - analytical: 0.5
   - conversational: no check (skip)

The threshold table lives inside the `nli_check` node, not in the
graph's conditional edge function. The conditional edge after nli_check
reads `state["faithfulness_passed"]` (bool set by the node).

## 6. Conversation Memory

### Memory node (load_memory)

At the start of each turn, load from checkpointer state:
- Last N messages (sliding window, default 6)
- `conversation_summary` (if > 6 turns exist)
- `entity_memory` (entity IDs from prior turns)
- Book context (book_id, max_chapter from first message)

### Summarization (summarize_memory)

Triggered conditionally: after `generate`, if `state["turn_count"] % 5 == 0`.

Implementation: `turn_count` is an `Annotated[int, operator.add]` field
in `ChatAgentState` (same pattern as existing `retries`). The `generate`
node adds `{"turn_count": 1}` to its return dict. The conditional edge
after generate checks `state.get("turn_count", 0) % 5 == 0`.

The local aux LLM compresses the full conversation into a JSON summary
stored in `state["conversation_summary"]`.

### Entity memory enrichment

The `kg_query_scored` and `retrieve_multi` nodes append found entity IDs
to `state["entity_memory"]`. On subsequent turns, `load_memory` injects
these as additional search scope for KG queries.

## 7. Frontend Chat Upgrades

### 7.1 Source streaming (SSE event)

Backend emits a `sources` SSE event via `get_stream_writer()` in the
rerank node. Frontend hook receives it and displays a collapsible
"Sources" panel while generation streams.

### 7.2 Citation highlights

Citations `[Ch.5, §3]` are parsed by a React component and rendered as
interactive elements with hover tooltips and click-to-expand.

### 7.3 Feedback (thumbs up/down)

POST /api/chat/feedback endpoint. PostgreSQL table `chat_feedback`.

DDL goes in `scripts/init_postgres.sql` (new file, run by
`init_postgres.sh` alongside LangGraph checkpoint tables):

```sql
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
```

### 7.4 Thread history sidebar

Left sidebar with past conversations loaded from the Zustand store
(already has thread list). Add: title, book name, date display, delete.

### 7.5 Confidence indicator

Visual badge based on NLI faithfulness_score: green/yellow/red.

## 8. Entity Disambiguation (Phase 2)

Deferred. Requires LangGraph `interrupt_before=["disambiguate_entity"]`
at graph compile time. The graph must be compiled with this interrupt
point, and `ChatService` must handle the interrupt/resume cycle. This is
a significant change to the service layer and is better suited for Phase 2.

## 9. RLHF / Feedback Pipeline (Phase 2)

### Phase 1: feedback storage only
- `chat_feedback` table + POST endpoint + frontend buttons

### Phase 2: export + dashboard
- `GET /api/admin/feedback/export?format=jsonl` endpoint
- Admin dashboard with satisfaction metrics

## 10. Cost Estimation

For 3 tomes of Primal Hunter (~720K tokens text):

| Usage | Model | Cost |
|-------|-------|------|
| 1000 queries (generation) | Gemini 2.5 Flash-Lite free | $0 |
| 1000 queries (generation) | DeepSeek V3.2 via OpenRouter | ~$1.60 |
| All local models | GPU only | $0 |

Total for personal use: **$0 to $1.60 per 1000 queries**.

## 11. Phasing

### Phase 1 (this implementation cycle)

**Backend — LLM infrastructure:**
1. Extend `providers.py` with `openrouter` and `local` (Ollama) branches
2. Add new config fields (`llm_generation`, `llm_auxiliary`, `openrouter_api_key`, etc.)
3. Load local models at startup (zerank-1-small, DeBERTa NLI) with lazy init
4. Add `transformers`, `accelerate`, `langchain-ollama` to pyproject.toml

**Backend — Chat agent graph:**
5. Add new state fields (conversation_summary, entity_memory, hyde_document, etc.)
6. Implement `load_memory` node
7. Upgrade `intent_analyzer` to 6 routes
8. Implement `hyde_expand` node
9. Upgrade `retrieve_multi` to batch-embed all query variants
10. Implement `kg_query_scored` with composite scoring
11. Replace `rerank` with `rerank_zerank` (local CrossEncoder)
12. Implement `deduplicate_chunks` node
13. Implement `temporal_sort` node (used by timeline_qa route)
14. Upgrade `generate` with structured output + fiction-tuned prompts
15. Implement `generate_cot` node for complex/timeline routes
16. Replace `faithfulness` with `nli_check` (DeBERTa NLI)
17. Implement `summarize_memory` node (conditional on turn_count)
18. Rewire graph with 6-route conditional edges
19. Emit `sources` SSE event from rerank node via `get_stream_writer()`
20. Update `ChatService` to map new generation_output to ChatResponse

**Backend — Feedback:**
21. Create `chat_feedback` PostgreSQL table (init_postgres.sql)
22. Add POST /api/chat/feedback endpoint
23. Add GET /api/chat/feedback (admin, list recent)

**Frontend:**
24. Source streaming display (collapsible panel)
25. Citation highlight component (parse + render [Ch.N, §P])
26. Feedback thumbs up/down buttons on messages
27. Thread history sidebar (list + select + delete)
28. Confidence indicator badge

### Phase 2 (future)
- ColBERT late interaction retrieval (BGE-M3 colbert_vecs mode)
- Span-level attribution verification
- Entity disambiguation with LangGraph interrupt
- Query decomposition with parallel sub-pipelines (Send API)
- Self-reflection node
- RLHF export pipeline + admin dashboard
