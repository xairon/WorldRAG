<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Neo4j-5.x-008CC1?logo=neo4j&logoColor=white" alt="Neo4j">
  <img src="https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white" alt="Next.js 16">
  <img src="https://img.shields.io/badge/Graphiti-0.5+-6D28D9?logoColor=white" alt="Graphiti">
  <img src="https://img.shields.io/badge/LangGraph-0.3+-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

# WorldRAG

**Automatic Knowledge Graph construction + RAG chat for fiction novel universes.**

WorldRAG ingests novels (LitRPG, fantasy, sci-fi), automatically discovers the ontology of each fictional universe, builds a temporal Knowledge Graph in Neo4j, and exposes a chat interface for querying the graph with hybrid retrieval.

The core innovation is the **SagaProfileInducer** -- a module that analyzes the first book of a saga and induces the ontology automatically (character classes, magic systems, factions, progression systems...), then uses it to guide extraction of subsequent books.

> Research project -- LIFAT, Universite de Tours.

---

## How It Works

```mermaid
flowchart TB
    subgraph Ingestion
        EPUB["EPUB / PDF / TXT"] --> PARSE["Parse chapters"]
        PARSE --> CHUNK["Chunk (~500 tokens)"]
    end

    subgraph Discovery["Discovery Mode (1st book)"]
        CHUNK --> GRAPHITI_D["Graphiti add_episode_bulk<br/>(universal types only)"]
        GRAPHITI_D --> NEO4J_D["Neo4j<br/>Entity + Episodic + Temporal edges"]
        NEO4J_D --> INDUCER["SagaProfileInducer"]
        INDUCER --> |"Clustering + LLM"| PROFILE["SagaProfile<br/>(Spell, House, Skill, ...)"]
    end

    subgraph Guided["Guided Mode (books 2+)"]
        CHUNK --> GRAPHITI_G["Graphiti add_episode_bulk<br/>(universal + induced types)"]
        GRAPHITI_G --> NEO4J_G["Neo4j<br/>Typed entities + temporal edges"]
    end

    subgraph PostProcess["Post-processing"]
        NEO4J_D --> LEIDEN["Leiden clustering<br/>(Neo4j GDS)"]
        NEO4J_G --> LEIDEN
        LEIDEN --> COMMUNITY["Community summaries<br/>(LLM)"]
    end

    subgraph Chat["Chat Pipeline (8-node LangGraph)"]
        QUERY["User question"] --> ROUTER["Intent router"]
        ROUTER --> |"open-ended"| GRAPHITI_S["Graphiti search<br/>(semantic + BM25 + BFS)"]
        ROUTER --> |"structured"| CYPHER["Cypher lookup<br/>(typed entities)"]
        ROUTER --> |"conversational"| DIRECT["No retrieval"]
        GRAPHITI_S --> CTX["Context assembly"]
        CYPHER --> CTX
        DIRECT --> CTX
        CTX --> GEN["Generate (CoT)"]
        GEN --> FAITH["Faithfulness check (NLI)"]
        FAITH --> |"pass"| ANSWER["Answer + citations"]
        FAITH --> |"fail (max 2)"| GRAPHITI_S
    end

    PROFILE -.-> GRAPHITI_G
    NEO4J_D -.-> GRAPHITI_S
    NEO4J_G -.-> GRAPHITI_S
    COMMUNITY -.-> CTX
```

---

## Key Concepts

### SagaProfileInducer

The original contribution. When you ingest the first book of a saga, WorldRAG:

1. Extracts entities with **universal types** only (Character, Location, Object, Organization, Event, Concept)
2. Clusters semantically similar entities (e.g., "Expelliarmus", "Patronus", "Lumos" form a cluster)
3. An LLM formalizes each cluster into an **induced type** (Spell, House, MagicalCreature...)
4. Detects **textual patterns** (`[Skill Acquired: X]`, `[Level N -> M]`)
5. Produces a **SagaProfile** -- a Pydantic model that is injected into Graphiti for all subsequent books

```mermaid
flowchart LR
    subgraph "Discovery (Book 1)"
        RAW["Raw entities<br/>(generic Concept nodes)"]
        RAW --> CLUSTER["Semantic clustering<br/>(BGE-m3 embeddings)"]
        CLUSTER --> LLM["LLM formalization"]
        LLM --> TYPES["Induced types:<br/>Spell, House, Skill..."]
        TYPES --> PYDANTIC["Dynamic Pydantic models"]
    end

    subgraph "Guided (Books 2+)"
        PYDANTIC --> GRAPHITI["Graphiti<br/>entity_types={Spell: SpellModel, ...}"]
    end
```

**Examples of induced profiles:**

