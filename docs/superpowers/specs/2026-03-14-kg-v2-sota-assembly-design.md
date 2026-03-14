# WorldRAG KG v2 — Assemblage SOTA + Induction Narrative

**Design Spec — v2 (post-review)**
*2026-03-14 — Nicolas, LIFAT / Université de Tours*

---

## 1. Vision

Réécrire intégralement le pipeline de construction de Knowledge Graph en utilisant **Graphiti comme moteur central** (extraction + stockage temporel + retrieval) et un module original : le **SagaProfileInducer**, pour l'induction automatique d'ontologie par saga.

Le pipeline actuel (LangGraph 4-pass, 11 types hardcodés, ontologie 3 couches YAML, LocalEmbedder/BGE-M3, reconciler 3-tier) est remplacé par une architecture centrée sur Graphiti, plus performante, plus générique et moins coûteuse à maintenir.

### Principes directeurs

1. **Graphiti comme moteur unique** — extraction, stockage temporel, entity resolution et retrieval. Un seul moteur, pas de double extraction.
2. **Un seul module original** — le SagaProfileInducer, qui génère des modèles Pydantic injectés dans `add_episode(entity_types=...)`.
3. **Schéma dynamique** — l'ontologie n'est plus hardcodée, elle est induite automatiquement par saga et traduite en types Pydantic pour Graphiti.
4. **KGGen optionnel** — utilisé uniquement comme pass de clustering post-hoc pour détecter les aliases que Graphiti aurait manqués.

### Changement clé vs v1 du spec

La v1 proposait KGGen comme extracteur primaire + Graphiti pour le stockage. L'analyse des APIs réelles a révélé :

- **KGGen** : `generate(input_data, cluster=True)` — pas de paramètre `entity_types`, impossible d'injecter les types induits du SagaProfile.
- **Graphiti** : `add_episode(entity_types={"Skill": SkillModel})` — supporte nativement les types custom Pydantic, fait extraction + stockage en un seul appel.
- **Graphiti** : `add_triplet()` pour les entités pré-extraites, `add_episode_bulk()` pour l'ingestion batch.

Conséquence : **Graphiti devient le moteur central, KGGen est relégué à un rôle optionnel de clustering.**

---

## 2. Architecture globale

```
EPUB (tome 1)
  │
  ├─ Ingestion (ebooklib + LangChain chunking)
  │   └─ Chapitres → Chunks (~500 tokens, metadata chapitre/position)
  │
  ├─ [Discovery Mode] ◀── premier tome d'une saga
  │   ├─ Graphiti add_episode_bulk (types universels uniquement)
  │   │   └─ entity_types = {CHARACTER, LOCATION, OBJECT, ORGANIZATION, EVENT, CONCEPT}
  │   │   └─ Graphiti extrait, déduplique, crée entity summaries, edges temporels
  │   ├─ SagaProfileInducer ◀── CONTRIBUTION ORIGINALE
  │   │   ├─ Analyse les Entity nodes dans Neo4j (Graphiti les a typés)
  │   │   ├─ Clustering sémantique des nœuds peu spécifiques
  │   │   ├─ LLM : propose types spécifiques + patterns + cardinalités
  │   │   └─ Génère des modèles Pydantic dynamiques → SagaProfile
  │   └─ (Optionnel) Re-ingestion avec types enrichis
  │       └─ Graphiti add_episode_bulk avec entity_types = universels + induits
  │
  ├─ [Guided Mode] ◀── tomes suivants
  │   ├─ Graphiti add_episode_bulk (types universels + induits du SagaProfile)
  │   │   └─ entity_types = {CHARACTER, LOCATION, ..., SKILL, CLASS, BLOODLINE, ...}
  │   │   └─ edge_types + edge_type_map issus du SagaProfile
  │   ├─ SagaProfileInducer delta (nouveaux systèmes découverts ?)
  │   └─ (Optionnel) KGGen clustering post-hoc pour alias detection
  │
  └─ Post-processing
      ├─ Leiden community clustering (Neo4j GDS)
      └─ Community summaries (LLM)

QUERY (chat)
  │
  ├─ Intent router (3 routes)
  ├─ Retrieval :
  │   ├─ Graphiti search (semantic + BM25 + BFS) — toutes questions
  │   ├─ Cypher typé — questions structurées précises (filtrage par type + temporalité)
  │   └─ (les deux modes utilisent les mêmes nœuds dans le même Neo4j)
  ├─ Context assembly (entity summaries + episodic chunks + community summaries)
  ├─ Generation (Gemini 2.5 Flash, CoT)
  ├─ Faithfulness check (NLI)
  └─ Retry loop (max 2 : faithfulness fail → reformulate → re-retrieve → re-generate)
```

