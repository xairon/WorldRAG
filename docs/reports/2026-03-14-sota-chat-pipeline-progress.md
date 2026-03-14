# SOTA Chat Pipeline — Rapport de progression

Date: 2026-03-14
Status: En cours d'implémentation (Chunk 1/8 terminé)

## Résumé

Mise à niveau du pipeline chat WorldRAG vers un agent adaptatif SOTA avec :
- 6 routes d'intention (au lieu de 3)
- Modèles locaux (RTX 3090) + API gratuites/bon marché
- HyDE + multi-query retrieval
- Fidélité NLI (DeBERTa, pas LLM-as-judge)
- Mémoire conversationnelle
- Feedback utilisateur
- UX frontend amélioré

## Documents de référence

| Document | Chemin | Description |
|----------|--------|-------------|
| Design Spec | `docs/superpowers/specs/2026-03-14-full-sota-chat-pipeline-design.md` | Spec complète, 11 sections, approuvée |
| Plan d'implémentation | `docs/superpowers/plans/2026-03-14-sota-chat-pipeline.md` | 28 tâches en 8 chunks, reviewé par 2 reviewers |
| Survey KG SOTA | `docs/research/2026-03-14-kg-construction-sota-survey.md` | Veille techno KGGen/Graphiti/GFM-RAG (pour futur refactoring extraction) |
| Plan features restantes | `docs/superpowers/plans/2026-03-13-remaining-features.md` | Autres features en attente |

## Stack modèles

### Modèles locaux (~10.5GB VRAM)

| Rôle | Modèle | VRAM |
|------|--------|------|
| LLM auxiliaire | Qwen3.5-4B Q8 via Ollama | ~5GB |
| Reranker | zerank-1-small (1.7B) CrossEncoder | ~2GB |
| NLI fidélité | DeBERTa-v3-large (400M) CrossEncoder | ~1.5GB |
| Embeddings | BGE-M3 (568M) — déjà en place | ~0.5GB |

### Modèles API (génération)

| Provider | Modèle | Coût | Usage |
|----------|--------|------|-------|
| Google AI Studio (free) | Gemini 2.5 Flash-Lite | $0 | Par défaut, 30 RPM |
| OpenRouter | DeepSeek V3.2 | ~$0.30/M | Tier upgrade |
| OpenRouter | Kimi K2.5 | ~$1.30/M | Tier premium |
| Local | Qwen3.5-4B | $0 | Fallback offline |

## Progression par Chunk

### Chunk 1: Infrastructure LLM — TERMINÉ

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 1 | Dépendances pyproject.toml (transformers, accelerate, langchain-ollama) | DONE |
| Task 2 | Config Settings (llm_generation, llm_auxiliary, openrouter_api_key, etc.) | DONE |
| Task 3 | Provider branches (openrouter: + local: dans get_langchain_llm) | DONE |
| Task 4 | Local model singletons (zerank-1-small, DeBERTa NLI) | DONE |
| Task 4b | get_embedder() factory dans embeddings.py | DONE |

**Fichiers créés/modifiés :**
- `backend/app/llm/local_models.py` — singletons lazy-loaded pour reranker + NLI
- `backend/app/llm/providers.py` — branches `openrouter:` (ChatOpenAI) + `local:` (ChatOllama)
- `backend/app/llm/embeddings.py` — `get_embedder()` factory
- `backend/app/config.py` — 5 nouveaux champs Settings
- `pyproject.toml` + `uv.lock` — nouvelles dépendances
- Tests: `test_config_new_fields.py`, `test_providers_new_branches.py`, `test_local_models.py` (8/8 passing)

**Commits :**
- `3ab4551` feat(deps): add transformers, accelerate, langchain-ollama dependencies
- `e3cb8b2` feat(config): add SOTA chat pipeline config fields
- `05b2a79` feat(llm): add openrouter and local (ollama) provider branches
- `6196715` feat(llm): add local_models singletons and get_embedder() factory

### Chunk 2: State & Memory (Tasks 5, 6, 17) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 5 | Nouveaux champs ChatAgentState (conversation_summary, entity_memory, hyde_document, etc.) | PENDING |
| Task 6 | Node load_memory (sliding window 6 messages) | PENDING |
| Task 17 | Node summarize_memory (compression every 5 turns via aux LLM) | PENDING |

