# WorldRAG — Plan d'implémentation v3.1

> **Mise à jour v3.1** : Intègre veille SOTA complète « Construction de KG en 2025-2026 », 3 audits (architecture, risques, chef de projet), veille approfondie (ontologies littéraires, monitoring, LangGraph, optimisation coûts, Claude Code). Refocus : **la construction du KG est la priorité #1, les use cases viennent après**.

---

## 1. Vision du projet

### 1.1 Focus principal : le Knowledge Graph

**Le coeur du projet** : Construire un **Knowledge Graph SOTA pour la fiction** — riche, temporel, évolutif, avec un pipeline d'extraction intelligent et un monitoring pro-grade. Le KG est le backbone ; les applications (lecture augmentée, chatbot, wiki) sont des use cases qui viennent *après* que le KG soit solide.

**Ce que ça n'est PAS** : Un simple RAG. C'est un système d'**extraction profonde d'univers fictifs** avec temporalité, structures narratives, systèmes de progression et lore — le tout sur un KG qui évolue chapitre par chapitre et qui peut alimenter n'importe quelle application en aval.

### 1.2 Input / Output

**Input** : Fichiers mixtes (ePub, PDF, TXT) — des séries entières de novels (LitRPG, fantasy, sci-fi).
**Output principal** : Un KG Neo4j complet et validé, avec temporalité par chapitre, source grounding, et ontologie en couches.
**Use cases en aval** (Phase 3+) : Lecture augmentée, chatbot agentic RAG, wiki automatique, API GraphQL.

### 1.3 Positionnement SOTA (février 2026)

Ce projet s'inscrit dans la convergence LLM+KG de 2025-2026 identifiée par l'état de l'art :
- **Extraction** : On utilise LangExtract (Google) plutôt que LLMGraphTransformer (LangChain) car LangExtract offre le **source grounding** (offsets caractères), le multi-pass, et la parallélisation — features absentes de LLMGraphTransformer.
- **Orchestration** : LangGraph comme orchestrateur du pipeline (fan-out/fan-in, checkpointing, retry) plutôt que des pipelines ad-hoc.
- **KG temporel** : Temporalité custom chapter-based (validée par CIDOC-CRM, Wikidata qualifiers) plutôt que Graphiti (schéma incompatible, datetime).
- **Ontologie** : Fondée sur les ontologies académiques (GOLEM 2025, CIDOC-CRM, SEM, DOLCE, OntoMedia) — pas ad-hoc.
- **Two-pass LitRPG** : Regex pour les blue boxes (stats, système) + LLM pour le narratif — un pattern recommandé par la littérature.
- **Validation** : Détection automatique de contradictions via Cypher (inspiré SHACL) — pas juste de l'extraction aveugle.

### 1.4 Technos évaluées et écartées (avec justification SOTA)

