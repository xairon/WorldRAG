# WorldRAG KG v2 — Assemblage SOTA + Induction Narrative

**Design Spec**
*2026-03-14 — Nicolas, LIFAT / Université de Tours*

---

## 1. Vision

Réécrire intégralement le pipeline de construction de Knowledge Graph en assemblant les meilleurs outils SOTA (KGGen, Graphiti, Leiden) autour d'une contribution originale : le **SagaProfileInducer**, un module d'induction automatique d'ontologie par saga.

Le pipeline actuel (LangGraph 4-pass, 11 types hardcodés, ontologie 3 couches YAML, VoyageAI embeddings, reconciler 3-tier) est remplacé par un assemblage SOTA plus performant, plus générique et moins coûteux à maintenir.

### Principes directeurs

1. **Assembler le SOTA, pas le réinventer** — KGGen pour l'extraction, Graphiti pour le stockage temporel et le retrieval, Leiden pour les community clusters.
2. **Un seul module original** — le SagaProfileInducer, qui fait le pont entre outils généralistes et fiction multi-saga.
3. **Schéma dynamique** — l'ontologie n'est plus hardcodée, elle est induite automatiquement par saga.
4. **Graphiti augmenté** — un seul schéma Neo4j (Graphiti), enrichi avec des labels saga-specific. Pas de double schéma.

---

## 2. Architecture globale

```
EPUB (tome 1)
  │
  ├─ Ingestion (ebooklib + LangChain chunking)
  │   └─ Chapitres → Chunks (~500 tokens, metadata chapitre/position)
  │
  ├─ [Discovery Mode] ◀── premier tome d'une saga
  │   ├─ KGGen extraction libre (types universels)
  │   ├─ KGGen clustering itératif (entity resolution)
  │   ├─ Graphiti ingestion (épisodes + entités + edges temporels)
  │   └─ SagaProfileInducer ◀── CONTRIBUTION ORIGINALE
  │       ├─ Analyse du graphe Graphiti brut
  │       ├─ Clustering sémantique des CONCEPT nodes
  │       ├─ LLM : propose types spécifiques + patterns + cardinalités
  │       └─ Persiste SagaProfile (JSON + Neo4j)
  │
  ├─ [Guided Mode] ◀── tomes suivants
  │   ├─ KGGen extraction guidée (SagaProfile injecté dans les prompts)
  │   ├─ KGGen clustering itératif (avec contexte cross-tome)
  │   ├─ Graphiti ingestion (entity summaries mis à jour incrémentalement)
  │   └─ SagaProfileInducer update (nouveaux systèmes découverts ?)
  │
  └─ Post-processing
      ├─ Label augmentation (SagaProfile → labels Neo4j sur nœuds Graphiti)
      ├─ Leiden community clustering (Neo4j GDS)
      └─ Community summaries (LLM)

QUERY (chat)
  │
  ├─ Intent router (3 routes)
  ├─ Retrieval dual :
  │   ├─ Graphiti API : semantic + BM25 + BFS (questions ouvertes)
  │   └─ Cypher typé : requêtes structurées sur labels induits (questions précises)
  ├─ Context assembly (entity summaries + chunks + community summaries)
  ├─ Generation (Gemini 2.5 Flash, CoT)
  └─ Faithfulness check (NLI)
```

---

## 3. SagaProfileInducer — Contribution originale

### 3.1 Modèle de données

```python
class SagaProfile(BaseModel):
    """Ontologie induite automatiquement pour une saga."""
    saga_id: str                          # "primal-hunter", "harry-potter"
    saga_name: str                        # "The Primal Hunter"
    source_book: str                      # Tome utilisé pour l'induction
    version: int = 1                      # Incrémenté si évolution au tome N

    entity_types: list[InducedEntityType]
    relation_types: list[InducedRelationType]
    text_patterns: list[InducedPattern]

    narrative_systems: list[str]          # ["magic_system", "progression", "political"]
    estimated_complexity: str             # "low" | "medium" | "high"


class InducedEntityType(BaseModel):
    """Un type d'entité découvert dans l'univers."""
    type_name: str                        # "SPELL", "HOUSE", "BLOODLINE"
    parent_universal: str                 # "CONCEPT", "ORGANIZATION", "CHARACTER"
    description: str                      # "Maisons de Poudlard, affectées au Sorting Hat"
    instances_found: list[str]            # ["Gryffindor", "Slytherin", ...]
    typical_attributes: list[str]         # ["founder", "element", "animal"]
    confidence: float                     # 0.0–1.0


class InducedRelationType(BaseModel):
    """Un type de relation avec contraintes."""
    relation_name: str                    # "BELONGS_TO_HOUSE"
    source_type: str                      # "CHARACTER"
    target_type: str                      # "HOUSE"
    cardinality: str                      # "1:1", "1:N", "N:N"
    temporal: bool                        # True si la relation peut changer
    description: str


class InducedPattern(BaseModel):
    """Pattern textuel récurrent découvert."""
    pattern_regex: str                    # r"\[Skill Acquired: (.+?)\]"
    extraction_type: str                  # "SKILL_ACQUISITION"
    example: str                          # "[Skill Acquired: Shadow Step]"
    confidence: float
```