### Ce qui reste de l'infra actuelle

- FastAPI + lifespan (ajoute GraphitiClient dans app.state)
- arq workers (tâches refactorisées pour Graphiti)
- Redis (cache, task queue)
- PostgreSQL (LangGraph checkpointing, chat feedback, migrations)
- Frontend Next.js (adapté pour le nouveau schéma dynamique)
- LangFuse + LangSmith (observabilité)
- Docker Compose prod (ajoute Neo4j GDS plugin)

### Ce qui est supprimé

- `backend/app/services/extraction/` (tout — remplacé par Graphiti `add_episode`)
- `backend/app/agents/extraction/` (le LangGraph d'extraction custom)
- `backend/app/schemas/extraction.py` (11 types hardcodés → types induits Pydantic)
- `ontology/*.yaml` (3 couches hardcodées → SagaProfile induit)
- `backend/app/llm/embeddings.py` (LocalEmbedder → Graphiti gère ses propres embeddings)
- `backend/app/agents/chat/` (refait avec retrieval Graphiti, 8 nœuds)
- `scripts/init_neo4j.cypher` (contraintes hardcodées → Graphiti `build_indices_and_constraints()`)

### Ce qui est nouveau

- `backend/app/services/saga_profile/` — SagaProfileInducer + models + pydantic_generator
- `backend/app/services/ingestion/` — Orchestrateur Graphiti (Discovery/Guided modes)
- `backend/app/core/graphiti_client.py` — Client Graphiti singleton
- `backend/app/agents/chat/` — Nouveau pipeline 8 nœuds

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
    type_name: str                        # "Spell", "House", "Bloodline"
    parent_universal: str                 # "Concept", "Organization", "Character"
    description: str                      # "Maisons de Poudlard, affectées au Sorting Hat"
    instances_found: list[str]            # ["Gryffindor", "Slytherin", ...]
    typical_attributes: list[str]         # ["founder", "element", "animal"]
    confidence: float                     # 0.0–1.0


class InducedRelationType(BaseModel):
    """Un type de relation avec contraintes."""
    relation_name: str                    # "belongs_to_house"
    source_type: str                      # "Character"
    target_type: str                      # "House"
    cardinality: str                      # "1:1", "1:N", "N:N"
    temporal: bool                        # True si la relation peut changer
    description: str


class InducedPattern(BaseModel):
    """Pattern textuel récurrent découvert."""
    pattern_regex: str                    # r"\[Skill Acquired: (.+?)\]"
    extraction_type: str                  # "skill_acquisition"
    example: str                          # "[Skill Acquired: Shadow Step]"
    confidence: float
```

### 3.2 Traduction SagaProfile → Pydantic models pour Graphiti

L'innovation technique : le SagaProfileInducer génère dynamiquement des classes Pydantic compatibles avec l'API `entity_types` de Graphiti.

```python
from pydantic import create_model, Field

def saga_profile_to_graphiti_types(
    profile: SagaProfile,
) -> dict[str, type[BaseModel]]:
    """Convertit un SagaProfile en dict entity_types pour Graphiti.add_episode()."""

    # Types universels (toujours présents)
    types: dict[str, type[BaseModel]] = {
        "Character": Character,   # Pydantic model fixe
        "Location": Location,
        "Object": Object,
        "Organization": Organization,
        "Event": Event,
        "Concept": Concept,
    }

    # Types induits (dynamiques, générés à partir du profil)
    for induced in profile.entity_types:
        attrs = {
            attr: (str | None, Field(None, description=f"{attr} of {induced.type_name}"))
            for attr in induced.typical_attributes
        }
        # Génère dynamiquement : class Spell(BaseModel): incantation: str | None = None; ...
        model = create_model(induced.type_name, **attrs)
        types[induced.type_name] = model

    return types


def saga_profile_to_graphiti_edges(
    profile: SagaProfile,
) -> tuple[dict[str, type[BaseModel]], dict[tuple[str, str], list[str]]]:
    """Convertit les relations induites en edge_types + edge_type_map pour Graphiti."""
    edge_types = {}
    edge_type_map = {}

    for rel in profile.relation_types:
        # Crée un edge type Pydantic
        edge_model = create_model(
            rel.relation_name,
            temporal=(bool, Field(default=rel.temporal)),
        )
        edge_types[rel.relation_name] = edge_model
        # Map source→target → allowed edge types
        key = (rel.source_type, rel.target_type)
        edge_type_map.setdefault(key, []).append(rel.relation_name)

    return edge_types, edge_type_map
```

### 3.3 Algorithme d'induction (Discovery Mode)

**Entrée** : graphe Graphiti après ingestion du tome 1 avec types universels uniquement.

**Étape 1 — Extraction des candidats**
- Requête Neo4j : récupérer tous les Entity nodes du `group_id` de la saga
- Graphiti les a déjà typés (labels Entity + le type universel choisi par le LLM)
- Récupérer les entity summaries et les edges (prédicats) les plus fréquents

**Étape 2 — Clustering sémantique**
- Embedder les noms + summaries des Entity nodes (même embedder que Graphiti pour cohérence)
- Clustering hiérarchique (agglomerative, seuil cosine > 0.75)
- Chaque cluster = un candidat de type induit
- Ex: cluster ["Expelliarmus", "Patronus", "Avada Kedavra", "Lumos"] → type candidat Spell

**Étape 3 — Formalisation LLM**
- Pour chaque cluster significatif (≥3 instances), appel LLM :
  "Voici N entités extraites d'un roman : [liste + summaries].
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
- Générer les modèles Pydantic dynamiques via `saga_profile_to_graphiti_types()`

**Sortie** : SagaProfile validé + dict entity_types prêts pour Graphiti.

### 3.4 Guided Mode (tomes suivants)

1. Charger le SagaProfile existant → convertir en `entity_types` + `edge_types` + `edge_type_map`
2. Injecter dans `graphiti.add_episode_bulk(entity_types=..., edge_types=..., edge_type_map=...)`
3. Pre-scan regex avec les patterns du SagaProfile → pré-annotation des passages structurés
4. Après ingestion : re-run SagaProfileInducer en mode "delta"
   - Détecte les nouveaux clusters non couverts par le profil existant
   - Propose des évolutions : "Nouveau type découvert : Horcrux (3 instances)"
   - Incrémente version si le profil évolue

### 3.5 Exemples concrets d'induction

**Harry Potter — tome 1 :**
- Cluster : ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"] → `House`
- Cluster : ["Expelliarmus", "Wingardium Leviosa", "Alohomora"] → `Spell`
- Cluster : ["Hippogriffe", "Basilic", "Norbert"] → `MagicalCreature`
- Relation induite : `Character -[belongs_to_house]-> House` (1:1, non-temporel)
- Relation induite : `Character -[casts]-> Spell` (N:N, temporel)
- Pas de patterns structurés (prose pure)

**Primal Hunter — tome 1 :**
- Cluster : ["Shadow Step", "Arcane Powershot", "Stealth"] → `Skill`
- Cluster : ["Bloodline of the Primal Hunter"] → `Bloodline`
- Cluster : ["Alchemist", "Archer of the Apex Hunter"] → `Class`
- Patterns détectés : `[Skill Acquired: X]`, `[Level X → Y]`, `[Quest Complete: X]`
- Relation induite : `Character -[has_skill]-> Skill` (N:N, temporel)
- Relation induite : `Character -[has_class]-> Class` (1:N, temporel)

**L'Assassin Royal — tome 1 :**
- Cluster : ["Art", "Vif"] → `MagicSystem` (seulement 2 instances — confiance moyenne)
- Pas de patterns structurés → `text_patterns: []`
- Profil plus simple, l'inducteur s'adapte à la complexité de l'univers

---

## 4. Intégration Graphiti (moteur central)

### 4.1 Rôle

Graphiti est le moteur unique pour : extraction d'entités/relations (via LLM interne), entity resolution, stockage temporel (bi-temporel), entity summaries évolutifs, retrieval hybride (semantic + BM25 + BFS).

### 4.2 Client Graphiti partagé

```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

class GraphitiClient:
    """Client Graphiti singleton, initialisé dans le lifespan FastAPI."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_auth: tuple[str, str],
        llm_client: LLMClient | None = None,
        embedder: EmbedderClient | None = None,
    ):
        self.client = Graphiti(
            uri=neo4j_uri,
            user=neo4j_auth[0],
            password=neo4j_auth[1],
            llm_client=llm_client,      # Gemini 2.5 Flash via LiteLLM
            embedder=embedder,           # BGE-m3 (cohérent avec SagaProfileInducer)
        )

    async def init_schema(self) -> None:
        """Initialise les indexes et contraintes Graphiti dans Neo4j."""
        await self.client.build_indices_and_constraints()

    async def ingest_book_discovery(
        self,
        chapters: list[RawEpisode],
        saga_id: str,
    ) -> None:
        """Ingestion Discovery Mode : types universels uniquement."""
        universal_types = {
            "Character": Character,
            "Location": Location,
            "Object": Object,
            "Organization": Organization,
            "Event": Event,
            "Concept": Concept,
        }
        await self.client.add_episode_bulk(
            bulk_episodes=chapters,
            entity_types=universal_types,
            group_id=saga_id,
        )

    async def ingest_book_guided(
        self,
        chapters: list[RawEpisode],
        saga_id: str,
        profile: SagaProfile,
    ) -> None:
        """Ingestion Guided Mode : types universels + induits."""
        entity_types = saga_profile_to_graphiti_types(profile)
        edge_types, edge_type_map = saga_profile_to_graphiti_edges(profile)
        await self.client.add_episode_bulk(
            bulk_episodes=chapters,
            entity_types=entity_types,
            edge_types=edge_types,
            edge_type_map=edge_type_map,
            group_id=saga_id,
        )

    async def search(
        self,
        query: str,
        saga_id: str,
        num_results: int = 20,
    ) -> list:
        """Recherche hybride Graphiti (semantic + BM25 + BFS)."""
        return await self.client.search(
            query=query,
            group_ids=[saga_id],
            num_results=num_results,
        )

    async def close(self) -> None:
        await self.client.close()
```

### 4.3 Modèle temporel narratif

Graphiti exige des `datetime` pour son modèle bi-temporel. Pour la fiction, le mapping est :

```python
class NarrativeTemporalMapper:
    """Mappe (book, chapter, scene_order) → datetime pour Graphiti.

    Chaque saga a son propre espace temporel via group_id.
    Les datetime ne sont PAS comparables entre sagas différentes.
    """

    EPOCH = datetime(2000, 1, 1)
    BOOK_OFFSET_DAYS = 10_000  # chaque livre décalé de ~27 ans

    @staticmethod
    def to_datetime(book_num: int, chapter_num: int, scene_order: int = 0) -> datetime:
        if book_num < 1 or chapter_num < 0:
            raise ValueError(f"Invalid book_num={book_num} or chapter_num={chapter_num}")
        days = (book_num - 1) * NarrativeTemporalMapper.BOOK_OFFSET_DAYS + chapter_num
        seconds = scene_order
        return NarrativeTemporalMapper.EPOCH + timedelta(days=days, seconds=seconds)

    @staticmethod
    def from_datetime(dt: datetime) -> tuple[int, int, int]:
        delta = dt - NarrativeTemporalMapper.EPOCH
        if delta.days < 0:
            raise ValueError(f"Datetime {dt} is before epoch {NarrativeTemporalMapper.EPOCH}")
        book = delta.days // NarrativeTemporalMapper.BOOK_OFFSET_DAYS + 1
        chapter = delta.days % NarrativeTemporalMapper.BOOK_OFFSET_DAYS
        scene = delta.seconds
        return book, chapter, scene

    @staticmethod
    def chapter_to_episodes(
        chapters: list,
        book_id: str,
        book_num: int,
    ) -> list:
        """Convertit les chapitres parsés en RawEpisode Graphiti."""
        from graphiti_core.utils.bulk_utils import RawEpisode

        episodes = []
        for ch in chapters:
            episodes.append(RawEpisode(
                name=f"{book_id}:ch{ch.number}",
                body=ch.text,
                source_description=f"Chapter {ch.number} of {book_id}",
                reference_time=NarrativeTemporalMapper.to_datetime(book_num, ch.number),
                source=EpisodeType.text,
            ))
        return episodes
```

**Note** : les valeurs datetime ne sont PAS comparables entre sagas différentes. Le `group_id` de Graphiti assure l'isolation. Toutes les requêtes incluent `group_ids=[saga_id]`.

### 4.4 Embeddings

Graphiti accepte un `EmbedderClient` custom. Pour la cohérence (même espace vectoriel partout), on configure Graphiti avec BGE-m3, le même embedder que le SagaProfileInducer utilise pour le clustering.

```python
# Configuration dans le lifespan FastAPI
from graphiti_core.embedder import EmbedderClient

# Graphiti + SagaProfileInducer utilisent le même embedder
embedder = BGEm3Embedder()  # wrapper autour de sentence-transformers/BAAI/bge-m3
graphiti = GraphitiClient(
    neo4j_uri=settings.neo4j_uri,
    neo4j_auth=(settings.neo4j_user, settings.neo4j_password),
    embedder=embedder,
)
```

---

## 5. KGGen — Rôle optionnel de clustering post-hoc

### 5.1 Pourquoi KGGen est optionnel

Graphiti fait sa propre entity resolution (exact → embedding → LLM). KGGen ajoute une passe de clustering itératif inspirée du crowd-sourcing qui peut capturer des aliases que Graphiti manque.

### 5.2 Usage

```python
from kg_gen import KGGen

class PostHocClusterer:
    """Clustering optionnel post-Graphiti via KGGen."""

    def __init__(self):
        self.kg = KGGen(model="gemini/gemini-2.5-flash")

    async def find_missed_aliases(self, entity_names: list[str]) -> dict[str, list[str]]:
        """Détecte les alias manqués par Graphiti.

        Retourne {canonical_name: [alias1, alias2, ...]}
        """
        # Construire un pseudo-texte avec les noms d'entités pour le clustering
        text = ". ".join(f"{name} is an entity" for name in entity_names)
        graph = self.kg.generate(input_data=text, cluster=True)
        return graph.entity_clusters  # {canonical: [variants]}
```

**Quand l'activer** : en post-processing, après l'ingestion Graphiti, si le nombre d'entités est élevé (>200) ou si l'on suspecte des doublons (détection heuristique via embeddings proches).

---

## 6. Pipeline chat redesigné

### 6.1 Simplification

Le pipeline actuel a 17 nœuds LangGraph. Avec Graphiti comme backend, la majorité deviennent inutiles.

| Nœud actuel | Statut |
|---|---|
| router (intent 6 routes) | **Gardé** — simplifié à 3 routes |
| query_transform | **Supprimé** — Graphiti gère la recherche sémantique |
| hyde | **Supprimé** — retrieval Graphiti déjà hybride (3 modes) |
| retrieve | **Remplacé** par `graphiti.search()` |
| rerank (zerank) | **Supprimé** — Graphiti fusionne et ranke ses 3 modes |
| dedup | **Supprimé** — Graphiti déduplique nativement |
| temporal_sort | **Supprimé** — Graphiti trie temporellement nativement |
| kg_query | **Remplacé** par Cypher sur types Graphiti |
| context_assembly | **Gardé** — enrichi avec entity summaries Graphiti |
| generate (CoT) | **Gardé** |
| faithfulness (NLI) | **Gardé** — avec retry loop |
| memory | **Gardé** — checkpointing PostgreSQL |

### 6.2 Nouveau graph LangGraph (8 nœuds)

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
                   │ faithfulness │◄──────────┐
                   │   (NLI)      │           │
                   └──────┬───────┘           │
                          │                   │
                     pass ▼            fail   │
                   ┌──────────────┐  (max 2)  │
                   │    done      │───────────┘
                   └──────────────┘  reformulate
```

**3 routes :**
- `graphiti_search` — questions ouvertes, thématiques, narratives → API Graphiti (semantic + BM25 + BFS)
- `cypher_lookup` — questions structurées précises ("skills de Jake au chapitre 30") → Cypher sur types Graphiti
- `direct` — conversationnel, pas de retrieval

**Context assembly enrichi :**
- Entity summaries Graphiti (résumés évolutifs par entité)
- Community summaries Leiden (thèmes de haut niveau)
- Episodic chunks (passages source pour les citations)
- Edges temporels filtrés (spoiler guard via max_chapter → NarrativeTemporalMapper)

**Retry loop** (préservé du pipeline v1) : si le score NLI < seuil, reformuler la query → re-retrieve → re-generate. Max 2 retries.

---

## 7. Coûts et performances attendues

### 7.1 Coût par livre (Gemini 2.5 Flash)

| Étape | Coût estimé |
|---|---|
| Graphiti ingestion (LLM extraction + entity resolution + summaries) | ~$0.30 |
| SagaProfileInducer (tome 1 uniquement) | ~$0.03 |
| KGGen clustering post-hoc (optionnel) | ~$0.06 |
| Community summaries (Leiden + LLM) | ~$0.03 |
| **Total (tome 1)** | **~$0.42** |
| **Total (tomes suivants, sans KGGen)** | **~$0.33** |

### 7.2 Performances retrieval attendues

| Métrique | Pipeline actuel | Nouveau pipeline |
|---|---|---|
| Latence retrieval | ~200ms (vector + rerank) | ~300ms (Graphiti 3-modes) |
| Multi-hop | Non (vector search shallow) | Oui (BFS Graphiti) |
| Questions temporelles | Basique (WHERE clause) | Natif (bi-temporel) |
| Questions thématiques | Non | Oui (community summaries) |
| Entity summaries | Non | Oui (Graphiti natif) |
| Retry sur faithfulness | Oui (max 2) | Oui (préservé) |

---

## 8. Infrastructure

### 8.1 Préservée

| Composant | Notes |
|---|---|
| FastAPI + lifespan | Ajoute GraphitiClient dans app.state |
| arq workers | Tâches refactorisées pour Graphiti |
| Redis | Cache + task queue inchangé |
| PostgreSQL | Checkpointing + feedback + migrations |
| LangFuse + LangSmith | Callbacks inchangés |
| Frontend Next.js | Adapté pour lire les types dynamiques Graphiti |
| Auth middleware | Inchangé |
| Admin API (DLQ, costs) | DLQ adapté : échec chapitre → re-queue pour Graphiti |

### 8.2 Docker Compose — changements

```yaml
neo4j:
  image: neo4j:5-community
  environment:
    NEO4J_PLUGINS: '["apoc", "graph-data-science"]'   # Ajout GDS pour Leiden
    NEO4J_dbms_security_procedures_allowlist: "apoc.*,gds.*"
    NEO4J_dbms_memory_heap_max__size: "6G"  # GDS crée des projections in-memory
    NEO4J_dbms_memory_pagecache_size: "3G"
  mem_limit: 12g  # Augmenté pour GDS
```

**Note** : vérifier que Leiden est disponible en Neo4j Community Edition (certains algorithmes GDS nécessitent Enterprise). Alternative : implémenter Leiden via la lib Python `leidenalg` directement sur les données exportées.

### 8.3 Reader agent

Le reader agent actuel (`backend/app/agents/reader/`) est **supprimé**. Ses fonctionnalités (Q&A in-chapter) sont couvertes par le nouveau chat pipeline avec le filtre `max_chapter` + route `cypher_lookup`.

---

## 9. Dépendances

### 9.1 Ajoutées

| Package | Rôle |
|---|---|
| `graphiti-core` | Moteur central : extraction + stockage + retrieval |
| `kg-gen` | Clustering post-hoc optionnel |
| `leidenalg` | Community clustering (fallback si GDS indisponible) |

### 9.2 Supprimées

| Package | Raison |
|---|---|
| `langextract` | Remplacé par Graphiti extraction |
| `instructor` | Remplacé par Graphiti extraction |
| `voyageai` | VoyageAI n'était déjà plus utilisé (aliasé vers LocalEmbedder) |
| `thefuzz` | Remplacé par Graphiti entity resolution |

---

## 10. Test migration

### 10.1 Tests supprimés (correspondant au code supprimé)

- `tests/test_extraction_*.py` — tous les tests d'extraction custom
- `tests/test_reconciler.py` — reconciler 3-tier supprimé
- `tests/test_entity_registry.py` — EntityRegistry supprimé
- `tests/test_ontology*.py` — ontologie YAML supprimée
- `tests/test_embeddings.py` — LocalEmbedder supprimé
- `tests/test_chat_*.py` (partiellement) — nœuds supprimés (hyde, rerank, dedup)

### 10.2 Nouveaux tests

| Test | Ce qu'il valide |
|---|---|
| `test_saga_profile_inducer.py` | Induction sur 3 sagas de test (mock LLM) |
| `test_pydantic_generator.py` | Génération dynamique de modèles Pydantic |
| `test_narrative_temporal_mapper.py` | Mapping chapitre ↔ datetime (round-trip) |
| `test_graphiti_client.py` | Ingestion + search (mock Graphiti ou instance test) |
| `test_discovery_guided_flow.py` | Flow complet Discovery → Profile → Guided |
| `test_chat_pipeline_v2.py` | Nouveau pipeline 8 nœuds (mock retrieval) |
| `test_community_clustering.py` | Leiden + LLM summaries |

---

## 11. Métriques de validation

**Test sur 3 sagas :**
1. **Primal Hunter** (LitRPG, blue boxes, progression) — SagaProfile doit capturer Skill, Class, Bloodline, patterns `[Skill Acquired: X]`
2. **Harry Potter** (fantasy classique, prose pure) — doit capturer Spell, House, MagicalCreature
3. **L'Assassin Royal** (fantasy low-magic) — profil simple (MagicSystem avec 2 instances)

**Benchmarks :**
- MINE-narratif adapté : 50 faits annotés manuellement par livre, score de retrouvabilité
- Comparaison coût/qualité vs pipeline v1 sur Primal Hunter
- Latence retrieval P95 < 500ms
- Faithfulness NLI score moyen sur 50 questions de test

---

## 12. Risques identifiés

| Risque | Mitigation |
|---|---|
| Graphiti `add_episode_bulk` ne supporte pas `entity_types` | Vérifier l'API au sprint 1. Fallback : `add_episode` séquentiel (plus lent) |
| Leiden indisponible en Neo4j Community | Fallback : `leidenalg` Python sur données exportées |
| SagaProfileInducer produit un profil dégénéré (trop peu de types, ou faux positifs) | Seuil de confiance 0.6 + validation humaine optionnelle |
| Graphiti extraction qualité inférieure à KGGen | Activer KGGen clustering post-hoc + comparer sur benchmark MINE |
| Coût Graphiti supérieur aux estimations (double LLM calls internes) | Monitorer via LangSmith, ajuster le LLM (Gemini Flash Lite si besoin) |