| Techno | Pourquoi non |
|--------|-------------|
| **Microsoft GraphRAG** | Trop cher (3-5x tokens), extraction générique, pas de temporalité. LazyGraphRAG intéressant pour la query mais pas pour la construction. |
| **LLMGraphTransformer** (LangChain) | Pas de source grounding (deal-breaker), pas de multi-pass, schéma enforcement plus faible que Pydantic. Strictement inférieur à LangExtract + Instructor pour notre use case. |
| **KGGen** (Stanford) | Triples non typés, pas de schéma enforcement, pas de grounding, pas de temporalité. Algo de clustering intéressant — lire le paper pour le dedup, mais ne pas intégrer l'outil. |
| **BookNLP** | Coréférence sub-70% sur les longs textes. Notre pipeline LLM-based fait mieux. +2GB de deps (PyTorch+TF). Révisiter seulement si l'alias resolution échoue au test. |
| **AutoSchemaKG** | Résout un problème différent (schéma inconnu à l'échelle web). Notre ontologie 3-couches hand-crafted est le bon choix pour la fiction. À monitorer pour l'auto-discovery Layer 3 future. |
| **Graphiti** | Schéma Neo4j incompatible. Double extraction LLM = double coût. datetime vs chapter numbers. |
| **LightRAG** | Pas de Neo4j natif, pas de grounding. Intéressant pour le retrieval dual-level mais pas pour la construction. |
| **LlamaIndex PropertyGraphIndex** | Triplets trop simples, pas de propriétés riches. |
| **Celery** | Sync, lourd. arq est async-natif. |

---

## 2. Stack technique — Décisions finales

### 2.1 Stack backbone retenu

| Techno | Rôle | Justification |
|--------|------|---------------|
| **LangExtract** (Google, 33.6k★) | Extraction d'entités avec grounding | Source grounding exact (offsets caractères), multi-passes pour recall, parallélisation, few-shot adaptable. Optimisé pour Gemini. |
| **LangGraph** (LangChain) | Orchestration pipeline + agentic RAG | StateGraph, fan-out/fan-in parallèle natif, checkpointing PostgreSQL, RetryPolicy natif, streaming SSE, conditional routing. |
| **Neo4j 5.x** | Graph DB unique | LPG + vector index natif + fulltext Lucene + Cypher. Un seul service graph+vector. |
| **neo4j-graphrag** | RAG retrievers production | VectorCypherRetriever, HybridCypherRetriever, Text2CypherRetriever. |
| **Instructor** (jxnl) | Extraction structurée + réconciliation | Multi-provider, Pydantic schemas stricts, retry intégré, validation. |
| **Voyage AI voyage-3.5** | Embeddings SOTA | 32K context, Matryoshka (dims ajustables), +8% vs OpenAI. Coût négligeable ($0.60/10K chunks). |
| **Cohere Rerank v3.5** | Reranking | Best-in-class, multilingue. |
| **arq + Redis** | Task queue | Async natif, léger, parfait avec FastAPI. Job dispatch book-level. |
| **FastAPI** | API backend | Async, OpenAPI, SSE natif. |
| **Next.js 15 + React 19** | Frontend | SSR, App Router, TypeScript. |
| **LangFuse** (self-hosted) | Monitoring LLM + observabilité | MIT open-source, $0 self-hosted, cost tracking automatique, trace waterfall, intégration LangGraph native. |
| **structlog** | Logging structuré | Async-native, contextvars pour FastAPI, JSON output. |
| **PostgreSQL** | Checkpointing LangGraph + LangFuse | `langgraph-checkpoint-postgres` pour resume-after-crash. LangFuse DB. |

### 2.2 Technos retirées du plan (vs v2)

| Techno | Pourquoi retirée |
|--------|-----------------|
| **Graphiti** | Schéma Neo4j incompatible avec ontologie custom (`:EntityNode` vs `:Character`). Double extraction LLM (re-extrait par-dessus LangExtract = double coût). `reference_time` en datetime, pas chapter numbers. Temporalité custom en Cypher = plus simple et adapté. |
| **graphiti-core** | Remplacé par écriture directe Neo4j avec temporalité custom `valid_from_chapter`/`valid_to_chapter`. |

### 2.3 Technos ajoutées au plan (vs v2)

| Techno | Rôle |
|--------|------|
| **LangFuse** (self-hosted) | Monitoring complet de tous les LLM calls (extraction + chat + reader) |
| **structlog** | Logging structuré JSON pour tout le pipeline |
| **PostgreSQL** | Checkpointing LangGraph + LangFuse backend |
| **tenacity** | Retry granulaire pour sub-calls dans les nodes LangGraph |
| **aiolimiter** | Rate limiting async par provider API |
| **tiktoken** | Token counting pré-vol pour estimations de coût |
| **langgraph-checkpoint-postgres** | Persistence des checkpoints extraction pipeline |

---

## 3. Optimisation des coûts API — Stratégie complète

### 3.1 Model tiering — Le bon modèle pour la bonne tâche

```env
# === Extraction (Gemini = moins cher + context caching) ===
LANGEXTRACT_MODEL=gemini-2.5-flash          # $0.15/1M input, context caching 75% off
LANGEXTRACT_PASSES=2                         # Réduit de 3 (tester qualité)
LANGEXTRACT_BATCH_CHAPTERS=10                # Batch 10 chapitres/appel (Gemini 1M context)

# === Réconciliation/Classification (GPT-4o-mini = 16.7x moins cher que GPT-4o) ===
LLM_RECONCILIATION=openai:gpt-4o-mini       # Changé de gpt-4o
LLM_CLASSIFICATION=openai:gpt-4o-mini
LLM_DEDUP=openai:gpt-4o-mini
LLM_CYPHER=openai:gpt-4o-mini               # Changé de gpt-4o, fallback gpt-4o

# === User-facing (qualité prioritaire) ===
LLM_CHAT=openai:gpt-4o                      # Gardé — face utilisateur
```

### 3.2 Stratégie de caching multi-niveaux

| Niveau | Mécanisme | Économie |
|--------|-----------|----------|
| **Prompt caching Gemini** | 4 `CachedContent` (1/passe extraction), each chargé avec system prompt + few-shot examples (≥32K tokens). 75% off sur tokens cachés. | ~60% sur extraction |
| **OpenAI Batch API** | JSONL batch pour réconciliation + dédup (50% off, 24h turnaround). | 50% sur réconciliation |
| **OpenAI auto prompt cache** | System prompts identiques across chapters (≥1024 tokens prefix). 50% off automatique. | ~15% sur Instructor calls |
| **Semantic cache Redis** | Cache chat queries similaires (cosine ≥0.95). Évite LLM calls redondants. | 30-60% sur chat |
| **Chapter context cache** | Cache `GET /api/reader/{book}/chapter/{n}` tant que pas de nouveau chapitre ingéré. | 100% cache hit reader |

### 3.3 Progressive extraction — Ne pas tout extraire partout

```python
# Seul Pass 1 (Characters) tourne sur TOUS les chapitres
# Les autres passes sont conditionnelles :
PROGRESSION_KEYWORDS = {"level", "skill", "class", "evolution", "tier", "breakthrough"}
EVENT_KEYWORDS = {"battle", "fight", "death", "kill", "discover", "reveal", "war"}

# Pass 2 (Systems)  → ~60% des chapitres (keyword match)
# Pass 3 (Events)   → ~40% des chapitres (keyword match)
# Pass 4 (Lore)     → ~30% des chapitres (LLM classification GPT-4o-mini, ~$0.0001/chapitre)
```

### 3.4 Estimations de coût

| Scénario | Novel 1000 chapitres | Coût/chapitre |
|----------|---------------------|---------------|
| **Naïf (GPT-4o tout)** | ~$466 | $0.47 |
| **Optimisé (notre stack)** | **~$8-12** | **$0.008-0.012** |
| **Série 2000 chapitres** | **~$17-25** | $0.008-0.012 |

---

## 4. Ontologie — Schéma du Knowledge Graph (fondé sur la littérature)

> Basé sur : CIDOC-CRM (événements/temporalité), SEM (structure événementielle), OntoMedia (entités narratives), DOLCE (taxonomie temporelle), Wikidata (propriétés caractères), FRBRoo (bibliographie).

### 4.1 Layer 1 — Core Narrative (universel, tous genres)

```cypher
// === BIBLIOGRAPHIQUE (FRBRoo/LRMoo) ===
(:Series {name, author, genre, description})
(:Book {title, order_in_series, total_chapters, publication_date})
(:Chapter {number, title, book_id, summary, word_count})
(:Chunk {text, position, chapter_id, token_count, embedding})

(:Series)-[:CONTAINS_WORK {position}]->(:Book)
(:Book)-[:HAS_CHAPTER {position}]->(:Chapter)
(:Chapter)-[:HAS_CHUNK {position}]->(:Chunk)

// === PERSONNAGES (OntoMedia + Wikidata + Bamman) ===
(:Character {
    name, canonical_name, aliases[],
    description,
    role,          // protagonist|antagonist|mentor|sidekick|ally|minor
    species,       // human|elf|dwarf|AI|dragon
    gender,
    first_appearance_chapter
})

(:Character)-[:RELATES_TO {
    type,              // ally|enemy|mentor|family|romantic|rival|patron|subordinate
    subtype,           // father|mother|sibling|spouse (for family)
    sentiment,         // -1.0 to 1.0
    valid_from_chapter,
    valid_to_chapter,
    context
}]->(:Character)

(:Character)-[:MEMBER_OF {
    role,              // leader|member|founder|defector
    valid_from_chapter,
    valid_to_chapter
}]->(:Faction)

(:Faction {name, description, type, alignment})

// === ÉVÉNEMENTS (SEM + DOLCE + LODE) ===
// Taxonomie DOLCE : state_change|action|process|achievement
(:Event {
    name, description,
    event_type,        // "action"|"state_change"|"achievement"|"process"|"dialogue"
    significance,      // "minor"|"moderate"|"major"|"critical"|"arc_defining"
    chapter_start,
    chapter_end        // null pour événements ponctuels
})

(:Character)-[:PARTICIPATES_IN {
    role              // "agent"|"patient"|"beneficiary"|"witness"|"cause"
}]->(:Event)

(:Event)-[:OCCURS_AT]->(:Location)
(:Event)-[:CAUSES]->(:Event)
(:Event)-[:ENABLES]->(:Event)
(:Event)-[:OCCURS_BEFORE]->(:Event)
(:Event)-[:PART_OF]->(:Arc)

// Grounding source (LODE illustrate + LangExtract offsets)
(:Event)-[:GROUNDED_IN {char_offset_start, char_offset_end}]->(:Chunk)
(:Character)-[:MENTIONED_IN {char_offset_start, char_offset_end}]->(:Chunk)

// === STRUCTURE NARRATIVE (Propp + Narratologie) ===
(:Arc {
    name, description,
    arc_type,          // "main_plot"|"subplot"|"character_arc"|"world_arc"
    chapter_start, chapter_end,
    status             // "active"|"completed"|"abandoned"
})

(:NarrativeFunction {
    name,              // "Call to Adventure"|"Trial"|"Boss Battle"|"Power Up"
    propp_code,        // code Propp optionnel
    description
})

(:Arc)-[:STRUCTURED_BY {order}]->(:NarrativeFunction)
(:Event)-[:FULFILLS]->(:NarrativeFunction)

// === MONDE (CIDOC-CRM places) ===
(:Location {
    name, description,
    location_type,     // "city"|"dungeon"|"realm"|"continent"|"pocket_dimension"
    parent_location_name
})

(:Location)-[:PART_OF]->(:Location)
(:Location)-[:CONNECTED_TO {method}]->(:Location)

(:Character)-[:LOCATED_AT {
    valid_from_chapter, valid_to_chapter
}]->(:Location)

// === ITEMS & OBJETS ===
(:Item {
    name, description,
    item_type,         // "weapon"|"armor"|"consumable"|"artifact"|"key_item"
    rarity             // "common"|"uncommon"|"rare"|"epic"|"legendary"|"unique"
})

(:Character)-[:POSSESSES {
    valid_from_chapter, valid_to_chapter,
    acquisition_method  // "loot"|"craft"|"gift"|"purchase"|"quest_reward"
}]->(:Item)

// === CONCEPTS & LORE ===
(:Concept {name, description, domain})
(:Prophecy {name, description, status})  // "unfulfilled"|"fulfilled"|"subverted"
```

### 4.2 Layer 2 — Genre-specific (LitRPG / Fantasy / Sci-Fi)

```cypher
// === LITRPG: SYSTÈME DE PROGRESSION ===
(:System {name, description, system_type})
    // system_type: "cultivation"|"class_based"|"skill_based"|"stat_based"|"hybrid"

(:Class {name, description, tier, requirements[], system_name})
(:Skill {name, description, skill_type, rank, effects[], system_name})
    // skill_type: "active"|"passive"|"racial"|"class"|"profession"|"unique"
    // rank: "common"|"uncommon"|"rare"|"epic"|"legendary"|"transcendent"
(:Title {name, description, effects[], requirements})
(:Level {value, realm, stage})
    // realm: "mortal"|"D-grade"|"C-grade"|"B-grade"|"A-grade"|"S-grade"

(:Character)-[:HAS_CLASS {valid_from_chapter, valid_to_chapter, acquisition_event}]->(:Class)
(:Character)-[:HAS_SKILL {valid_from_chapter, valid_to_chapter, skill_level}]->(:Skill)
(:Character)-[:HAS_TITLE {acquired_chapter}]->(:Title)
(:Character)-[:AT_LEVEL {valid_from_chapter, valid_to_chapter}]->(:Level)

(:Class)-[:EVOLVES_INTO {requirements}]->(:Class)
(:Skill)-[:EVOLVES_INTO]->(:Skill)
(:Skill)-[:BELONGS_TO]->(:Class)

// === CRÉATURES & RACES ===
(:Race {name, description, traits[], typical_abilities[]})
(:Creature {name, description, species, threat_level, habitat})

(:Character)-[:IS_RACE]->(:Race)
(:Creature)-[:INHABITS]->(:Location)
```

### 4.3 Layer 3 — Series-specific (configurable par série)

```cypher
// Exemple pour The Primal Hunter :
(:Bloodline {name, description, owner_name, effects[]})
(:PrimordialChurch {deity_name, domain, blessing_effects[]})
(:AlchemyRecipe {name, ingredients[], effects[], rarity})
(:Profession {name, tier, type})
```

> **Principe** : Layer 3 est défini par un fichier YAML de configuration par série. Les prompts LangExtract sont générés dynamiquement à partir de cette config. Pour les nouvelles séries, AutoSchemaKG (HKUST 2025) pourra être exploré pour auto-discovery du Layer 3.

### 4.4 Fondements académiques

L'ontologie est fondée sur les travaux suivants :
- **GOLEM** (MDPI 2025) — Ontologie formelle pour la fiction et la narration, extensible, alignée CIDOC-CRM + DOLCE. Référence pour valider la complétude de notre Layer 1. [ontology.golemlab.eu](https://ontology.golemlab.eu/)
- **CIDOC-CRM** (ISO 21127) — Modèle événement-temporalité de référence pour le patrimoine culturel
- **SEM** (VU Amsterdam) — Simple Event Model : Event → Actor → Place → Time (notre modèle événementiel)
- **DOLCE** — Taxonomie temporelle : State / Event / Process / Achievement (classification des événements)
- **OntoMedia** (Southampton) — Distinction fabula/sjuzhet (flashbacks), entités narratives
- **Wikidata** — Modèle qualifieur temporal (valid_from/valid_to sur les propriétés)
- **FRBRoo/LRMoo** — Hiérarchie bibliographique (Series → Book → Chapter)
- **Bamman et al.** (CMU) — Modèle computationnel des personnages fictifs (rôles, agency, sentiment)

### 4.5 Gestion de la cohérence multi-volumes (patterns SOTA)

```cypher
// === RETCONS ===
// Ne jamais supprimer. Annoter :
(:Fact)-[:RETCONNED_BY {retcon_chapter, reason}]->(:Fact)
// Flags: canonical (true/false), source_reliability (narrator, character, system)

// === NARRATEURS NON FIABLES / POV MULTIPLES ===
// Modéliser le statut épistémique :
(:Event)-[:PERCEIVED_BY {
    reliability,        // "narrator"|"character_pov"|"system"|"flashback"
    perceiver_name,     // quel personnage rapporte ce fait
    confidence          // 0.0-1.0
}]->(:Character)

// === DEUX INDEX TEMPORELS ===
(:Event {
    chapter_start: 200,        // discourse order (où le lecteur le lit)
    fabula_order: 150,         // temps diégétique (chronologie in-universe)
    is_flashback: true
})
```

### 4.6 Temporalité — Modèle custom (chapitre-based, pas datetime)

> Décision d'audit : les numéros de chapitres sont plus naturels et précis que les datetime pour les romans.

```cypher
// Toutes les relations temporelles portent valid_from_chapter / valid_to_chapter
// Pas de datetime — on utilise des integers chapitres

// Requête : état d'un personnage à un chapitre donné
MATCH (c:Character {name: $name})-[r]->(target)
WHERE r.valid_from_chapter <= $chapter
  AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter >= $chapter)
RETURN type(r) AS relation, target

// Index pour performance temporelle
CREATE INDEX rel_temporal FOR ()-[r:HAS_CLASS]-() ON (r.valid_from_chapter)
CREATE INDEX rel_validity FOR ()-[r:AT_LEVEL]-() ON (r.valid_from_chapter, r.valid_to_chapter)

// Contrainte d'unicité pour éviter les doublons en écriture concurrente
CREATE CONSTRAINT character_unique FOR (c:Character) REQUIRE c.canonical_name IS UNIQUE
CREATE CONSTRAINT skill_unique FOR (s:Skill) REQUIRE (s.name, s.system_name) IS UNIQUE
CREATE CONSTRAINT location_unique FOR (l:Location) REQUIRE l.name IS UNIQUE
```

### 4.5 Distinction fabula / sjuzhet (OntoMedia)

```cypher
// fabula_order = ordre chronologique in-universe (pour flashbacks)
// chapter_start = discourse position (où le lecteur le rencontre)
(:Event {
    name: "Battle of X",
    chapter_start: 200,        // le lecteur le lit au ch.200
    fabula_order: 150,         // mais ça s'est passé avant le ch.150 en timeline
    is_flashback: true
})
```

---

## 5. Architecture du système

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WorldRAG Architecture v3                        │
│                                                                         │
│  ┌──────────┐     ┌───────────────────────────────────────────────────┐ │
│  │          │     │              FastAPI Backend                       │ │
│  │ Next.js  │◄───►│                                                   │ │
│  │ Frontend │ API │  ┌─────────────┐    ┌──────────────────────────┐  │ │
│  │          │ +SSE│  │  LangGraph  │    │   LangExtract            │  │ │
│  │ - Reader │     │  │  3 Graphs:  │    │   + Instructor           │  │ │
│  │ - Graph  │     │  │  extraction │    │   4 passes parallèles    │  │ │
│  │ - Chat   │     │  │  reader     │    │   + réconciliation       │  │ │
│  │ - Library│     │  │  chat_agent │    └────────────┬─────────────┘  │ │
│  │ - Monitor│     │  └──────┬──────┘                 │                │ │
│  └──────────┘     │         │                        │                │ │
│                   │  ┌──────▼────────────────────────▼──────────────┐ │ │
│                   │  │              Neo4j 5.x (direct)              │ │ │
│                   │  │  - Knowledge Graph (ontologie custom)        │ │ │
│                   │  │  - Vector Index (Voyage 3.5)                 │ │ │
│                   │  │  - Fulltext Index (Lucene)                   │ │ │
│                   │  │  - Temporalité custom (valid_from/to_chapter)│ │ │
│                   │  └─────────────────────────────────────────────┘ │ │
│                   │                                                   │ │
│                   │  ┌──────────┐  ┌────────────┐  ┌──────────────┐  │ │
│                   │  │  Redis   │  │ PostgreSQL │  │  LangFuse    │  │ │
│                   │  │ - arq    │  │ - LG ckpt  │  │  (self-host) │  │ │
│                   │  │ - cache  │  │ - LangFuse │  │  - traces    │  │ │
│                   │  │ - DLQ    │  │   backend  │  │  - costs     │  │ │
│                   │  │ - pub/sub│  │            │  │  - dashboard │  │ │
│                   │  └──────────┘  └────────────┘  └──────────────┘  │ │
│                   └───────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ LLM Providers: OpenAI (GPT-4o/mini) │ Gemini (2.5 Flash) │ Ollama ││
│  │ Voyage AI (embeddings)  │  Cohere (reranking)                      ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Trois LangGraph graphs séparés

> Décision d'audit : pas un monolithe, 3 graphs spécialisés.

**Graph 1 : `extraction_graph`** — Pipeline d'extraction par chapitre
```
START ──► [PARALLEL fan-out]
           ├── extract_characters (LangExtract + RetryPolicy)
           ├── extract_systems    (LangExtract + RetryPolicy) [conditionnel]
           ├── extract_events     (LangExtract + RetryPolicy) [conditionnel]
           └── extract_lore       (LangExtract + RetryPolicy) [conditionnel]
       ──► [fan-in] reconcile (Instructor)
       ──► check_cost_ceiling [conditionnel: continue | abort]
       ──► write_to_neo4j (Cypher direct)
       ──► END
```
- Checkpointed : `AsyncPostgresSaver`, thread_id = `extract-{book_id}-ch{chapter_number}`
- Resume après crash : `ainvoke(None, config)` reprend au noeud échoué
- `Annotated[list, operator.add]` pour accumulation parallèle

**Graph 2 : `reader_context_graph`** — Assemblage contexte lecture augmentée
```
START ──► fetch_chapter_entities
       ──► [PARALLEL]
           ├── get_character_states (Cypher temporel)
           ├── get_location (Cypher)
           └── get_timeline_position (Cypher)
       ──► assemble_context
       ──► END
```
- Pas de checkpointing (rapide, idempotent)
- Principalement des reads Neo4j, pas des LLM calls

**Graph 3 : `chat_agent_graph`** — Agentic RAG (Adaptive + Corrective + Self-RAG)
```
START ──► classify
       ──► [conditional: retrieve | cypher_direct]
       ──► rerank (Cohere)
       ──► grade [conditional: generate | rewrite → retrieve (loop, max 3)]
       ──► generate
       ──► self_check [conditional: END | rewrite (loop, max 2)]
```
- Checkpointed pour mémoire conversationnelle
- `with_fallbacks()` sur le LLM (GPT-4o → Claude → GPT-4o-mini)
- Guard max rewrite count (empêche boucles infinies)

### 5.2 Architecture deux niveaux : arq + LangGraph

```
arq worker (book-level)
  │
  for each chapter:
    │
    ├── Check checkpoint (skip if already completed)
    ├── LangGraph extraction_graph.ainvoke() (per-chapter intelligence)
    ├── Save checkpoint to PostgreSQL
    ├── Publish progress via Redis pub/sub → SSE → frontend
    └── On failure: DLQ Redis + continue next chapter
```

---

## 6. Observabilité & Monitoring — Stack complet

### 6.1 LangFuse (self-hosted) — Monitoring LLM

```yaml
# docker-compose.langfuse.yml
services:
  langfuse:
    image: langfuse/langfuse:2
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_URL: http://localhost:3001
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      SALT: ${LANGFUSE_SALT}
      TELEMETRY_ENABLED: "false"
    depends_on:
      - langfuse-db

  langfuse-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data
```

**Intégration LangGraph** : Un callback handler par invocation.
```python
from langfuse.callback import CallbackHandler

handler = CallbackHandler(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
    tags=["extraction", "chapter-42"],
)
result = await extraction_graph.ainvoke(state, config={"callbacks": [handler]})
```

**Intégration LangExtract** : Spans manuels via SDK LangFuse.
```python
trace = langfuse.trace(name=f"extraction-{pass_name}", metadata={...})
span = trace.span(name=f"langextract-{pass_name}")
# ... extraction ...
span.generation(name=f"llm-{pass_name}", model="gemini-2.5-flash", usage={...})
```

**Tableau de bord** : Coût par chapitre, par passe, par modèle, par livre. Latence par noeud. Erreurs.

### 6.2 structlog — Logging structuré

```python
# Chaque log inclut automatiquement request_id, chapter_id, pipeline_stage
logger.info("extraction_pass_completed",
    pass_name="characters",
    entity_count=12,
    tokens_used=3450,
    cost_usd=0.003,
    duration_ms=2134,
)
```

Middleware FastAPI pour injection automatique du contexte request dans tous les logs.

### 6.3 Error handling — Stack résilience

| Couche | Mécanisme | Implémentation |
|--------|-----------|---------------|
| **Node-level retry** | `RetryPolicy(max_attempts=3, retry_on=(RateLimitError, TimeoutError))` | LangGraph natif sur `add_node()` |
| **Sub-call retry** | `tenacity` avec exponential backoff + jitter | Décorateur sur fonctions LLM internes |
| **Model fallback** | `primary.with_fallbacks([fallback_1, fallback_2])` | LangChain-core natif |
| **Circuit breaker** | Custom : 5 failures → OPEN 60s → HALF_OPEN 3 calls → CLOSED | Par provider (openai_breaker, gemini_breaker) |
| **Dead letter queue** | Redis list `worldrag:dlq:extraction` | Chapitres en échec stockés pour retry manuel |
| **Cost ceiling** | Conditional edge LangGraph après reconciliation | Abort si coût accumulé > seuil |
| **Checkpointing** | `AsyncPostgresSaver` par chapitre | Resume `ainvoke(None, config)` après crash |
| **Rate limiting** | `aiolimiter.AsyncLimiter` + `asyncio.Semaphore` | Par provider API dans les nodes |

### 6.4 Endpoint admin monitoring

```
GET /api/admin/costs                    → Coûts LLM agrégés par provider/modèle/livre
GET /api/admin/pipeline/{book_id}       → Statut pipeline (chapitre en cours, erreurs, DLQ)
GET /api/admin/dlq                      → Dead letter queue (chapitres en échec)
POST /api/admin/dlq/{id}/retry          → Retry un chapitre échoué
GET /api/admin/extraction-quality       → Métriques qualité (entités/chapitre, doublons détectés)
```

---

## 7. Pipeline d'extraction — Architecture SOTA KG-first

> **C'est LA phase critique du projet.** La qualité du KG détermine la qualité de toutes les applications en aval.

### 7.1 Two-pass extraction pattern (recommandé SOTA pour LitRPG)

Les sagas LitRPG contiennent des **données semi-structurées** (blue boxes, fenêtres de stats, notifications système) directement dans le texte narratif. C'est un avantage : ces éléments sont bien plus faciles à extraire par regex/pattern matching que par LLM.

```
Pour chaque chapitre :
│
├─► PASSE 0 : Pré-extraction structurelle (REGEX, $0, instantané)
│   │
│   │  Patterns à détecter :
│   │  ┌─────────────────────────────────────┐
│   │  │ [Skill Acquired: Arcane Hunter's    │ ← regex: \[.*?Acquired:.*?\]
│   │  │  Arrow - Legendary]                 │
│   │  │ Level: 87 → 88                      │ ← regex: Level:\s*\d+\s*→\s*\d+
│   │  │ +5 Perception, +3 Agility           │ ← regex: \+\d+\s+\w+
│   │  │ Class: Arcane Hunter (C-grade)      │ ← regex: Class:\s*.+?\(.*?grade\)
│   │  │ Title earned: Progenitor            │ ← regex: Title\s+earned:\s*.+
│   │  └─────────────────────────────────────┘
│   │
│   │  → structured_data[] (skills, levels, stats, classes, titles)
│   │  → Pas d'appel API. Gratuit. Fiable à ~95% sur les blue boxes.
│   │  → char_offset_start/end pour chaque match (grounding natif)
│   │
├─► PASSE 1-4 : Extraction LLM (LangExtract + LangGraph fan-out)
│   │  → enrichie par les résultats de la passe 0
│   │  → le prompt LLM inclut les entités déjà trouvées par regex
│   │  → réduit le travail LLM et améliore la cohérence
```

### 7.2 Flux complet du pipeline d'extraction

```
Pour chaque chapitre (via arq worker) :
│
├─► Check checkpoint PostgreSQL (skip if done)
│
├─► PASSE 0 : Regex/pattern extraction (blue boxes, stats, notifications)
│   → structured_data[] avec grounding offsets
│
├─► LangGraph extraction_graph :
│   │
│   ├─► [PARALLEL fan-out, operator.add reducers]
│   │   │
│   │   ├─► extract_characters (LangExtract, Gemini 2.5 Flash)
│   │   │   prompt: "Extract characters, relationships, dialogue attribution..."
│   │   │   context: structured_data[] de Passe 0 (entités déjà identifiées)
│   │   │   extraction_passes=2, max_workers=10
│   │   │   → characters[] avec source grounding (offsets)
│   │   │
│   │   ├─► extract_systems (CONDITIONNEL: keyword match OU passe 0 non-vide)
│   │   │   prompt: "Extract classes, skills, levels, items, power systems..."
│   │   │   context: structured_data[] de Passe 0 (stats déjà parsées)
│   │   │   → systems[], skills[], items[]
│   │   │
│   │   ├─► extract_events (CONDITIONNEL: keyword match)
│   │   │   prompt: "Extract events, battles, discoveries, deaths..."
│   │   │   → events[] avec temporal anchoring (fabula + discourse order)
│   │   │
│   │   └─► extract_lore (CONDITIONNEL: LLM classification $0.0001)
│   │       prompt: "Extract locations, creatures, races, factions, world rules..."
│   │       → locations[], creatures[], concepts[]
│   │
│   ├─► [fan-in] reconcile (Instructor GPT-4o-mini)
│   │   - Fusion regex_entities + llm_entities
│   │   - Dédup entités (exact → fuzzy thefuzz → LLM-as-Judge pour cas ambigus)
│   │   - Résolution coréférences cross-passe (alias → canonical_name)
│   │   - Validation Pydantic stricte contre schemas ontologie
│   │   - Score de confiance par entité (seuil ≥ 0.7)
│   │   - Embedding similarity pour entity linking cross-chapitre
│   │
│   ├─► check_cost_ceiling [conditional edge: abort si budget dépassé]
│   │
│   ├─► write_to_neo4j (Cypher MERGE direct)
│   │   - batch_id UUID par chapitre (pour rollback)
│   │   - MERGE avec contraintes d'unicité
│   │   - Relations temporelles avec valid_from_chapter
│   │   - Source provenance: chaque triple → chunk_id + char_offsets
│   │
│   └─► validate_consistency (Cypher queries de validation)
│       - Détection contradictions (personnage à 2 lieux simultanément)
│       - Cohérence temporelle (level ne décroît jamais, sauf retcon explicite)
│       - Alertes logged dans LangFuse, pas de blocage
│
├─► Save checkpoint "completed" dans PostgreSQL
├─► Log coûts + métriques qualité dans LangFuse
└─► Publish progress Redis pub/sub → SSE frontend
```

### 7.3 Entity resolution cross-chapitre/cross-livre

> Pattern recommandé SOTA : embedding similarity + LLM-as-Judge

```python
# Approche 3 niveaux pour la résolution d'entités cross-chapitre :

# Niveau 1 — Exact match (gratuit, instantané)
# "Jake Thayne" == "Jake Thayne" → même entité

# Niveau 2 — Fuzzy match + alias (thefuzz, gratuit)
# "Jake" / "Jake Thayne" / "Thayne" / "the Arcane Hunter" → score > 0.85

# Niveau 3 — Embedding similarity + LLM-as-Judge (pour cas ambigus)
# Embedding("Jake Thayne, protagonist, Arcane Hunter") vs
# Embedding("Jacob T., hunter from Earth") → cosine > 0.90
# → LLM confirme : "sont-ils la même entité ?" avec contexte
```

### 7.4 Validation de cohérence automatique (pattern SHACL-like)

```cypher
// === RÈGLES DE VALIDATION POST-INGESTION ===

// R1: Un personnage ne peut pas être à deux endroits au même chapitre
MATCH (c:Character)-[r1:LOCATED_AT]->(l1:Location),
      (c)-[r2:LOCATED_AT]->(l2:Location)
WHERE r1.valid_from_chapter <= r2.valid_from_chapter
  AND (r1.valid_to_chapter IS NULL OR r1.valid_to_chapter >= r2.valid_from_chapter)
  AND l1 <> l2
RETURN c.name AS character, l1.name AS loc1, l2.name AS loc2,
       r1.valid_from_chapter AS from1, r2.valid_from_chapter AS from2
// → Alerte "contradiction_location" dans LangFuse

// R2: Le level d'un personnage ne décroît jamais (sauf retcon)
MATCH (c:Character)-[r1:AT_LEVEL]->(l1:Level),
      (c)-[r2:AT_LEVEL]->(l2:Level)
WHERE r2.valid_from_chapter > r1.valid_from_chapter
  AND l2.value < l1.value
RETURN c.name, l1.value AS old_level, l2.value AS new_level
// → Alerte "level_regression" dans LangFuse

// R3: Une skill ne peut pas appartenir à deux classes incompatibles
MATCH (s:Skill)-[:BELONGS_TO]->(c1:Class),
      (s)-[:BELONGS_TO]->(c2:Class)
WHERE c1 <> c2
RETURN s.name, c1.name AS class1, c2.name AS class2
// → Alerte "skill_conflict" dans LangFuse

// R4: Événement référence un personnage qui n'existe pas encore
MATCH (e:Event)-[:PARTICIPATES_IN]-(c:Character)
WHERE c.first_appearance_chapter > e.chapter_start
RETURN e.name, c.name, e.chapter_start, c.first_appearance_chapter
// → Alerte "temporal_paradox" dans LangFuse
```

### 7.5 Rollback par chapitre

```cypher
// Chaque écriture porte un batch_id UUID
// Rollback d'un chapitre entier si la qualité est insuffisante :
MATCH (n) WHERE n.batch_id = $batch_id DETACH DELETE n
MATCH ()-[r]->() WHERE r.batch_id = $batch_id DELETE r
```

### 7.6 Dry-run mode

Mode extraction sans écriture Neo4j : génère un rapport JSON de ce qui serait créé. Pour validation manuelle avant commit. Essentiel pour les premiers chapitres d'une nouvelle série.

### 7.7 Métriques de qualité d'extraction

| Métrique | Mesure | Cible |
|----------|--------|-------|
| **Entités/chapitre** | Nombre moyen d'entités extraites | 15-40 |
| **Doublons détectés** | % d'entités fusionnées par le reconciler | < 20% |
| **Contradictions** | Nombre d'alertes validation Cypher | < 5% des chapitres |
| **Confiance moyenne** | Score Instructor moyen des entités | ≥ 0.8 |
| **Grounding coverage** | % d'entités avec char_offset | ≥ 90% |
| **Coût/chapitre** | Coût LLM total par chapitre | < $0.02 |
| **Gold standard F1** | Precision/Recall vs benchmark annoté (5 chapitres) | ≥ 0.75 |

---

## 8. Agentic RAG — Chat Engine via LangGraph

### 8.1 State

```python
class WorldRAGState(TypedDict):
    messages: list[BaseMessage]
    query_type: str           # factual|explorative|relational|narrative|system
    entities_mentioned: list[str]
    needs_temporal: bool
    chapter_context: int | None
    retrieved_docs: list[str]
    relevance_score: float
    rewrite_count: int
    max_rewrites: int         # guard: max 3
    cost_entries: Annotated[list[dict], operator.add]
    final_answer: str
```

### 8.2 Hybrid retrieval 3-source + RRF

```
Query ──► [PARALLEL]
          ├── Vector search (Voyage 3.5 embeddings via neo4j-graphrag)
          ├── Graph traversal (2-hop Cypher from mentioned entities)
          └── Fulltext search (Lucene BM25 via Neo4j)
      ──► RRF (Reciprocal Rank Fusion)
      ──► Cohere Rerank v3.5 (top-100 → top-10)
      ──► LLM generation
```

### 8.3 Tools agent

```python
@tool
async def search_knowledge_graph(query: str) -> str:
    """Recherche hybride dans le KG (semantic + keyword + graph)"""

@tool
async def execute_cypher(cypher: str) -> str:
    """Exécute une requête Cypher read-only (RBAC Neo4j user read-only + timeout)"""

@tool
async def get_character_state(name: str, chapter: int) -> str:
    """État complet d'un personnage à un chapitre donné"""

@tool
async def get_timeline(chapter_start: int, chapter_end: int) -> str:
    """Événements entre deux chapitres"""

@tool
async def get_entity_relations(entity_name: str, depth: int = 2) -> str:
    """Relations d'une entité dans le graphe (k-hop)"""

@tool
async def compare_character_states(name: str, chapter_a: int, chapter_b: int) -> str:
    """Diff d'état d'un personnage entre deux chapitres"""
```

**Sécurité Cypher** : Neo4j user read-only avec RBAC + `dbms.transaction.timeout=30s` + whitelist MATCH/RETURN/WHERE/WITH.

---

## 9. Lecture augmentée — Premier use case

### 9.1 API

```
GET /api/reader/{book_id}/chapter/{chapter_number}

Response: {
    "chapter": { "text": "...", "title": "...", "number": 42 },
    "context": {
        "characters_present": [
            { "name": "Jake Thayne", "role": "protagonist",
              "current_level": 87, "current_class": "Arcane Hunter",
              "recent_events": ["Defeated the Monarch", "Acquired Pillar skill"],
              "relationships_here": ["Villy (patron)", "Sylphie (companion)"] }
        ],
        "active_skills_used": [...],
        "location": { "name": "Nevermore", "type": "dungeon", "description": "..." },
        "timeline_position": { "arc": "Nevermore Arc", "progress": "3/15" },
        "grounded_entities": [
            { "text": "Jake", "type": "Character", "offset_start": 42, "offset_end": 46,
              "tooltip": "Jake Thayne, Arcane Hunter lvl 87" }
        ],
        "previous_chapter_recap": "...",
        "foreshadowing": [...]
    }
}
```

### 9.2 Performance < 500ms

| Données | Stratégie | Latence |
|---------|-----------|---------|
| Texte + entités grounded | Batch Cypher unique | < 50ms |
| Character states temporels | Redis cache (invalidé à l'ingestion) | < 10ms |
| Timeline position, arc | Cypher pré-indexé | < 20ms |
| Recap + foreshadowing | **Pré-calculés à l'ingestion** (stockés sur `:Chapter`) | < 5ms |
| **Total** | | **< 100ms** |

> Les recaps et foreshadowing sont générés par LLM pendant l'ingestion, pas au moment de la lecture.

---

## 10. Structure du projet

```
WorldRAG/
├── CLAUDE.md                              # Instructions Claude Code (root)
├── PLAN_IMPLEMENTATION.md                 # Ce fichier
├── .env.example
├── .gitignore
├── pyproject.toml
├── .mcp.json                              # MCP servers (Neo4j, Context7)
│
├── .claude/
│   ├── settings.json                      # Hooks Claude Code
│   └── rules/                             # Règles scoped
│       ├── python-backend.md              # Règles Python (paths: backend/**)
│       ├── typescript-frontend.md         # Règles TypeScript (paths: frontend/**)
│       ├── neo4j-cypher.md                # Conventions Cypher (paths: **/*.cypher)
│       └── testing.md                     # Conventions tests (paths: **/tests/**)
│
├── backend/
│   ├── CLAUDE.md                          # Instructions backend-specific
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI, lifespan, CORS, routers
│   │   ├── config.py                      # Pydantic Settings
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py            # get_neo4j, get_redis, get_llm, get_langfuse
│   │   │   ├── middleware.py              # RequestContextMiddleware (structlog)
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── health.py
│   │   │       ├── books.py               # Upload, list, delete
│   │   │       ├── chapters.py            # Détail chapitre
│   │   │       ├── graph.py               # Explore, search, stats
│   │   │       ├── entities.py            # CRUD entités, merge, correct
│   │   │       ├── chat.py                # Agentic RAG (SSE streaming)
│   │   │       ├── reader.py              # Lecture augmentée
│   │   │       └── admin.py               # Monitoring, costs, DLQ
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── logging.py                 # Setup structlog + JSON
│   │   │   ├── resilience.py              # CircuitBreaker, retry_with_backoff
│   │   │   ├── rate_limiter.py            # aiolimiter per-provider
│   │   │   ├── cost_tracker.py            # Token counting + cost calculation
│   │   │   ├── dead_letter.py             # DLQ Redis
│   │   │   └── checkpoint.py              # Pipeline checkpoint helpers
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── providers.py               # Factory multi-provider + with_fallbacks()
│   │   │   ├── embeddings.py              # Voyage AI embedder
│   │   │   ├── reranker.py                # Cohere Rerank
│   │   │   └── streaming.py               # Streaming chat tokens
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── book.py
│   │   │   ├── entities.py                # Pydantic: Character, Skill, Location, Event...
│   │   │   ├── extraction.py              # LangExtract schemas + Instructor reconciliation
│   │   │   ├── graph.py
│   │   │   ├── chat.py
│   │   │   └── reader.py
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # Neo4jRepository base class
│   │   │   ├── book_repo.py
│   │   │   ├── entity_repo.py
│   │   │   ├── graph_repo.py
│   │   │   ├── timeline_repo.py
│   │   │   └── search_repo.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py               # Parse ePub/PDF/TXT
│   │   │   ├── chunking.py                # Structure-aware par chapitre
│   │   │   ├── extraction/
│   │   │   │   ├── __init__.py             # build_extraction_graph()
│   │   │   │   ├── regex_extractor.py      # PASSE 0: blue boxes, stats (regex, $0)
│   │   │   │   ├── characters.py           # Node LangExtract personnages
│   │   │   │   ├── systems.py              # Node LangExtract systèmes
│   │   │   │   ├── events.py               # Node LangExtract événements
│   │   │   │   ├── lore.py                 # Node LangExtract lore
│   │   │   │   ├── reconciler.py           # Node Instructor réconciliation
│   │   │   │   ├── validator.py            # Validation Cypher (SHACL-like)
│   │   │   │   └── router.py              # Progressive extraction routing
│   │   │   ├── graph_writer.py             # Cypher MERGE direct (remplace graph_builder)
│   │   │   ├── deduplication.py            # exact → fuzzy → LLM
│   │   │   ├── retrieval.py                # neo4j-graphrag + Voyage + Cohere + RRF
│   │   │   ├── reader_engine.py            # Moteur lecture augmentée (Graph 2)
│   │   │   └── monitoring.py              # LangFuse integration helpers
│   │   │
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── chat_agent.py               # Graph 3: StateGraph agentic RAG
│   │   │   ├── tools.py                    # search_kg, cypher, timeline, etc.
│   │   │   └── state.py                    # TypedDicts pour les 3 graphs
│   │   │
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── extraction_characters.py
│   │   │   ├── extraction_systems.py
│   │   │   ├── extraction_events.py
│   │   │   ├── extraction_lore.py
│   │   │   ├── classification.py
│   │   │   ├── reconciliation.py
│   │   │   ├── cypher.py
│   │   │   └── qa.py
│   │   │
│   │   └── workers/
│   │       ├── __init__.py
│   │       ├── settings.py
│   │       └── pipeline.py                 # arq tasks: process_book, process_chapter
│   │
│   └── tests/
│       ├── conftest.py                     # Fixtures: mock_llm, neo4j_test, redis_test
│       ├── fixtures/                       # Golden test data
│       │   ├── chapter_1_text.txt
│       │   ├── chapter_1_extraction.json
│       │   └── expected_entities.json
│       ├── test_ingestion.py
│       ├── test_chunking.py
│       ├── test_extraction.py              # Unit (mocked) + golden tests
│       ├── test_reconciler.py
│       ├── test_graph_writer.py
│       ├── test_retrieval.py
│       ├── test_reader_engine.py
│       └── test_chat_agent.py
│
├── frontend/
│   ├── CLAUDE.md                          # Instructions frontend-specific
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx                    # Dashboard
│       │   ├── library/page.tsx
│       │   ├── reader/[bookId]/[chapter]/page.tsx
│       │   ├── graph/page.tsx
│       │   ├── chat/page.tsx
│       │   ├── monitor/page.tsx            # Monitoring dashboard
│       │   └── entities/
│       │       ├── page.tsx
│       │       └── [id]/page.tsx
│       ├── components/
│       │   ├── ui/
│       │   ├── layout/
│       │   ├── reader/
│       │   ├── graph/
│       │   ├── chat/
│       │   ├── library/
│       │   ├── entities/
│       │   └── monitor/                    # Pipeline status, cost charts, DLQ viewer
│       └── lib/
│           ├── api.ts
│           ├── types.ts
│           ├── stores/
│           └── hooks/
│
├── ontology/
│   ├── core.yaml                          # Layer 1 (universel)
│   ├── litrpg.yaml                        # Layer 2 (genre)
│   └── primal_hunter.yaml                 # Layer 3 (série)
│
├── scripts/
│   ├── init_neo4j.cypher                  # Indexes + constraints + schema
│   ├── seed_sample.py                     # Sample data pour dev
│   └── migrations/                        # Schema evolution scripts
│       ├── 001_initial_schema.cypher
│       └── 002_add_narrative_functions.cypher
│
└── docker-compose.yml                     # Neo4j + Redis + PostgreSQL + LangFuse
```

---

## 11. Testing — Stratégie 3 niveaux

### Niveau 1 — Unit tests (mocked, rapides, CI)
```python
class TestChunking:
    def test_chapter_boundary_detection(self):
        text = "Chapter 1\n...\nChapter 2\n..."
        chunks = chunk_by_chapter(text)
        assert len(chunks) == 2
```

### Niveau 2 — Golden tests (fixtures, pas de LLM)
```python
class TestExtraction:
    @pytest.fixture
    def mock_llm_response(self):
        return json.load(open("fixtures/chapter_1_extraction.json"))

    def test_character_extraction_parsing(self, mock_llm_response):
        result = parse_extraction_response(mock_llm_response)
        assert any(c.name == "Jake Thayne" for c in result.characters)
```

### Niveau 3 — E2E avec LLM (nightly, coûteux)
```python
@pytest.mark.slow
@pytest.mark.llm
class TestExtractionE2E:
    async def test_full_chapter_extraction(self):
        result = await extract_chapter("fixtures/sample_chapter.txt")
        assert len(result.characters) >= 3
```

### Gold standard
Fichier de référence avec les 20+ entités clés des 5 premiers chapitres du corpus test. Sert de benchmark pour mesurer la qualité d'extraction (precision, recall, F1).

---

## 12. Phases d'implémentation — KG-first

> **Philosophie** : La construction du KG est la priorité absolue. Les use cases (lecture augmentée, chat, wiki) viennent après. On ne passe pas aux use cases tant que le KG n'est pas solide.

### Phase 1 — Infrastructure + Monitoring (fondations pro-grade)
**Durée** : 2 semaines
**Objectif** : Backend qui démarre, toutes connexions OK, monitoring en place, ontologie définie.

**Fichiers à créer :**
- `pyproject.toml`, `.env.example`, `.gitignore`, `CLAUDE.md`
- `.claude/settings.json`, `.claude/rules/*.md`, `.mcp.json`
- `docker-compose.yml` (Neo4j + Redis + PostgreSQL + LangFuse)
- `backend/app/main.py`, `config.py`
- `backend/app/core/logging.py`, `resilience.py`, `rate_limiter.py`, `cost_tracker.py`
- `backend/app/api/dependencies.py`, `middleware.py`, `routes/health.py`, `routes/admin.py`
- `backend/app/llm/providers.py`, `embeddings.py`, `reranker.py`
- `backend/app/repositories/base.py`
- `backend/app/services/monitoring.py`
- `scripts/init_neo4j.cypher` (indexes, constraints, schema complet Layer 1+2)
- `ontology/core.yaml`, `ontology/litrpg.yaml`, `ontology/primal_hunter.yaml`

**Critère** : `GET /api/health` → `{"neo4j": "ok", "redis": "ok", "postgres": "ok", "langfuse": "ok", "llm": "ok"}`. LangFuse dashboard accessible. Schema Neo4j initialisé avec tous les indexes et contraintes. Ontologie YAML validée contre GOLEM.

### Phase 2 — Pipeline d'extraction KG (LE COEUR — priorité maximale)
**Durée** : 4-5 semaines
**Objectif** : Pipeline d'extraction complet et robuste. C'est la phase la plus importante.

**Sous-phases :**

#### 2a — Ingestion & Chunking (1 semaine)
- `services/ingestion.py` — Parse ePub/PDF/TXT → chapitres
- `services/chunking.py` — Structure-aware par chapitre
- `services/extraction/regex_extractor.py` — **Passe 0 : blue boxes, stats, notifications**
- `schemas/book.py`, `repositories/book_repo.py`
- `api/routes/books.py` (upload)
- **Critère** : Upload ePub → chapitres parsés + chunks dans Neo4j + blue boxes extraites par regex

#### 2b — Extraction LLM 4 passes (2 semaines)
- `services/extraction/__init__.py` — `build_extraction_graph()` LangGraph
- `services/extraction/characters.py`, `systems.py`, `events.py`, `lore.py`
- `services/extraction/router.py` — Progressive extraction (keyword routing)
- `schemas/extraction.py` — Pydantic schemas stricts pour chaque passe
- `prompts/extraction_*.py` — Prompts optimisés avec few-shot examples
- `agents/state.py` (ExtractionPipelineState)
- **Critère** : 5 chapitres de Primal Hunter → 20+ entités correctes dans Neo4j. Traces LangFuse visibles.

#### 2c — Réconciliation & Entity Resolution (1 semaine)
- `services/extraction/reconciler.py` — Instructor reconciliation
- `services/deduplication.py` — exact → fuzzy → embedding → LLM-as-Judge
- `services/graph_writer.py` — Cypher MERGE direct avec batch_id + temporalité
- `core/dead_letter.py`, `core/checkpoint.py`
- **Critère** : Pas de doublons dans le KG. Entity resolution cross-chapitre fonctionne.

#### 2d — Validation & Qualité (1 semaine)
- `services/extraction/validator.py` — Cypher validation rules (SHACL-like)
- `scripts/validation_rules.cypher` — Règles de cohérence automatiques
- `tests/fixtures/` — Gold standard (5 chapitres annotés manuellement)
- `tests/test_extraction.py`, `test_reconciler.py`, `test_graph_writer.py`
- **Critère** : < 5% de contradictions. F1 ≥ 0.75 sur gold standard. Dry-run mode fonctionne.

#### 2e — Pipeline production (1 semaine)
- `workers/pipeline.py` — arq tasks : process_book (boucle chapitres)
- Checkpointing PostgreSQL, resume après crash
- Cost ceiling per chapter + per book
- Rate limiting par provider
- SSE progress → frontend
- **Critère** : Extraction d'un livre entier (50+ chapitres) end-to-end. Resume après kill. DLQ fonctionne.

### Phase 3 — Use cases en aval (après que le KG soit solide)
**Durée** : 6-8 semaines
**Objectif** : Exploiter le KG avec des applications.

#### 3a — API d'exploration KG + Graph Explorer (2 semaines)
- `api/routes/graph.py`, `entities.py`
- `repositories/graph_repo.py`, `entity_repo.py`, `timeline_repo.py`
- Frontend : ForceGraph, EntityTable, Dashboard, fiche entité
- **Critère** : Explorer visuellement le KG, chercher des entités, voir les relations.

#### 3b — Lecture augmentée (2-3 semaines)
- `services/reader_engine.py` (Graph 2: reader_context_graph)
- `api/routes/reader.py`, `chapters.py`
- Frontend : ChapterView, ContextPanel, EntityHighlight, TimelineBar
- **Critère** : Lire un chapitre avec entités highlightées + panneau contexte. < 200ms.

#### 3c — RAG & Chatbot agentic (2-3 semaines)
- `agents/chat_agent.py` (Graph 3), `tools.py`
- `services/retrieval.py` (neo4j-graphrag + Voyage + Cohere + RRF)
- `api/routes/chat.py`
- Frontend : ChatWindow, MessageBubble, SourceCard
- **Critère** : "Quand Jake a-t-il obtenu Arcane Hunter ?" → réponse correcte avec source.

### Phase 4 — Polish production
**Durée** : 2-3 semaines
- Dockerfiles (backend + frontend)
- `POST /api/entities/{id}/correct` — feedback loop
- Scripts de migration Neo4j
- Tests complets (coverage > 80%)
- CI/CD
- **Critère** : `docker compose up` → tout fonctionne. CI green.

---

## 13. Dépendances — `pyproject.toml`

```toml
[project]
name = "worldrag"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # API
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "python-multipart>=0.0.18",
    "sse-starlette>=2.0",
    # Graph DB
    "neo4j>=5.27",
    "neo4j-graphrag>=1.0",
    # Extraction
    "langextract>=0.1",
    "instructor>=1.14",
    # LLM Providers
    "openai>=1.60",
    "anthropic>=0.40",
    "google-genai>=1.0",
    # Agents / Orchestration
    "langgraph>=0.3",
    "langchain-core>=0.3",
    "langchain-openai>=0.3",
    "langchain-anthropic>=0.3",
    "langgraph-checkpoint-postgres>=2.0",
    # Embeddings & Reranking
    "voyageai>=0.3",
    "cohere>=5.0",
    # Task queue
    "arq>=0.26",
    "redis>=5.0",
    # Monitoring & Observability
    "langfuse>=2.27",
    "structlog>=24.0",
    "tiktoken>=0.8",
    # Resilience
    "tenacity>=9.0",
    "aiolimiter>=1.1",
    # Document parsing
    "ebooklib>=0.18",
    "pdfplumber>=0.11",
    "beautifulsoup4>=4.12",
    "httpx>=0.28",
    # Utils
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "thefuzz>=0.22",
    "asyncpg>=0.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.8",
    "pyright>=1.1",
]

[tool.ruff]
target-version = "py312"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "ANN", "ASYNC", "B", "SIM", "TCH"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
venvPath = "."
venv = ".venv"

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "llm: marks tests that require LLM API calls",
]
```

---

## 14. Configuration `.env.example`

```env
# === Neo4j ===
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=worldrag

# === Redis ===
REDIS_URL=redis://localhost:6379

# === PostgreSQL (LangGraph checkpoints + LangFuse) ===
POSTGRES_URI=postgresql://worldrag:worldrag@localhost:5432/worldrag

# === LLM Providers ===
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# === LangExtract (extraction) ===
LANGEXTRACT_MODEL=gemini-2.5-flash
LANGEXTRACT_PASSES=2
LANGEXTRACT_MAX_WORKERS=20
LANGEXTRACT_BATCH_CHAPTERS=10

# === Instructor (réconciliation, classification) ===
LLM_RECONCILIATION=openai:gpt-4o-mini
LLM_CLASSIFICATION=openai:gpt-4o-mini
LLM_DEDUP=openai:gpt-4o-mini
LLM_CYPHER=openai:gpt-4o-mini
USE_BATCH_API=true

# === User-facing ===
LLM_CHAT=openai:gpt-4o

# === Embeddings & Reranking ===
VOYAGE_API_KEY=...
VOYAGE_MODEL=voyage-3.5
COHERE_API_KEY=...

# === LangFuse (self-hosted) ===
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# === LangSmith (optionnel, pour traces LangGraph) ===
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=worldrag

# === App ===
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
LOG_FORMAT=json
COST_CEILING_PER_CHAPTER=0.50
COST_CEILING_PER_BOOK=50.00
```

---

## 15. Setup Claude Code — Optimisé pour le développement

### 15.1 CLAUDE.md (racine)

Contenu du CLAUDE.md racine couvre : architecture globale, conventions de commit, commandes utiles (`uv run`, `docker compose`), structure du projet, et liens vers les plans.

### 15.2 `.claude/rules/` — Règles scoped

- `python-backend.md` (paths: `backend/**`) : Python 3.12+, async/await, Pydantic v2, ruff formatting, pyright strict, imports absolus
- `typescript-frontend.md` (paths: `frontend/**`) : TypeScript strict, Next.js App Router, tailwind, shadcn/ui conventions
- `neo4j-cypher.md` (paths: `**/*.cypher`) : Conventions Cypher, indexes requis, temporal pattern
- `testing.md` (paths: `**/tests/**`) : pytest-asyncio, fixtures, golden tests pattern, markers slow/llm

### 15.3 `.claude/settings.json` — Hooks

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd $CLAUDE_PROJECT_DIR && uv run ruff check --fix {{filepath}} 2>/dev/null; uv run ruff format {{filepath}} 2>/dev/null; true"
          }
        ]
      }
    ]
  }
}
```

### 15.4 `.mcp.json` — MCP Servers

```json
{
  "mcpServers": {
    "neo4j": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-neo4j-cypher"],
      "env": {
        "NEO4J_URI": "${NEO4J_URI:-bolt://localhost:7687}",
        "NEO4J_USER": "${NEO4J_USER:-neo4j}",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD:-worldrag}"
      }
    }
  }
}
```

---

## 16. docker-compose.yml

```yaml
services:
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/worldrag
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_max__size: "2G"
      NEO4J_dbms_memory_pagecache_size: "1G"
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: worldrag
      POSTGRES_PASSWORD: worldrag
      POSTGRES_DB: worldrag
    volumes:
      - postgres_data:/var/lib/postgresql/data

  langfuse:
    image: langfuse/langfuse:2
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_URL: http://localhost:3001
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET:-worldrag-secret}
      SALT: ${LANGFUSE_SALT:-worldrag-salt}
      TELEMETRY_ENABLED: "false"
    depends_on:
      - langfuse-db

  langfuse-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data