### 3.2 Algorithme d'induction (Discovery Mode)

**Étape 1 — Extraction des candidats**
- Récupérer tous les nœuds de type CONCEPT depuis Graphiti
- Récupérer les edges (prédicats) les plus fréquents
- Récupérer les attributs récurrents (via entity summaries Graphiti)

**Étape 2 — Clustering sémantique**
- Embedder les noms + descriptions des CONCEPT nodes (BGE-m3)
- Clustering hiérarchique (agglomerative, seuil cosine > 0.75)
- Chaque cluster = un candidat de type induit
- Ex: cluster ["Expelliarmus", "Patronus", "Avada Kedavra", "Lumos"] → type candidat SPELL

**Étape 3 — Formalisation LLM**
- Pour chaque cluster significatif (≥3 instances), appel LLM :
  "Voici N entités extraites d'un roman : [liste].
   Elles semblent former un système narratif.
   Propose : type_name, description, attributs typiques,
   relations probables avec les types universels,
   cardinalité, temporalité."
- Le LLM retourne un InducedEntityType + InducedRelationType[]

**Étape 4 — Détection de patterns textuels**
- Scanner le texte brut du tome pour des motifs récurrents :
  - Crochets structurés : `[X: Y]`, `[X!]`, `[X → Y]`
  - Blocs formatés (tableaux de stats, blue boxes)
- LLM classifie chaque pattern → InducedPattern

**Étape 5 — Assemblage et validation**
- Fusionner les types, relations, patterns → SagaProfile
- Filtrer les types à faible confidence (< 0.6)
- Persister en JSON + nœud `:SagaProfile` dans Neo4j

### 3.3 Guided Mode (tomes suivants)

1. Injecter les types induits dans le prompt KGGen (entity_types enrichis)
2. Pre-scan regex avec les patterns du SagaProfile (pré-annotation avant KGGen)
3. Après ingestion Graphiti : re-run SagaProfileInducer en mode "delta"
   - Détecte les nouveaux clusters non couverts par le profil existant
   - Propose des évolutions : "Nouveau type découvert : HORCRUX (3 instances)"
   - Incrémente version si le profil évolue

### 3.4 Exemples concrets d'induction

**Harry Potter — tome 1 :**
- Cluster CONCEPT : ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"] → `HOUSE`
- Cluster CONCEPT : ["Expelliarmus", "Wingardium Leviosa", "Alohomora"] → `SPELL`
- Cluster CONCEPT : ["Hippogriffe", "Basilic", "Norbert"] → `MAGICAL_CREATURE`
- Relation induite : `CHARACTER -[BELONGS_TO_HOUSE]-> HOUSE` (1:1, non-temporel)
- Relation induite : `CHARACTER -[CASTS]-> SPELL` (N:N, temporel)
- Pas de patterns structurés (prose pure)

**Primal Hunter — tome 1 :**
- Cluster CONCEPT : ["Shadow Step", "Arcane Powershot", "Stealth"] → `SKILL`
- Cluster CONCEPT : ["Bloodline of the Primal Hunter"] → `BLOODLINE`
- Cluster CONCEPT : ["Alchemist", "Archer of the Apex Hunter"] → `CLASS`
- Patterns détectés : `[Skill Acquired: X]`, `[Level X → Y]`, `[Quest Complete: X]`
- Relation induite : `CHARACTER -[HAS_SKILL]-> SKILL` (N:N, temporel)
- Relation induite : `CHARACTER -[HAS_CLASS]-> CLASS` (1:N, temporel)

**L'Assassin Royal — tome 1 :**
- Cluster CONCEPT : ["Art", "Vif"] → `MAGIC_SYSTEM` (seulement 2 instances — confiance moyenne)
- Cluster CONCEPT : ["Six-Duchés", "Îles Pirates", "Montagnes"] → rattaché à LOCATION, pas de type induit
- Peu de patterns structurés → `text_patterns: []`
- Profil plus simple, l'inducteur s'adapte à la complexité de l'univers

---

## 4. Intégration KGGen

### 4.1 Rôle