### Chunk 3: Intent & Query Expansion (Tasks 7, 8) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 7 | Router 6-routes avec parsing JSON (remplace raw text 3-routes) | PENDING |
| Task 8 | Node hyde_expand (hypothetical document + embedding) | PENDING |

### Chunk 4: Retrieval & Reranking (Tasks 9-13) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 9 | Multi-dense retrieval (embed toutes variantes + HyDE) | PENDING |
| Task 10 | KG scoring composite + entity_memory enrichment | PENDING |
| Task 11 | Reranker local zerank-1-small + SSE source streaming | PENDING |
| Task 12 | Chunk deduplication (cosine >0.80) | PENDING |
| Task 13 | Temporal sort pour route timeline | PENDING |

### Chunk 5: Generation & Faithfulness (Tasks 14-16) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 14 | Structured GenerationOutput (Pydantic) avec citations span-level | PENDING |
| Task 15 | Chain-of-thought generation pour routes analytical/timeline | PENDING |
| Task 16 | NLI faithfulness check (DeBERTa, remplace LLM-as-judge) | PENDING |

### Chunk 6: Graph Wiring & Service (Tasks 18-20) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 18 | Topologie 6-routes dans graph.py + migration tests | PENDING |
| Task 19 | ChatService mapping generation_output → ChatResponse | PENDING |
| Task 20 | SSE streaming des sources dans chat_service | PENDING |

### Chunk 7: Feedback System (Tasks 21-22) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 21 | Table PostgreSQL chat_feedback + DDL | PENDING |
| Task 22 | Endpoints API POST/GET feedback | PENDING |

### Chunk 8: Frontend (Tasks 24-28) — EN ATTENTE

| Tâche | Description | Status |
|-------|-------------|--------|
| Task 24 | Source panel collapsible (SSE streaming) | PENDING |
| Task 25 | Citation highlight [Ch.N, §P] | PENDING |
| Task 26 | Feedback buttons (thumbs up/down) | PENDING |
| Task 27 | Thread sidebar (historique conversations) | PENDING |
| Task 28 | Confidence badge (vert/jaune/rouge NLI) | PENDING |

## Phase 2 (différée)

Ces fonctionnalités sont documentées dans le design spec mais pas dans le plan Phase 1 :

- **ColBERT** late interaction retrieval
- **Span verification** (vérification char-offset des citations)
- **Entity disambiguation** (pronoun resolution multi-turn)
- **Parallel decomposition** (sous-questions parallèles pour questions complexes)
- **Self-reflection** loop (le LLM évalue sa propre réponse)
- **RLHF export** (export feedback pour fine-tuning)

## Travail en cours non lié au plan SOTA

Les fichiers modifiés non-stagés dans git proviennent de sessions précédentes (pre-SOTA). Ils incluent des modifications à :
- Chat graph, nodes, tests (implémentation initiale pre-SOTA)
- Reader agent (`backend/app/agents/reader/`)
- Checkpointer (`backend/app/core/checkpointer.py`)
- Frontend chat page, hooks, stores
- Docker compose (PostgreSQL ajouté)

Ces changements doivent être commités séparément avant de continuer l'implémentation SOTA.

## Instructions de reprise

1. **Installer les dépendances** : `python -m uv sync`
2. **Lancer l'infrastructure** : `docker compose up -d` (Neo4j + Redis + PostgreSQL + LangFuse)
3. **Installer Ollama** + pull Qwen3.5-4B : `ollama pull qwen3.5:4b`
4. **Reprendre l'implémentation** : Commencer par Chunk 2 (Tasks 5, 6, 17)
5. **Plan complet** : `docs/superpowers/plans/2026-03-14-sota-chat-pipeline.md`
6. **Spec complète** : `docs/superpowers/specs/2026-03-14-full-sota-chat-pipeline-design.md`

## Future : Refactoring Extraction

Un survey SOTA sur la construction de KG par LLM a été sauvegardé à `docs/research/2026-03-14-kg-construction-sota-survey.md`. Les innovations principales (KGGen, Graphiti, GFM-RAG) sont découplées du pipeline chat — aucun impact sur l'implémentation en cours. Le brainstorm extraction sera fait APRÈS la complétion du pipeline chat.