volumes:
  neo4j_data:
  redis_data:
  postgres_data:
  langfuse_pgdata:
```

---

## 17. Sources de la veille

### Technologies — Stack retenu
- [Google LangExtract](https://github.com/google/langextract) — 33.6k★, extraction avec grounding
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/) — StateGraph, checkpointing, RetryPolicy
- [neo4j-graphrag](https://neo4j.com/docs/neo4j-graphrag-python/current/) — Retrievers production-ready
- [Voyage AI voyage-3.5](https://blog.voyageai.com/2025/05/20/voyage-3-5/) — +8% vs OpenAI
- [LangFuse](https://langfuse.com/) — LLM observability open-source
- [Instructor](https://python.useinstructor.com/) — Structured extraction Pydantic

### Technologies — Évaluées et écartées (avec justification)
- [LLMGraphTransformer](https://python.langchain.com/api_reference/experimental/graph_transformers/) — Pas de source grounding, pas de multi-pass
- [KGGen (Stanford)](https://github.com/stair-lab/kg-gen) — 1k★, triples non typés, algo clustering intéressant
- [BookNLP (Bamman)](https://github.com/booknlp/booknlp) — 889★, coréférence sub-70%, deps lourdes
- [AutoSchemaKG (HKUST)](https://github.com/HKUST-KnowComp/AutoSchemaKG) — 698★, à monitorer pour auto-discovery Layer 3
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — 29.6k★, trop cher pour construction, intéressant pour query
- [LightRAG](https://github.com/HKUST-KnowComp/LightRAG) — Pas de Neo4j natif, pas de grounding

### État de l'art KG 2025-2026 — Références clés
- **Convergence LLM+KG** : Le LLMGraphTransformer et SimpleKGPipeline rendent la construction accessible, mais pour la fiction avec grounding+temporalité, LangExtract + ontologie custom reste supérieur
- **Two-pass LitRPG** : Regex pour blue boxes + LLM pour narratif (pattern recommandé)
- **Entity resolution** : GPT-4 surpasse les PLM fine-tunés de 40-68% sur les types non vus (Ghanem & Cruz 2025)
- **Validation SHACL-like** : Détection automatique de contradictions via Cypher post-ingestion
- **Ontologie dimensionnement** : 3-7 types de nœuds de départ → notre Layer 1 Core est dans la bonne range
- **Fine-tuning vs prompting** : Point de rentabilité ~1500 docs. En dessous, few-shot suffit → notre approche est correcte
- **Docling (IBM)** : Alternative pour le parsing PDF — à évaluer si pdfplumber montre ses limites
- **Norme GQL (ISO 39075:2024)** : Premier nouveau langage DB ISO depuis SQL. Neo4j adopte déjà les GQLSTATUS
- **Retcons & narrateurs non fiables** : Pattern RETCONNED_BY + PERCEIVED_BY avec statut épistémique

### Ontologies littéraires
- **GOLEM** (MDPI 2025) — Ontologie formelle pour la fiction, extensible, alignée CIDOC-CRM + DOLCE. [ontology.golemlab.eu](https://ontology.golemlab.eu/)
- CIDOC-CRM (ISO 21127) — Événements et temporalité
- FRBRoo/LRMoo — Modèle bibliographique
- OntoMedia (U. Southampton) — Ontologie narrative (fabula/sjuzhet)
- SEM (VU Amsterdam) — Simple Event Model
- DOLCE — Taxonomie temporelle (State / Event / Process / Achievement)
- Wikidata — Propriétés caractères fictifs + modèle qualifieur temporal
- Propp — Fonctions narratives (31 fonctions, OWL Peinado & Gervas)
- Bamman et al. (CMU) — Modèle computationnel des personnages fictifs

### Audits internes
- Audit architecture technique — Incompatibilité LangExtract↔Graphiti, dual schema Neo4j
- Audit risques et faisabilité — Over-engineering, coûts LLM, timeline réaliste
- Audit chef de projet — Re-séquençage phases, KG-first