KGGen remplace l'intégralité du pipeline d'extraction custom : LangExtract 4 passes, Instructor, reconciler 3-tier, EntityRegistry, ontologie YAML.

### 4.2 Interface avec le pipeline

```python
from kg_gen import KGGen

class BookExtractor:
    """Orchestre KGGen pour l'extraction d'un livre complet."""

    def __init__(self, saga_profile: SagaProfile | None = None):
        self.kg = KGGen(model="gemini/gemini-2.5-flash")
        self.profile = saga_profile

    def extract_chapter(self, chapter_text: str, chapter_num: int) -> list[Triple]:
        entity_types = ["CHARACTER", "LOCATION", "OBJECT", "ORGANIZATION", "EVENT", "CONCEPT"]
        if self.profile:
            entity_types += [t.type_name for t in self.profile.entity_types]

        triples = self.kg.extract(text=chapter_text, entity_types=entity_types)
        for triple in triples:
            triple.metadata["chapter"] = chapter_num
        return triples

    def extract_book(self, chapters: list[Chapter]) -> KGGenGraph:
        all_triples = []
        for ch in chapters:
            triples = self.extract_chapter(ch.text, ch.number)
            all_triples.extend(triples)

        # Clustering itératif global (cross-chapters)
        graph = self.kg.cluster(all_triples)
        return graph
```

### 4.3 Ce que KGGen gère nativement

| Besoin | Avant (custom) | Après (KGGen) |
|---|---|---|
| Entity extraction | LangExtract 4 passes | `kg.extract()` — 2 passes |
| Entity resolution | 3-tier (exact → fuzzy → LLM) | `kg.cluster()` — clustering itératif |
| Alias mapping | EntityRegistry custom | Natif dans le clustering |
| Structured output | Instructor + Pydantic | DSPy (intégré à KGGen) |
| Cross-chapter dedup | reconciler.py | Clustering global post-extraction |

### 4.4 Ce que KGGen ne gère PAS

| Besoin | Solution |
|---|---|
| Types induits | SagaProfileInducer → `entity_types` injectés dans les prompts |
| Patterns textuels | Pre-scan regex (patterns du SagaProfile) → pré-annotation |
| Metadata temporelle | Post-enrichissement des triples avec chapter_num |
| Stockage Neo4j | Graphiti |

---

## 5. Intégration Graphiti + Neo4j

### 5.1 Rôle

Graphiti remplace : le modèle de graphe custom, le stockage Neo4j custom (`entity_repo.py`, `book_repo.py`), les embeddings VoyageAI, le retrieval hybride custom.

### 5.2 Client Graphiti partagé

```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

class GraphitiClient:
    """Client Graphiti singleton, initialisé dans le lifespan FastAPI."""

    def __init__(self, neo4j_uri: str, neo4j_auth: tuple[str, str]):
        self.client = Graphiti(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_auth[0],
            neo4j_password=neo4j_auth[1],
        )

    async def ingest_chapter(
        self,
        chapter_text: str,
        book_id: str,
        chapter_num: int,
        saga_id: str,
    ) -> None:
        await self.client.add_episode(
            name=f"{book_id}:ch{chapter_num}",
            episode_body=chapter_text,
            source=EpisodeType.text,
            reference_time=NarrativeTemporalMapper.to_datetime(1, chapter_num),
            source_description=f"Chapter {chapter_num} of {book_id}",
            group_id=saga_id,
        )

    async def search(self, query: str, saga_id: str, max_chapter: int | None = None):
        results = await self.client.search(
            query=query,
            group_ids=[saga_id],
            num_results=20,
        )
        if max_chapter is not None:
            max_dt = NarrativeTemporalMapper.to_datetime(1, max_chapter)
            results = [r for r in results if r.valid_at <= max_dt]
        return results
```

### 5.3 Modèle temporel narratif

Graphiti exige des `datetime` pour son modèle bi-temporel. Pour la fiction :

```python
class NarrativeTemporalMapper:
    """Mappe (book, chapter, scene_order) → datetime pour Graphiti."""

    EPOCH = datetime(2000, 1, 1)
    BOOK_OFFSET_DAYS = 10_000  # chaque livre décalé de ~27 ans

    @staticmethod
    def to_datetime(book_num: int, chapter_num: int, scene_order: int = 0) -> datetime:
        days = (book_num - 1) * NarrativeTemporalMapper.BOOK_OFFSET_DAYS + chapter_num
        seconds = scene_order
        return NarrativeTemporalMapper.EPOCH + timedelta(days=days, seconds=seconds)

    @staticmethod
    def from_datetime(dt: datetime) -> tuple[int, int, int]:
        delta = dt - NarrativeTemporalMapper.EPOCH
        book = delta.days // NarrativeTemporalMapper.BOOK_OFFSET_DAYS + 1
        chapter = delta.days % NarrativeTemporalMapper.BOOK_OFFSET_DAYS
        scene = delta.seconds
        return book, chapter, scene
```