| Saga | Induced Types | Patterns |
|------|---------------|----------|
| Harry Potter | Spell, House, MagicalCreature | -- (prose only) |
| Primal Hunter | Skill, Class, Bloodline | `[Skill Acquired: X]`, `[Level N -> M]` |
| L'Assassin Royal | MagicSystem (2 instances) | -- (low-magic) |

### Temporal Model

Graphiti maintains a **bi-temporal** graph -- every fact has validity timestamps. WorldRAG maps narrative time (book, chapter, scene) to datetime via `NarrativeTemporalMapper`:

```
(book=1, chapter=5) -> datetime(2000-01-06)
(book=2, chapter=1) -> datetime(2027-05-19)
```

This enables queries like "What skills did Jake have at chapter 30?" with native temporal filtering.

### Dual Retrieval

The chat pipeline uses two complementary retrieval strategies:

| Strategy | When | How |
|----------|------|-----|
| **Graphiti search** | Open-ended questions | Semantic + BM25 + BFS graph traversal |
| **Cypher lookup** | Structured questions | Typed queries on induced labels |

Both hit the same Neo4j database -- Graphiti nodes are augmented with saga-specific labels.

---

## Tech Stack

```mermaid
graph LR
    subgraph Backend
        FASTAPI["FastAPI"] --> LANGGRAPH["LangGraph"]
        FASTAPI --> ARQ["arq workers"]
        LANGGRAPH --> GRAPHITI_LIB["graphiti-core"]
        GRAPHITI_LIB --> NEO4J["Neo4j 5.x + GDS"]
        ARQ --> GRAPHITI_LIB
        ARQ --> REDIS["Redis"]
    end

    subgraph "LLM Layer"
        GEMINI["Gemini 2.5 Flash"]
        OLLAMA["Ollama (Qwen3.5-4B)"]
        DEBERTA["DeBERTa-v3 (NLI)"]
        BGEM3["BGE-m3 (embeddings)"]
    end

    subgraph Frontend
        NEXTJS["Next.js 16"] --> SIGMA["Sigma.js"]
        NEXTJS --> ZUSTAND["Zustand"]
    end

    subgraph Observability
        LANGSMITH["LangSmith"]
        LANGFUSE["LangFuse"]
    end

    Backend --> |"LLM calls"| GEMINI
    Backend --> |"local models"| OLLAMA
    Backend --> |"faithfulness"| DEBERTA
    Backend --> |"embeddings"| BGEM3
    Frontend --> |"API"| FASTAPI
    Backend --> LANGSMITH
    Backend --> LANGFUSE
```

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API** | FastAPI (async) | REST API, SSE streaming, file upload |
| **KG Engine** | Graphiti (graphiti-core) | Extraction, entity resolution, temporal storage, hybrid retrieval |
| **Graph DB** | Neo4j 5.x + GDS + APOC | Storage, Cypher queries, Leiden clustering |
| **Orchestration** | LangGraph 0.3+ | 8-node chat pipeline, async workers |
| **Extraction LLM** | Gemini 2.5 Flash | Entity/relation extraction via Graphiti |
| **Chat LLM** | Gemini 2.5 Flash | Answer generation with CoT |
| **Local LLM** | Qwen3.5-4B (Ollama) | Conversation memory summarization |
| **NLI** | DeBERTa-v3-large (local) | Faithfulness checking |
| **Embeddings** | BGE-m3 (local) | Semantic search via Graphiti |
| **Task Queue** | arq + Redis | Async book ingestion + clustering |
| **Checkpointing** | PostgreSQL | LangGraph conversation state |
| **Monitoring** | LangSmith + LangFuse | Traces, costs, KG pipeline vs RAG pipeline |
| **Frontend** | Next.js 16 / React 19 | Chat UI, graph explorer |
| **State** | Zustand | Frontend state management |
| **Clustering** | Leiden (Neo4j GDS) | Community detection + LLM summaries |

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **Docker** + Docker Compose
- **uv**: `pip install uv`
- **Ollama** (optional, for local models): [ollama.ai](https://ollama.ai)

### 1. Clone and install

```bash
git clone https://github.com/xairon/WorldRAG.git
cd WorldRAG

uv sync --all-extras           # Python deps
cd frontend && npm install     # Frontend deps
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   GEMINI_API_KEY=...          (required - extraction + chat)
#   GRAPHITI_ENABLED=true       (activate KG v2 pipeline)
```

### 3. Start infrastructure

```bash
docker compose up -d
# Starts: Neo4j + GDS, Redis, PostgreSQL, LangFuse
```

### 4. Start services

```bash
# Terminal 1: API
uv run uvicorn backend.app.main:app --reload --port 8000

# Terminal 2: Workers
uv run arq app.workers.settings.WorkerSettings

# Terminal 3: Frontend
cd frontend && npm run dev
```

### 5. Ingest a book

```bash
# Upload
curl -X POST http://localhost:8000/api/books \
  -F "file=@primal_hunter_book1.epub" \
  -F "title=The Primal Hunter" \
  -F "genre=litrpg"

# Trigger Graphiti extraction (Discovery Mode)
curl -X POST http://localhost:8000/api/books/{book_id}/extract-graphiti \
  -H "Content-Type: application/json" \
  -d '{"saga_id": "primal-hunter", "saga_name": "The Primal Hunter", "book_num": 1}'

# Check induced profile
curl http://localhost:8000/api/saga-profiles/primal-hunter
```

---

## API Reference

### Books

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/books` | Upload book (ePub/PDF/TXT) |
| `GET` | `/api/books` | List all books |
| `GET` | `/api/books/{id}` | Book details + chapters |
| `POST` | `/api/books/{id}/extract-graphiti` | Trigger Graphiti extraction (Discovery/Guided) |
| `DELETE` | `/api/books/{id}` | Delete book + data |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/query` | Send question, get answer (sync) |
| `GET` | `/api/chat/stream` | SSE streaming (tokens + sources) |
| `POST` | `/api/chat/feedback` | Submit thumbs up/down |
| `GET` | `/api/chat/feedback/{thread_id}` | Get feedback for thread |

### Saga Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/saga-profiles` | List all induced profiles |
| `GET` | `/api/saga-profiles/{id}` | Get profile details |
| `PUT` | `/api/saga-profiles/{id}` | Update profile manually |
| `DELETE` | `/api/saga-profiles/{id}` | Delete profile |

### Graph & Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/graph/{book_id}` | Graph data for Sigma.js |
| `GET` | `/api/graph/{book_id}/search` | Entity search |
| `GET` | `/api/health` | Health check (all services) |
| `GET` | `/api/admin/costs` | Cost tracking |
| `GET` | `/api/admin/dlq` | Dead letter queue |

---

## Architecture

### Pipeline Modes

```mermaid
stateDiagram-v2
    [*] --> Upload: EPUB uploaded
    Upload --> Discovery: First book of saga
    Upload --> Guided: SagaProfile exists

    state Discovery {
        [*] --> GraphitiUniversal: add_episode_bulk\n(6 universal types)
        GraphitiUniversal --> Induce: SagaProfileInducer
        Induce --> Profile: SagaProfile\n(types + patterns + relations)
        Profile --> Leiden: Community clustering
        Leiden --> [*]
    }

    state Guided {
        [*] --> GraphitiTyped: add_episode_bulk\n(universal + induced types)
        GraphitiTyped --> DeltaInduce: SagaProfileInducer delta
        DeltaInduce --> LeidenG: Community clustering
        LeidenG --> [*]
    }

    Discovery --> ChatReady
    Guided --> ChatReady
    ChatReady --> [*]: Ready for queries
```

### Chat Pipeline (8-node LangGraph)

```mermaid
graph TD
    A["Router<br/>(3 routes)"] --> B["Graphiti Search<br/>(semantic + BM25 + BFS)"]
    A --> C["Cypher Lookup<br/>(typed entities)"]
    A --> D["Direct<br/>(no retrieval)"]
    B --> E["Context Assembly<br/>(summaries + chunks)"]
    C --> E
    D --> E
    E --> F["Generate<br/>(CoT reasoning)"]
    F --> G{"Faithfulness<br/>NLI check"}
    G --> |"pass"| H["Done"]
    G --> |"fail<br/>(max 2 retries)"| B

    style A fill:#6366f1,color:#fff
    style G fill:#f59e0b,color:#000
    style H fill:#10b981,color:#fff
```

### Data Flow

```mermaid
graph LR
    subgraph "Storage Layer"
        NEO4J["Neo4j<br/>(Graphiti schema)"]
        REDIS["Redis<br/>(saga profiles + cache)"]
        PG["PostgreSQL<br/>(checkpoints + feedback)"]
    end

    subgraph "Processing"
        WORKER["arq Worker<br/>(extraction + clustering)"]
        GRAPHITI["Graphiti Engine"]
    end

    subgraph "API"
        FAST["FastAPI"]
        CHAT["Chat v2 Service"]
    end

    FAST --> |"enqueue"| WORKER
    WORKER --> |"add_episode"| GRAPHITI
    GRAPHITI --> NEO4J
    WORKER --> |"SagaProfile"| REDIS
    WORKER --> |"Leiden"| NEO4J
    CHAT --> |"search"| GRAPHITI
    CHAT --> |"Cypher"| NEO4J
    CHAT --> |"checkpoints"| PG
    FAST --> CHAT
```

---

## Project Structure

```
WorldRAG/
├── backend/app/
│   ├── main.py                              # FastAPI + lifespan (Neo4j, Redis, PG, Graphiti)
│   ├── config.py                            # Pydantic Settings (.env)
│   ├── api/routes/
│   │   ├── books.py                         # Upload + extract-graphiti endpoint
│   │   ├── chat.py                          # Query + stream + feedback (v1/v2 switch)
│   │   ├── saga_profiles.py                 # CRUD for induced ontology profiles
│   │   ├── graph.py                         # Graph explorer for Sigma.js
│   │   └── health.py, admin.py, ...
│   ├── core/
│   │   ├── graphiti_client.py               # Graphiti singleton wrapper
│   │   ├── logging.py                       # structlog setup
│   │   ├── resilience.py                    # Circuit breakers + retries
│   │   └── cost_tracker.py, dead_letter.py
│   ├── services/
│   │   ├── saga_profile/
│   │   │   ├── models.py                    # SagaProfile, InducedEntityType, ...
│   │   │   ├── inducer.py                   # SagaProfileInducer (5-step algorithm)
│   │   │   ├── pydantic_generator.py        # SagaProfile -> Graphiti entity_types
│   │   │   └── temporal.py                  # NarrativeTemporalMapper
│   │   ├── ingestion/
│   │   │   └── graphiti_ingest.py           # Discovery / Guided mode orchestrator
│   │   ├── chat_service_v2.py               # ChatServiceV2 (Graphiti retrieval)
│   │   └── community_clustering.py          # Leiden + LLM community summaries
│   ├── agents/chat_v2/
│   │   ├── graph.py                         # 8-node LangGraph builder
│   │   └── state.py                         # ChatV2State TypedDict
│   └── workers/
│       ├── tasks.py                         # process_book_graphiti + legacy tasks
│       └── settings.py                      # arq config + Graphiti init
├── frontend/                                # Next.js 16 / React 19
│   ├── components/chat/                     # Thread sidebar, sources, citations, feedback
│   ├── components/graph/                    # Sigma.js graph explorer
│   └── lib/utils.ts                         # Dynamic entity type colors/icons
├── docker-compose.prod.yml                  # Production (ports 495xx, GPU, GDS)
├── docker-compose.yml                       # Development
└── docs/
    └── superpowers/specs/                   # Design specs + implementation plans
```

---

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI API key (extraction + chat) |
| `GRAPHITI_ENABLED` | `true` to activate KG v2 pipeline |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection |
| `NEO4J_PASSWORD` | `worldrag` | Neo4j password |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `POSTGRES_URI` | `postgresql://...` | PostgreSQL connection |
| `LLM_CHAT` | `gemini:gemini-2.5-flash` | Chat generation model |
| `LLM_GENERATION` | `gemini:gemini-2.5-flash-lite` | Auxiliary LLM |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `LANGFUSE_HOST` | -- | LangFuse host (self-hosted) |
| `LANGCHAIN_API_KEY` | -- | LangSmith API key |

---

## Testing

```bash
# All new KG v2 tests (121 tests)
uv run python -m pytest backend/tests/test_saga_profile_models.py \
  backend/tests/test_narrative_temporal_mapper.py \
  backend/tests/test_pydantic_generator.py \
  backend/tests/test_graphiti_client.py \
  backend/tests/test_graphiti_ingest.py \
  backend/tests/test_saga_profile_inducer.py \
  backend/tests/test_chat_v2_pipeline.py \
  backend/tests/test_saga_profiles_api.py \
  backend/tests/test_extract_graphiti_endpoint.py \
  backend/tests/test_chat_service_v2.py \
  backend/tests/test_community_clustering.py -v

# Linting
uv run ruff check backend/ --fix
uv run ruff format backend/
```

---

## Research Context

WorldRAG is developed at **LIFAT** (Laboratoire d'Informatique Fondamentale et Appliquee de Tours), Universite de Tours, France.

The project explores automatic Knowledge Graph construction from fiction novels using SOTA tools (Graphiti, Leiden, LangGraph) with a focus on **ontology induction** -- discovering the rules and systems of fictional universes automatically rather than hardcoding them.

### References

- Mo et al. "KGGen: Extracting Knowledge Graphs from Plain Text with Language Models." NeurIPS 2025.
- Rasmussen et al. "Zep: A Temporal Knowledge Graph Architecture for Agent Memory." arXiv:2501.13956.
- Bai et al. "AutoSchemaKG: Automatic Schema-based Knowledge Graph Construction." HKUST, 2025.
- Bian et al. "LLM-empowered Knowledge Graph Construction: A Survey." arXiv:2510.20345.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>WorldRAG</strong> -- Turning novels into knowledge, one chapter at a time.
</p>