### 5.4 Label augmentation

Post-processing qui ajoute les labels Neo4j induits sur les nœuds Graphiti existants.

```python
class LabelAugmenter:
    """Ajoute les labels saga-specific sur les nœuds Entity Graphiti."""

    def __init__(self, driver: AsyncDriver, profile: SagaProfile):
        self.driver = driver
        self.profile = profile

    async def augment(self) -> int:
        augmented = 0
        async with self.driver.session() as session:
            for entity_type in self.profile.entity_types:
                # Instances connues → label direct via APOC
                for instance_name in entity_type.instances_found:
                    await session.run(
                        """
                        MATCH (n:Entity {name: $name, group_id: $saga_id})
                        CALL apoc.create.addLabels(n, [$label]) YIELD node
                        RETURN node
                        """,
                        name=instance_name,
                        saga_id=self.profile.saga_id,
                        label=entity_type.type_name,
                    )
                    augmented += 1

            # Entités non classifiées → classification LLM batch
            result = await session.run(
                """
                MATCH (n:Entity {group_id: $saga_id})
                WHERE size([label IN labels(n) WHERE label <> 'Entity']) = 0
                RETURN n.name AS name, n.summary AS summary
                LIMIT 200
                """,
                saga_id=self.profile.saga_id,
            )
            unclassified = [dict(r) async for r in result]
            # → LLM batch classification → APOC addLabels

        return augmented
```

---

## 6. Pipeline chat redesigné

### 6.1 Simplification

Le pipeline actuel a 17 nœuds LangGraph. Avec Graphiti comme backend, la majorité deviennent inutiles.

| Nœud actuel | Statut |
|---|---|
| router (intent 6 routes) | **Gardé** — simplifié à 3 routes |
| query_transform | **Supprimé** — Graphiti gère la recherche sémantique |
| hyde | **Supprimé** — retrieval Graphiti déjà hybride |
| retrieve | **Remplacé** par `graphiti.search()` |
| rerank (zerank) | **Supprimé** — Graphiti fusionne et ranke ses 3 modes |
| dedup | **Supprimé** — Graphiti déduplique nativement |
| temporal_sort | **Supprimé** — Graphiti trie temporellement |
| kg_query | **Remplacé** par Cypher sur labels augmentés |
| context_assembly | **Gardé** — enrichi avec entity summaries Graphiti |
| generate (CoT) | **Gardé** |
| faithfulness (NLI) | **Gardé** |
| memory | **Gardé** — checkpointing PostgreSQL |

### 6.2 Nouveau graph LangGraph (7 nœuds)

```
                    ┌─────────────┐
                    │   router    │
                    │ (3 routes)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ graphiti  │ │  cypher  │ │  direct  │
        │ _search   │ │ _lookup  │ │(no retr.)│
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             └────────────┼────────────┘
                          ▼
                   ┌──────────────┐
                   │   context    │
                   │  _assembly   │
                   └──────┬───────┘
                          ▼
                   ┌──────────────┐
                   │   generate   │
                   │   (CoT)      │
                   └──────┬───────┘
                          ▼
                   ┌──────────────┐
                   │ faithfulness │
                   │   (NLI)      │
                   └──────────────┘
```

**3 routes :**
- `graphiti_search` — questions ouvertes, thématiques, narratives → API Graphiti (semantic + BM25 + BFS)
- `cypher_lookup` — questions structurées précises ("skills de Jake au chapitre 30") → Cypher sur labels augmentés
- `direct` — conversationnel, pas de retrieval

**Context assembly enrichi :**
- Entity summaries Graphiti (résumés évolutifs par entité)
- Community summaries Leiden (thèmes de haut niveau)
- Episodic chunks (passages source pour les citations)
- Edges temporels filtrés (spoiler guard via max_chapter)

---

## 7. Coûts et performances attendues

### 7.1 Coût par livre (Gemini 2.5 Flash)

| Étape | Coût estimé |
|---|---|
| KGGen extraction (2 passes) | ~$0.20 |
| KGGen clustering itératif | ~$0.06 |
| Graphiti ingestion (entity extraction + summaries) | ~$0.08 |
| SagaProfileInducer (tome 1 uniquement) | ~$0.03 |
| Label augmentation (LLM batch) | ~$0.02 |
| Community summaries (Leiden) | ~$0.03 |
| **Total (tome 1)** | **~$0.42** |
| **Total (tomes suivants)** | **~$0.39** |

### 7.2 Performances retrieval attendues

| Métrique | Pipeline actuel | Nouveau pipeline |
|---|---|---|
| Latence retrieval | ~200ms (vector + rerank) | ~300ms (Graphiti 3-modes) |
| Multi-hop | Non (vector search shallow) | Oui (BFS Graphiti) |
| Questions temporelles | Basique (WHERE clause) | Natif (bi-temporel) |
| Questions thématiques | Non | Oui (community summaries) |
| Entity summaries | Non | Oui (Graphiti natif) |

---

## 8. Infrastructure préservée

| Composant | Statut | Notes |
|---|---|---|
| FastAPI + lifespan | **Préservé** | Ajoute GraphitiClient dans app.state |
| arq workers | **Préservé** | Tâches refactorisées pour KGGen + Graphiti |
| Redis | **Préservé** | Cache + task queue inchangé |
| PostgreSQL | **Préservé** | Checkpointing + feedback + migrations |
| LangFuse + LangSmith | **Préservé** | Callbacks inchangés |
| Docker Compose | **Préservé** | Ajoute Neo4j GDS plugin pour Leiden |
| Frontend Next.js | **Adapté** | Graph explorer lit les labels dynamiques |
| Auth middleware | **Préservé** | Inchangé |
| Admin API | **Préservé** | Adapté aux nouvelles tâches |

---

## 9. Code supprimé

| Chemin | Raison |
|---|---|
| `backend/app/services/extraction/` | Remplacé par KGGen |
| `backend/app/agents/extraction/` | LangGraph d'extraction supprimé |
| `backend/app/schemas/extraction.py` | 11 types hardcodés → types induits |
| `ontology/*.yaml` | 3 couches hardcodées → SagaProfile induit |
| `backend/app/llm/embeddings.py` | VoyageAI → BGE-m3 via Graphiti |
| `backend/app/agents/chat/` | Refait avec retrieval Graphiti (7 nœuds) |
| `scripts/init_neo4j.cypher` | Contraintes hardcodées → Graphiti + labels dynamiques |

---

## 10. Code nouveau

| Chemin | Rôle |
|---|---|
| `backend/app/services/saga_profile/inducer.py` | SagaProfileInducer |
| `backend/app/services/saga_profile/models.py` | SagaProfile, InducedEntityType, etc. |
| `backend/app/services/saga_profile/augmenter.py` | LabelAugmenter (post-processing Neo4j) |
| `backend/app/services/saga_profile/temporal.py` | NarrativeTemporalMapper |
| `backend/app/services/ingestion/extractor.py` | BookExtractor (wrapper KGGen) |
| `backend/app/services/ingestion/graphiti_ingest.py` | Ingestion Graphiti par chapitre |
| `backend/app/core/graphiti_client.py` | Client Graphiti singleton |
| `backend/app/agents/chat/graph.py` | Nouveau pipeline 7 nœuds |
| `backend/app/agents/chat/nodes/` | graphiti_search, cypher_lookup, context_assembly, generate, faithfulness |

---

## 11. Dépendances ajoutées

| Package | Version | Rôle |
|---|---|---|
| `kg-gen` | latest | Extraction KGGen |
| `graphiti-core` | latest | Stockage temporel + retrieval |
| `neo4j-graph-data-science` | (plugin Neo4j) | Leiden clustering |

## 12. Dépendances supprimées

| Package | Raison |
|---|---|
| `langextract` | Remplacé par KGGen |
| `instructor` | Remplacé par KGGen (DSPy) |
| `voyageai` | Remplacé par BGE-m3 (Graphiti) |
| `thefuzz` | Remplacé par KGGen clustering |

---

## 13. Métriques de validation

**Test sur 3 sagas :**
1. **Primal Hunter** (LitRPG, blue boxes, progression system) — le SagaProfile doit capturer SKILL, CLASS, BLOODLINE, patterns `[Skill Acquired: X]`
2. **Harry Potter** (fantasy classique, prose pure) — doit capturer SPELL, HOUSE, MAGICAL_CREATURE sans patterns structurés
3. **L'Assassin Royal** (fantasy low-magic, peu de systèmes) — doit produire un profil simple (MAGIC_SYSTEM avec 2 instances seulement)

**Benchmarks :**
- MINE-narratif adapté : 50 faits annotés manuellement par livre, score de retrouvabilité dans le KG
- Comparaison coût/qualité vs pipeline v1 sur Primal Hunter
- Latence retrieval P95 < 500ms sur Graphiti
