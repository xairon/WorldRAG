# WorldRAG — Extraction Single-Pass SOTA

**Design Spec — v2 (post-review)**
*2026-03-16 — Nicolas, LIFAT / Université de Tours*

---

## 1. Vision

Refactorer le pipeline d'extraction de Knowledge Graph en remplaçant les **4 passes LangExtract parallèles** par une architecture **2-step KGGen-style** (entities → relations) utilisant **Instructor** pour la sortie structurée. Le pipeline reste custom (pas de Graphiti pour l'extraction), avec Neo4j direct comme stockage.

### Objectifs

1. **Speed** — 2 appels LLM par chapitre au lieu de 4-8 (~2x plus rapide)
2. **Cohérence** — le step 2 (relations) voit TOUTES les entités, capture les liens cross-type
3. **Prompt quality** — 2 prompts unifiés au lieu de 4 prompts redondants
4. **Maintainability** — ~8 fichiers au lieu de ~15, schema unique, moins de state management

### Principes directeurs

1. **KGGen 2-step prouvé** — 66% MINE vs 48% GraphRAG (NeurIPS 2025)
2. **Instructor comme couche structurée** — provider-agnostic (Gemini, ollama, GPT-4o-mini), retry + validation Pydantic
3. **Garder ce qui marche** — Regex Passe 0, mention detector, 3-tier dedup, entity registry, Neo4j MERGE/UNWIND
4. **Temporalité chapter-based** — valid_from/to_chapter (naturel pour la fiction), invalidation active + retcon
5. **Full schema + router hints** — 14 types toujours dans le prompt (11 core/genre + 3 Layer 3), router hint guide l'attention

### Ce qui change vs pipeline actuel

| Composant | Actuel | Nouveau |
|---|---|---|
| Extraction | 4 passes LangExtract parallèles | 2-step Instructor (entities → relations) |
| Sortie structurée | LangExtract (CharInterval) | Instructor (Pydantic discriminated union) |
| Prompts | 4 prompts domaine-spécifiques × ~200 lignes | 2 prompts unifiés × ~300 lignes |
| LangGraph | 8 nœuds (route, 4 passes, merge, mention, reconcile+narrative) | 5 nœuds linéaires (regex→entities→relations→mention→reconcile) |
| State | 4 result types + fan-out + Send | 2 result types, linéaire |
| Coreference (Pass 5b) | LLM, 1er pronom/segment, confidence×0.8 | Supprimé (valeur marginale) |
| Narrative (Pass 6) | LLM, truncated 15k chars | Supprimé (remplacé par entity summaries book-level) |
| Post-extraction book-level | Rien | Iterative clustering + entity summaries + community clustering |

### Ce qui ne change PAS

- Ingestion EPUB/PDF/TXT (ebooklib, pdfplumber, paragraphes typés)
- Chunking (1000 tokens, 100 overlap, paragraph-aware)
- Regex Passe 0 ($0, déterministe, blue boxes LitRPG)
- Mention detector ($0, programmatique, word-boundary)
- Entity registry (contexte croissant cross-chapitres)
- 3-tier dedup (exact → fuzzy → LLM-as-Judge)
- Neo4j persistence (MERGE/UNWIND, batch_id, GROUNDED_IN, temporal)
- Embedding pipeline (local bge-m3, GPU, $0)
- arq workers + Redis pub/sub progress
- Cost tracker + DLQ
- Provider infrastructure (rate limiting, circuit breakers, resilience)

---

## 2. Architecture du pipeline

### 2.1 Vue d'ensemble

```
CHAPTER-LEVEL (séquentiel — pour EntityRegistry)
══════════════════════════════════════════════════

  Chapter text + regex_matches (Passe 0)
       │
       ▼
  ┌──────────────────┐
  │ extract_entities │  Step 1 — 1 appel LLM (Instructor)
  │                  │  11 types, flat array, full schema + router hints
  │                  │  Retourne: entities[] avec offsets
  └────┬─────────────┘
       │
       ▼
  ┌──────────────────┐
  │ extract_relations│  Step 2 — 1 appel LLM (Instructor)
  │                  │  Reçoit entities[] + texte
  │                  │  Retourne: relations[] + ended_relations[]
  └────┬─────────────┘
       │
       ▼
  ┌──────────────────┐
  │ mention_detect   │  $0, programmatique
  │                  │  Word-boundary regex sur noms/aliases extraits
  └────┬─────────────┘
       │
       ▼
  ┌──────────────────┐
  │ reconcile_persist│  3-tier dedup → alias_map → normalize
  │                  │  → Neo4j MERGE/UNWIND → update EntityRegistry
  └──────────────────┘


BOOK-LEVEL (après tous les chapitres)
══════════════════════════════════════

  ┌──────────────────┐
  │ iterative_cluster│  KGGen-style sur toutes les entités du livre
  └────┬─────────────┘
       ▼
  ┌──────────────────┐
  │ entity_summaries │  1 appel LLM par entité significative (~50-100)
  └────┬─────────────┘
       ▼
  ┌──────────────────┐
  │ community_cluster│  leidenalg + LLM summaries par communauté
  └────┬─────────────┘
       ▼
  ┌──────────────────┐
  │ embed_chunks     │  Local bge-m3, GPU, $0 (inchangé)
  └──────────────────┘
```

### 2.2 LangGraph chapter-level — 5 nœuds linéaires

```python
graph = StateGraph(ExtractionState)

graph.add_node("extract_entities", extract_entities_node)
graph.add_node("extract_relations", extract_relations_node)
graph.add_node("mention_detect", mention_detect_node)
graph.add_node("reconcile_persist", reconcile_and_persist_node)

graph.add_edge(START, "extract_entities")
graph.add_edge("extract_entities", "extract_relations")
graph.add_edge("extract_relations", "mention_detect")
graph.add_edge("mention_detect", "reconcile_persist")
graph.add_edge("reconcile_persist", END)
```

Pas de fan-out, pas de Send, pas de merge. Linéaire et simple. Le parallélisme est au niveau du provider (pas besoin de paralléliser les nœuds — on fait 2 appels séquentiels au lieu de 4 parallèles, et c'est plus rapide car chaque appel est plus léger).

### 2.3 Comparaison performance

| Métrique | Actuel (4-pass) | Nouveau (2-step) |
|---|---|---|
| Appels LLM / chapitre (extraction) | 4 | 2 |
| Appels LLM / chapitre (dedup) | 1-10 | 1-10 (inchangé) |
| Appels LLM / chapitre (coref + narrative) | 2-6 | 0 (supprimés) |
| **Total LLM / chapitre** | **7-20** | **3-12** |
| Latence / chapitre (ollama qwen3:32b) | ~4-8 min | ~1.5-3 min |
| Latence / chapitre (Gemini Flash) | ~30-60s | ~15-30s |
| Cohérence cross-type | Non | Oui (step 2 voit toutes les entités) |
| Fichiers source extraction | ~15 | ~8 |

---

## 3. Schemas Pydantic (Instructor)

### 3.1 Step 1 — Extraction d'entités (discriminated union)

```python
from pydantic import BaseModel, Field
from typing import Annotated, Literal, Union

# ── Entités individuelles ─────────────────────────────────────────────

class ExtractedCharacter(BaseModel):
    entity_type: Literal["character"] = "character"
    name: str = Field(..., description="Nom exact tel qu'écrit dans le texte")
    canonical_name: str = Field("", description="Nom complet en minuscules, sans articles")
    aliases: list[str] = Field(default_factory=list)
    role: Literal["protagonist", "antagonist", "mentor", "sidekick",
                   "ally", "minor", "neutral"] = "minor"
    species: str = ""
    description: str = ""
    status: Literal["alive", "dead", "unknown", "transformed"] = "alive"
    extraction_text: str = Field(..., description="Span textuel source exact")
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedSkill(BaseModel):
    entity_type: Literal["skill"] = "skill"
    name: str
    description: str = ""
    skill_type: Literal["active", "passive", "racial", "class",
                         "profession", "unique"] = "active"
    rank: str = ""
    owner: str = ""
    effects: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedClass(BaseModel):
    entity_type: Literal["class"] = "class"  # "class" is valid as a Literal string value
    name: str
    tier: int | None = None
    owner: str = ""
    description: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedTitle(BaseModel):
    entity_type: Literal["title"] = "title"
    name: str
    effects: list[str] = Field(default_factory=list)
    owner: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedEvent(BaseModel):
    entity_type: Literal["event"] = "event"
    name: str
    description: str = ""
    event_type: Literal["action", "state_change", "achievement",
                         "process", "dialogue"] = "action"
    significance: Literal["minor", "moderate", "major",
                           "critical", "arc_defining"] = "moderate"
    participants: list[str] = Field(default_factory=list)
    location: str = ""
    is_flashback: bool = False
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedLocation(BaseModel):
    entity_type: Literal["location"] = "location"
    name: str
    location_type: str = ""
    parent_location: str = ""
    description: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedItem(BaseModel):
    entity_type: Literal["item"] = "item"
    name: str
    item_type: str = ""
    rarity: str = ""
    effects: str = ""
    owner: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedCreature(BaseModel):
    entity_type: Literal["creature"] = "creature"
    name: str
    species: str = ""
    threat_level: str = ""
    habitat: str = ""
    description: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedFaction(BaseModel):
    entity_type: Literal["faction"] = "faction"
    name: str
    faction_type: str = ""
    alignment: str = ""
    description: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedConcept(BaseModel):
    entity_type: Literal["concept"] = "concept"
    name: str
    domain: str = ""
    description: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedLevelChange(BaseModel):
    entity_type: Literal["level_change"] = "level_change"
    character: str
    old_level: int | None = None
    new_level: int | None = None
    realm: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedStatChange(BaseModel):
    entity_type: Literal["stat_change"] = "stat_change"
    character: str
    stat_name: str
    value: int
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── Layer 3: Series-specific entities ─────────────────────────────────


class ExtractedBloodline(BaseModel):
    entity_type: Literal["bloodline"] = "bloodline"
    name: str
    description: str = ""
    effects: list[str] = Field(default_factory=list)
    origin: str = ""
    owner: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedProfession(BaseModel):
    entity_type: Literal["profession"] = "profession"
    name: str
    tier: int | None = None
    profession_type: str = ""
    owner: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


class ExtractedChurch(BaseModel):
    entity_type: Literal["church"] = "church"
    deity_name: str
    domain: str = ""
    blessing: str = ""
    worshipper: str = ""
    extraction_text: str
    char_offset_start: int = -1
    char_offset_end: int = -1


# ── Union discriminée ─────────────────────────────────────────────────

EntityUnion = Annotated[
    Union[
        # Layer 1+2 (core + genre)
        ExtractedCharacter, ExtractedSkill, ExtractedClass, ExtractedTitle,
        ExtractedEvent, ExtractedLocation, ExtractedItem, ExtractedCreature,
        ExtractedFaction, ExtractedConcept, ExtractedLevelChange,
        ExtractedStatChange,
        # Layer 3 (series-specific)
        ExtractedBloodline, ExtractedProfession, ExtractedChurch,
    ],
    Field(discriminator="entity_type"),
]


class EntityExtractionResult(BaseModel):
    """Step 1 result — flat array of typed entities."""
    entities: list[EntityUnion] = Field(
        default_factory=list,
        description="Toutes les entités extraites, dans l'ordre d'apparition",
    )
    chapter_number: int = 0  # Self-contained chapter context
```

**Notes de design** :
- `char_offset_start/end = -1` par défaut (pas None) — le LLM peut omettre et on post-valide
- `entity_type` en Literal pour la discriminated union — Instructor + Pydantic v2 natif
- `Literal["class"]` est valide Python — `class` n'est réservé que comme identifiant, pas comme valeur de string
- Pas de `confidence` dans le schema LLM — la confidence vient du post-processing (alignment check)
- `extraction_text` obligatoire partout — force le grounding
- Layer 3 (Bloodline, Profession, Church) inclus dans l'EntityUnion — pas de pass séparé
- `chapter_number` ajouté à `EntityExtractionResult` pour rendre le résultat self-contained

**Contrainte critique : `from __future__ import annotations`**

Le fichier `extraction_v4.py` et le fichier state NE DOIVENT PAS utiliser `from __future__ import annotations`. LangGraph utilise `get_type_hints()` au runtime pour résoudre le schema du state — les annotations déférées cassent cette résolution silencieusement. Tous les fichiers dans la chaîne d'import du state (schemas, state, graph) doivent utiliser des types concrets.

**Nommage du fichier schemas** : `extraction_v4.py` (convention interne — le "v4" réfère à la 4e itération du pipeline d'extraction, même si les fichiers v2/v3 n'existent pas séparément)

### 3.2 Step 2 — Extraction de relations

```python
class ExtractedRelation(BaseModel):
    """Une relation entre deux entités."""
    source: str = Field(..., description="Nom canonique de l'entité source")
    target: str = Field(..., description="Nom canonique de l'entité cible")
    relation_type: Literal[
        "RELATES_TO", "MEMBER_OF", "HAS_SKILL", "HAS_CLASS", "HAS_TITLE",
        "PARTICIPATES_IN", "OCCURS_AT", "LOCATED_AT", "POSSESSES",
        "CAUSES", "ENABLES", "PART_OF", "EVOLVES_INTO", "IS_RACE",
        "INHABITS", "BELONGS_TO",
    ]
    subtype: str = Field("", description="Précision (père, mentor, allié, etc.)")
    sentiment: float | None = Field(None, ge=-1.0, le=1.0,
                                     description="Pour RELATES_TO uniquement")
    valid_from_chapter: int | None = None
    context: str = Field("", description="Bref extrait du texte justifiant la relation")


class RelationEnd(BaseModel):
    """Invalidation d'une relation existante dans ce chapitre."""
    source: str
    target: str
    relation_type: str
    ended_at_chapter: int
    reason: str = ""


class RelationExtractionResult(BaseModel):
    """Step 2 result — relations + invalidations temporelles."""
    relations: list[ExtractedRelation] = Field(default_factory=list)
    ended_relations: list[RelationEnd] = Field(
        default_factory=list,
        description="Relations qui cessent d'être vraies dans ce chapitre",
    )
```

**Notes de design** :
- `relation_type` contraint par Literal — l'ontologie core.yaml + litrpg.yaml définit les types autorisés
- `RelationEnd` pour l'invalidation temporelle — le Neo4j repo met à jour `valid_to_chapter`
- `source`/`target` sont des noms canoniques — doivent correspondre aux entités du step 1
- Le prompt du step 2 reçoit la liste d'entités extraites, donc le LLM est contraint

**Migration des relation types existants** :
Le pipeline actuel stocke les relations character-to-character comme `rel_type` (ally, enemy, mentor, etc.).
Dans v4, ces valeurs deviennent `relation_type=RELATES_TO` + `subtype=ally|enemy|mentor|...`.
Le `entity_repo.upsert_relationships()` doit être adapté :
- Actuel : `MERGE (a)-[:RELATES_TO {type: $rel_type}]->(b)`
- v4 : `MERGE (a)-[:RELATES_TO {subtype: $subtype, sentiment: $sentiment}]->(b)`
- Migration des données existantes : un script de migration met à jour les anciennes relations
  `SET r.subtype = r.type, r.type = null` (one-shot, réversible)

### 3.3 State LangGraph simplifié

```python
import operator
from typing import Annotated, Any
from typing_extensions import TypedDict


class ExtractionState(TypedDict, total=False):
    """State pour le nouveau pipeline 2-step."""

    # -- Input (set avant invocation) --
    book_id: str
    chapter_number: int
    chapter_text: str
    chunk_texts: list[str]
    regex_matches_json: str
    genre: str
    series_name: str
    source_language: str
    model_override: str | None

    # -- Cross-book context --
    entity_registry: dict  # EntityRegistry serialized
    series_entities: list[dict[str, Any]]

    # -- Step 1 result --
    entities: list[dict[str, Any]]  # EntityUnion serialized

    # -- Step 2 result --
    relations: list[dict[str, Any]]  # ExtractedRelation serialized
    ended_relations: list[dict[str, Any]]  # RelationEnd serialized

    # -- Grounding --
    grounded_entities: Annotated[list[dict[str, Any]], operator.add]

    # -- Reconciliation --
    alias_map: dict[str, str]

    # -- Metrics --
    total_cost_usd: float
    total_entities: int
    errors: Annotated[list[dict[str, Any]], operator.add]
```

30 lignes au lieu de 106. Pas de `characters`, `systems`, `events`, `lore` séparés — tout est dans `entities[]` (flat array).

### 3.4 Pipeline de grounding et population du registry

La validation de grounding est intégrée dans le nœud `extract_entities` (pas un nœud séparé) :

```python
async def extract_entities_node(state: ExtractionState) -> dict:
    """Step 1: extract entities + validate grounding inline."""
    # 1. Build prompt (full schema + router hints + registry context + Phase 0 hints)
    # 2. Call Instructor → EntityExtractionResult
    # 3. Post-validate grounding for each entity:
    for entity in result.entities:
        status, confidence = validate_grounding(entity, state["chapter_text"])
        grounded = GroundedEntity(
            entity_type=entity.entity_type,
            entity_name=entity.name,
            extraction_text=entity.extraction_text,
            char_offset_start=entity.char_offset_start,
            char_offset_end=entity.char_offset_end,
            alignment_status=status,
            confidence=confidence,
            pass_name="entities",
        )
        grounded_entities.append(grounded)
    # 4. Return entities + grounded_entities
    return {"entities": [...], "grounded_entities": grounded_entities}
```

Le nœud `reconcile_persist` peuple le registry depuis le flat array :

```python
async def reconcile_and_persist_node(state: ExtractionState) -> dict:
    # ...after reconciliation + persist...
    # Populate EntityRegistry from flat array
    registry = EntityRegistry.from_dict(state.get("entity_registry", {}))
    for entity_dict in state["entities"]:
        entity_type = entity_dict["entity_type"]
        name = entity_dict.get("canonical_name") or entity_dict["name"]
        aliases = entity_dict.get("aliases", [])
        registry.add(
            name=name,
            entity_type=entity_type,
            aliases=aliases,
            significance=_infer_significance(entity_dict),
            first_seen_chapter=state["chapter_number"],
            description=entity_dict.get("description", ""),
        )
    return {"entity_registry": registry.to_dict()}
```

### 3.5 Gestion des chapitres multi-chunks

Les chapitres longs (>1000 tokens) sont découpés en chunks. L'extraction opère **par chapitre, pas par chunk** :

- Le step 1 reçoit le `chapter_text` complet (pas les chunks individuels)
- Gemini 2.5 Flash (1M context) et qwen3:32b (128k context) gèrent des chapitres de 8-32k tokens sans problème
- Les chunks servent uniquement pour l'embedding et le GROUNDED_IN (localisation dans le chapitre)
- Si un chapitre dépasse 32k tokens (très rare) : fallback vers extraction per-chunk avec merge post-hoc

---

## 4. Prompts unifiés

### 4.1 Prompt Step 1 — Extraction d'entités

Le prompt est construit dynamiquement via `build_extraction_prompt()` (base.py modifié) avec :

**Role description** :
```
un expert en extraction d'information pour Knowledge Graphs narratifs,
spécialisé dans la fiction LitRPG et progression fantasy
```

**Prompt description** (corps principal) :
```
Extrais TOUTES les entités de ce chapitre dans un flat array JSON.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms, descriptions et attributs en français, exactement comme ils
apparaissent dans le texte source. Ne traduis JAMAIS en anglais.

=== TYPES D'ENTITÉS (11 types — ontologie complète) ===

CHARACTER : personnage nommé
- name, canonical_name, aliases, role, species, description, status
- Extrais UNIQUEMENT les personnages NOMMÉS (pas "le guerrier", "il", "elle")

SKILL : compétence / aptitude
- name, skill_type (active/passive/racial/class/profession/unique), rank, owner, effects

CLASS : classe de combat / métier
- name, tier (entier), owner, description

TITLE : titre honorifique ou de système
- name, effects, owner

EVENT : événement narratif significatif
- name (2-6 mots), description, event_type, significance, participants, location, is_flashback
- NE SUR-EXTRAIS PAS : combine les micro-actions en un seul événement

LOCATION : lieu nommé
- name, location_type, parent_location, description
- UNIQUEMENT les lieux NOMMÉS (pas "la forêt", "un bâtiment")

ITEM : objet nommé ou unique
- name, item_type, rarity, effects, owner
- UNIQUEMENT les objets NOMMÉS (pas "une épée", "des flèches")

CREATURE : espèce / monstre nommé
- name, species, threat_level, habitat, description

FACTION : organisation / guilde / ordre
- name, faction_type, alignment, description

CONCEPT : concept du monde (systèmes magiques, règles, cosmologie)
- name, domain, description

LEVEL_CHANGE : montée de niveau
- character, old_level, new_level, realm

STAT_CHANGE : changement de statistique
- character, stat_name, value (entier, positif ou négatif)

=== TYPES SPÉCIFIQUES À LA SÉRIE (Layer 3 — injectés si la série les définit) ===

BLOODLINE : lignée de sang (Primal Hunter, etc.)
- name, description, effects, origin, owner

PROFESSION : métier / profession non-combat
- name, tier, profession_type (crafting/combat/utility/social), owner

CHURCH : église / culte primordial
- deity_name, domain, blessing, worshipper

(Ces types sont inclus dans le prompt uniquement si l'ontologie Layer 3 de la
série les définit. Pour une série sans Layer 3, seuls les 11 types core sont présents.)

=== BLUE BOXES (indices Phase 0) ===
Les romans LitRPG contiennent des notifications système entre crochets [].
Les indices Phase 0 dans le CONTEXTE contiennent des extractions regex
de ces blue boxes. CONFIRME-les avec tes extractions narratives.

=== GROUNDING ===
Pour chaque entité, retourne :
- extraction_text : le span textuel EXACT copié du texte source
- char_offset_start / char_offset_end : position en caractères dans le texte

=== RÈGLES ===
- Extrais dans l'ORDRE D'APPARITION dans le texte
- Utilise les noms EXACTS tels qu'écrits (majuscules, accents, espaces)
- canonical_name en minuscules, sans articles (le/la/les/the/a)
- NE CRÉE PAS d'entités pour des références génériques
- Si un personnage est dans le registre d'entités, RÉFÉRENCIE-le par son canonical_name
- Qualité > quantité
```

**Router hints** (injectés dynamiquement basé sur le keyword scan) :
```
=== FOCUS ===
Le scan de ce chapitre indique une présence forte de :
- Éléments de système (skills, classes, levels) — extrais avec attention particulière
- [ou] Éléments de lore (lieux, items, créatures) — extrais avec attention particulière
- [ou] Développements de personnages — extrais relations et rôles avec soin
```

**Few-shot examples** : 2-3 exemples gold couvrant tous les types, adaptés au genre. Format JSON montrant le flat array `entities[]` avec tous les types mélangés.

### 4.2 Prompt Step 2 — Extraction de relations

**Role description** :
```
un expert en analyse de relations narratives pour Knowledge Graphs,
spécialisé dans les liens entre entités de fiction
```

**Prompt description** :
```
Étant donné le texte du chapitre ET la liste d'entités extraites ci-dessous,
extrais TOUTES les relations entre ces entités.

=== ENTITÉS EXTRAITES (Step 1) ===
{entities_json}

=== TYPES DE RELATIONS AUTORISÉS ===
- RELATES_TO : relation entre personnages (source=Character, target=Character)
  → subtype: ally, enemy, mentor, family, romantic, rival, patron, subordinate
  → subtype précis: père, mère, frère, sœur, époux, maître, disciple
  → sentiment: -1.0 (hostile) à 1.0 (amical)
- MEMBER_OF : appartenance à une faction (source=Character, target=Faction)
- HAS_SKILL : possession d'une compétence (source=Character, target=Skill)
- HAS_CLASS : possession d'une classe (source=Character, target=Class)
- HAS_TITLE : possession d'un titre (source=Character, target=Title)
- PARTICIPATES_IN : participation à un événement (source=Character, target=Event)
- OCCURS_AT : localisation d'un événement (source=Event, target=Location)
- LOCATED_AT : position d'une entité (source=any, target=Location)
- POSSESSES : possession d'un objet (source=Character, target=Item)
- CAUSES : causalité entre événements (source=Event, target=Event)
- ENABLES : un événement rend possible un autre (source=Event, target=Event)
- PART_OF : inclusion (source=Location, target=Location)
- EVOLVES_INTO : évolution (source=Skill/Class, target=Skill/Class)
- IS_RACE : race d'un personnage (source=Character, target=Creature)
- INHABITS : habitat d'une créature (source=Creature, target=Location)
- BELONGS_TO : appartenance système (source=Skill, target=Class)

=== INVALIDATION TEMPORELLE ===
Si une relation existante CESSE d'être vraie dans ce chapitre :
- Un personnage perd une compétence → RelationEnd(HAS_SKILL)
- Une alliance se brise → RelationEnd(RELATES_TO)
- Un personnage quitte une faction → RelationEnd(MEMBER_OF)
- Un personnage meurt → RelationEnd sur toutes ses relations actives

Retourne ces invalidations dans ended_relations[].

=== RÈGLES ===
- source et target DOIVENT être des noms d'entités extraites au Step 1
- Extrais UNIQUEMENT les relations explicitement déclarées ou clairement impliquées
- NE DÉDUIS PAS de relations spéculatives
- valid_from_chapter = numéro du chapitre courant (pour les nouvelles relations)
- context = bref extrait textuel justifiant la relation
```

### 4.3 Langue des prompts

Les prompts v4 sont écrits en français (langue principale du corpus cible). Le support bilingue de `build_extraction_prompt()` (FR/EN via `PromptLanguage`) est conservé : les prompts ci-dessus sont la version française, la version anglaise sera générée en traduisant les descriptions de types et les règles. Le `source_language` dans le state détermine la langue utilisée.

### 4.4 Adaptation de build_extraction_prompt()

Modifications à `backend/app/prompts/base.py` :
- Ajouter paramètre `router_hints: list[str] | None` — injecté comme section `[FOCUS]`
- Ajouter paramètre `extracted_entities_json: str | None` — pour le step 2
- Le `phase` passe de 0-6 à simplement "entities" ou "relations"
- Ontology schema remplacé par la description inline des types (plus lisible pour le LLM)

---

## 5. Temporalité — Modèle chapter-based enrichi

### 5.1 Modèle existant (conservé)

```cypher
// Entités avec fenêtre de validité
(c:Character {canonical_name: "jake", valid_from_chapter: 1})
(s:Skill {name: "shadow step", valid_from_chapter: 5, valid_to_chapter: 30})

// Relations temporelles
(c)-[:HAS_SKILL {valid_from_chapter: 5, valid_to_chapter: null}]->(s)
```

### 5.2 Ajouts — Invalidation active

Le step 2 produit des `RelationEnd` que le Neo4j repo traite :

```cypher
// Invalidation d'une relation existante
MATCH (source)-[r:HAS_SKILL]->(target:Skill {name: $skill_name})
WHERE source.canonical_name = $source_name
  AND r.valid_to_chapter IS NULL
SET r.valid_to_chapter = $ended_at_chapter,
    r.end_reason = $reason
```

### 5.3 Ajouts — Retcon detection

Si le step 2 crée une relation qui contredit une relation active :

```cypher
// Marquer l'ancienne relation comme retconnée
MATCH (a)-[r:RELATES_TO]->(b)
WHERE r.valid_to_chapter IS NULL AND r.retconned IS NULL
SET r.retconned = true, r.retconned_by_chapter = $chapter
// Créer la nouvelle relation
MERGE (a)-[:RELATES_TO {
    subtype: $subtype,
    valid_from_chapter: $chapter,
    retconned: false,
    batch_id: $batch_id
}]->(b)
```

### 5.4 Requêtes temporelles (pour le chat)

```cypher
// "Quelles skills Jake avait-il au chapitre 20 ?"
MATCH (c:Character {canonical_name: "jake"})-[r:HAS_SKILL]->(s:Skill)
WHERE r.valid_from_chapter <= 20
  AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter >= 20)
  AND (r.retconned IS NULL OR r.retconned = false)
RETURN s.name, r.valid_from_chapter

// Spoiler guard
MATCH (c:Character)-[r]->(target)
WHERE r.valid_from_chapter <= $max_chapter
RETURN c, r, target
```

---

## 6. Post-processing book-level

### 6.1 Iterative clustering (KGGen-style)

Après extraction de tous les chapitres, un pass global détecte les aliases manqués par le dedup per-chapter :

```python
async def iterative_cluster(driver: AsyncDriver, book_id: str) -> dict[str, str]:
    """KGGen-style clustering sur toutes les entités d'un livre.

    Algorithme :
    1. Récupérer tous les noms d'entités du livre (Neo4j)
    2. Grouper par entity_type
    3. Pour chaque type avec >5 entités :
       a. Embedder les noms + descriptions (bge-m3)
       b. Cosine similarity matrix
       c. Paires avec similarity > 0.85 → candidates
       d. LLM-as-Judge sur les candidates (batch Instructor)
       e. Appliquer les merges (MERGE Neo4j + alias_map)
    4. Itérer (max 3 rounds) jusqu'à convergence

    Retourne: alias_map global {alias -> canonical}
    """
```

**Coût** : ~$0.02-0.05 par livre (embedding local + quelques appels LLM pour les paires ambiguës).

### 6.2 Entity summaries

Résumés évolutifs par entité, enrichis avec toutes les mentions à travers le livre :

```python
async def generate_entity_summaries(
    driver: AsyncDriver,
    book_id: str,
    min_mentions: int = 3,
) -> list[EntitySummary]:
    """Génère des résumés pour les entités significatives.

    1. Fetch entités avec >= min_mentions mentions (GROUNDED_IN count)
    2. Pour chaque entité :
       a. Collecter tous les extraction_text ordonnés par chapitre
       b. LLM (Instructor) : générer summary de 2-3 phrases
       c. Stocker comme propriété `summary` sur le nœud Neo4j
    3. Entités protagonistes/majeures : summary plus long (5-8 phrases)
    """
```

**Schema** :
```python
class EntitySummary(BaseModel):
    entity_name: str
    entity_type: str
    summary: str = Field(..., description="Résumé en 2-8 phrases")
    key_facts: list[str] = Field(default_factory=list, description="Faits clés")
    first_chapter: int
    last_chapter: int
    mention_count: int
```

**Neo4j** :
```cypher
MATCH (e {canonical_name: $name})
SET e.summary = $summary,
    e.key_facts = $key_facts,
    e.mention_count = $mention_count
```

**Coût** : ~$0.03-0.08 par livre (50-100 entités × ~500 tokens chacune).

### 6.3 Community clustering (Leiden)

Groupes thématiques de haut niveau via l'algorithme de Leiden :

```python
import leidenalg
import igraph as ig

async def community_cluster(driver: AsyncDriver, book_id: str) -> list[Community]:
    """Clustering communautaire via leidenalg.

    1. Exporter le graphe Neo4j en igraph :
       - Nœuds = entités (Character, Skill, Location, etc.)
       - Arêtes = relations (HAS_SKILL, RELATES_TO, OCCURS_AT, etc.)
       - Poids = nombre de co-occurrences dans les chunks
    2. Leiden clustering (resolution=1.0, n_iterations=10)
    3. Pour chaque communauté de taille >= 3 :
       a. Extraire les noms + types des membres
       b. LLM : générer un résumé thématique (1-2 phrases)
       c. Stocker comme nœud Community dans Neo4j
    """
```

**Neo4j** :
```cypher
MERGE (comm:Community {id: $community_id})
ON CREATE SET
    comm.book_id = $book_id,
    comm.summary = $summary,
    comm.member_count = $member_count,
    comm.batch_id = $batch_id,
    comm.created_at = datetime()
ON MATCH SET
    comm.summary = $summary,
    comm.member_count = $member_count,
    comm.batch_id = $batch_id
WITH comm
UNWIND $member_names AS member_name
MATCH (e {canonical_name: member_name})
MERGE (e)-[:BELONGS_TO_COMMUNITY]->(comm)
```

**Coût** : ~$0.01-0.03 par livre (clustering local + ~10-20 appels LLM pour les summaries).

### 6.4 Rollback des opérations book-level

Toutes les opérations book-level utilisent un `batch_id` dédié (`book-level:{book_id}:{timestamp}`) :

```cypher
// Rollback entity summaries
MATCH (e) WHERE e.summary_batch_id = $batch_id
REMOVE e.summary, e.key_facts, e.mention_count, e.summary_batch_id

// Rollback community clustering
MATCH (comm:Community {batch_id: $batch_id})
DETACH DELETE comm

// Rollback iterative clustering alias merges
// Les merges sont tracés dans un log Redis (worldrag:cluster_log:{book_id})
// Rollback = restaurer les noms originaux depuis le log
```

En cas d'échec partiel, le worker marque le book status comme `book_level_partial` et log les opérations complétées vs échouées dans le DLQ.

---

## 7. Grounding et post-validation

### 7.1 Inline grounding (step 1)

Le LLM retourne `extraction_text`, `char_offset_start`, `char_offset_end` pour chaque entité. Ces offsets sont post-validés :

```python
def validate_grounding(entity: EntityUnion, chapter_text: str) -> tuple[str, float]:
    """Post-validate offsets returned by LLM.

    Returns: (alignment_status, confidence)
    - "exact" (1.0) : extraction_text found at claimed offset
    - "fuzzy" (0.7) : extraction_text found elsewhere in text
    - "unaligned" (0.3) : extraction_text not found in text
    """
    if entity.char_offset_start >= 0 and entity.char_offset_end > 0:
        claimed = chapter_text[entity.char_offset_start:entity.char_offset_end]
        if claimed.strip() == entity.extraction_text.strip():
            return "exact", 1.0

    # Fuzzy fallback — find extraction_text anywhere
    idx = chapter_text.find(entity.extraction_text)
    if idx >= 0:
        entity.char_offset_start = idx
        entity.char_offset_end = idx + len(entity.extraction_text)
        return "fuzzy", 0.7

    # Partial match
    ratio = fuzz.partial_ratio(entity.extraction_text, chapter_text)
    if ratio > 80:
        return "fuzzy", 0.5

    return "unaligned", 0.3
```

### 7.2 Mention detection (inchangé, $0)

Après le step 1, le mention detector retrouve toutes les occurrences supplémentaires des entités extraites dans le texte, via word-boundary regex. Chaque mention supplémentaire crée une relation MENTIONED_IN (pas GROUNDED_IN) vers le chunk correspondant.

---

## 8. Files to create / modify / delete

### 8.1 Créer

| Fichier | Contenu |
|---|---|
| `backend/app/services/extraction/entities.py` | Step 1 : `extract_entities_node()` — appel Instructor, post-validation grounding |
| `backend/app/services/extraction/relations.py` | Step 2 : `extract_relations_node()` — appel Instructor avec entités du step 1 |
| `backend/app/prompts/extraction_unified.py` | Prompt unifié entities + prompt relations + few-shot examples |
| `backend/app/schemas/extraction_v4.py` | Schemas Pydantic v4 (EntityUnion, RelationExtractionResult, etc.) |
| `backend/app/services/extraction/book_level.py` | Post-processing : iterative clustering + entity summaries + community clustering |

### 8.2 Modifier

| Fichier | Modification |
|---|---|
| `backend/app/services/extraction/__init__.py` | Réécrire le LangGraph (5 nœuds linéaires) |
| `backend/app/agents/state.py` | Simplifier ExtractionState (30 lignes vs 106) |
| `backend/app/prompts/base.py` | Ajouter `router_hints`, `extracted_entities_json`, simplifier `phase` |
| `backend/app/services/extraction/reconciler.py` | Adapter pour le flat array EntityUnion au lieu de 4 result types |
| `backend/app/services/extraction/mention_detector.py` | Adapter input (entités viennent d'un flat array) |
| `backend/app/services/graph_builder.py` | Adapter `_apply_alias_map()` pour le flat array + relations |
| `backend/app/repositories/entity_repo.py` | Ajouter `apply_relation_end()`, `upsert_entity_summary()`, `upsert_community()` |
| `backend/app/workers/tasks.py` | Nouveau `process_book_extraction_v4()` avec book-level post-processing |
| `backend/app/schemas/extraction.py` | Garder pour backward compat, déprécier, importer les nouveaux schemas |

### 8.3 Supprimer (après migration complète)

| Fichier | Raison |
|---|---|
| `backend/app/services/extraction/characters.py` | Remplacé par entities.py |
| `backend/app/services/extraction/systems.py` | Remplacé par entities.py |
| `backend/app/services/extraction/events.py` | Remplacé par entities.py |
| `backend/app/services/extraction/lore.py` | Remplacé par entities.py |
| `backend/app/services/extraction/coreference.py` | Supprimé (valeur marginale) |
| `backend/app/services/extraction/narrative.py` | Remplacé par entity summaries |
| `backend/app/services/extraction/router.py` | Le routage devient des hints dans le prompt, pas un nœud LangGraph |
| `backend/app/prompts/extraction_characters.py` | Remplacé par extraction_unified.py |
| `backend/app/prompts/extraction_systems.py` | Remplacé par extraction_unified.py |
| `backend/app/prompts/extraction_events.py` | Remplacé par extraction_unified.py |
| `backend/app/prompts/extraction_lore.py` | Remplacé par extraction_unified.py |
| `backend/app/prompts/extraction_creatures.py` | Remplacé par extraction_unified.py |
| `backend/app/prompts/extraction_provenance.py` | Intégré dans les relations (step 2) |
| `backend/app/prompts/extraction_series.py` | Intégré dans le prompt unifié |
| `backend/app/prompts/extraction_discovery.py` | Reporté (SagaProfileInducer futur) |
| `backend/app/prompts/coreference.py` | Supprimé avec coreference.py |
| `backend/app/prompts/narrative_analysis.py` | Remplacé par entity summaries |

---

## 9. Instructor integration

### 9.1 Provider factory

```python
# Dans backend/app/llm/providers.py — ajout

def get_instructor_for_extraction(
    model_override: str | None = None,
) -> tuple[instructor.AsyncInstructor, str]:
    """Get Instructor client for extraction steps.

    Default: Gemini 2.5 Flash
    Override: ollama (qwen3:32b) via OpenAI-compatible endpoint
    """
    if model_override and model_override.startswith("local:"):
        model_name = model_override.removeprefix("local:")
        client = instructor.from_openai(
            openai.AsyncOpenAI(
                base_url=settings.ollama_base_url,
                api_key="ollama",
            ),
            mode=instructor.Mode.JSON,
        )
        return client, model_name

    # Default: Gemini
    client = instructor.from_gemini(
        get_gemini_client(),
        mode=instructor.Mode.GEMINI_JSON,
    )
    return client, settings.extraction_model
```

### 9.2 Appel extraction

```python
async def extract_entities(
    chapter_text: str,
    prompt: str,
    model_override: str | None = None,
) -> EntityExtractionResult:
    """Step 1: Extract entities via Instructor."""
    client, model = get_instructor_for_extraction(model_override)

    result = await client.chat.completions.create(
        model=model,
        response_model=EntityExtractionResult,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": chapter_text},
        ],
        max_retries=3,
    )
    return result
```

### 9.3 Retry et rate limiting

- Instructor a son propre retry (max_retries=3) pour les erreurs de validation Pydantic
- Le retry infra existant (`extract_with_retry` / tenacity) gère les erreurs réseau/quota
- Les deux se composent : infra retry wraps Instructor retry

---

## 10. Migration et backward compatibility

### 10.1 Stratégie

1. **v4 en parallèle** — nouveau code dans les mêmes modules, nouveau endpoint `POST /books/{id}/extract/v4`
2. **v3 conservé** — pas de suppression immédiate, les deux coexistent
3. **A/B testing** — extraire le même livre en v3 et v4, comparer qualité
4. **Suppression v3** — après validation qualité sur 3 livres de test

### 10.2 Endpoint

```python
@router.post("/books/{book_id}/extract/v4")
async def extract_book_v4(
    book_id: str,
    background: BackgroundTasks,
    genre: str = "litrpg",
    provider: str | None = None,
):
    """Enqueue v4 single-pass extraction job."""
    await enqueue_job("process_book_extraction_v4", book_id, genre, provider)
    return {"job_id": f"extract-v4:{book_id}", "pipeline": "v4-2step"}
```

---

## 11. Coûts estimés

### 11.1 Per-chapter (Gemini 2.5 Flash)

| Étape | Input tokens | Output tokens | Coût |
|---|---|---|---|
| Step 1 (entities) | ~3k (prompt) + ~4k (chunk) = ~7k | ~2k | $0.0022 |
| Step 2 (relations) | ~3k (prompt) + ~4k (chunk) + ~1k (entities) = ~8k | ~1k | $0.0018 |
| Dedup (si Tier 3) | ~500 | ~200 | $0.0002 |
| **Total / chapitre** | | | **~$0.004** |

### 11.2 Per-book (76 chapitres)

| Étape | Coût |
|---|---|
| Chapter-level extraction (76 × $0.004) | ~$0.30 |
| Iterative clustering (book-level) | ~$0.03 |
| Entity summaries (~80 entités) | ~$0.05 |
| Community summaries (~15 communautés) | ~$0.02 |
| **Total / livre** | **~$0.40** |

### 11.3 Per-book (ollama qwen3:32b — $0)

| Étape | Coût | Temps estimé |
|---|---|---|
| Chapter-level extraction | $0 | ~2-3h (76 ch × 1.5-2.5 min) |
| Iterative clustering | $0 | ~10 min |
| Entity summaries | $0 | ~20 min |
| Community summaries | $0 | ~5 min |
| **Total** | **$0** | **~3-4h** |

### 11.4 Comparaison vs actuel

| Pipeline | Coût / livre (Gemini) | Temps / livre (ollama) |
|---|---|---|
| v3 (4-pass) | ~$0.60 | ~6-10h |
| **v4 (2-step)** | **~$0.40** | **~3-4h** |
| Gain | -33% | -50% |

---

## 12. Testing

### 12.1 Tests à créer

| Test | Ce qu'il valide |
|---|---|
| `test_entity_extraction.py` | Step 1 sur 3 fixtures de chapitres (mock Instructor) |
| `test_relation_extraction.py` | Step 2 avec entités connues (mock Instructor) |
| `test_extraction_schemas_v4.py` | Discriminated union, sérialisation/désérialisation |
| `test_extraction_graph_v4.py` | LangGraph 5-nœud end-to-end (mock LLM) |
| `test_relation_end.py` | Invalidation temporelle dans Neo4j |
| `test_iterative_clustering.py` | Book-level clustering (mock embeddings + LLM) |
| `test_entity_summaries.py` | Génération de summaries (mock LLM) |
| `test_community_clustering.py` | Leiden + summaries (mock graphe) |
| `test_grounding_validation.py` | Post-validation exact/fuzzy/unaligned |
| `test_instructor_providers.py` | Gemini / ollama / GPT-4o-mini provider switching |

### 12.2 Tests à modifier

| Test | Modification |
|---|---|
| `test_reconciler.py` | Adapter input format (flat array vs 4 result types) |
| `test_mention_detector.py` | Adapter input format |
| `test_graph_builder.py` | Adapter `_apply_alias_map()` |

### 12.3 Tests à supprimer

Tous les tests spécifiques aux 4 passes (test_characters.py, test_systems.py, test_events.py, test_lore.py, test_coreference.py, test_narrative.py) — remplacés par les nouveaux tests.

---

## 13. Risques identifiés

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Instructor discriminated union trop complexe pour ollama/qwen3:32b | Moyen | Élevé | Tester tôt ; fallback: 2 appels séparés par type-group |
| Quality dégradation vs 4 passes spécialisées | Faible | Moyen | A/B test sur 3 livres ; les prompts unifiés sont plus complets |
| Entity summaries coût trop élevé (>100 entités) | Faible | Faible | Seuil min_mentions=3, batch Instructor |
| Leiden clustering donne des communautés non-significatives | Moyen | Faible | Tuner resolution parameter ; filter size < 3 |
| RelationEnd mal détecté (invalidation incorrecte) | Moyen | Moyen | Validation conservative (confidence >= 0.8 dans le prompt) |
| Regression sur le grounding (offsets moins précis sans LangExtract) | Faible | Moyen | Post-validation fuzzy catchs 95% ; mention detector couvre le reste |

---

## 14. Métriques de validation

### 14.1 Qualité extraction

Test sur 3 livres : Primal Hunter (LitRPG), Harry Potter (fantasy), L'Assassin Royal (low-fantasy)

| Métrique | Seuil acceptable | Méthode |
|---|---|---|
| Entity recall | ≥ 90% vs v3 | 50 entités annotées manuellement par livre |
| Relation recall | ≥ 85% vs v3 | 30 relations annotées manuellement |
| Entity precision | ≥ 95% | % entités non-hallucinated |
| Grounding accuracy | ≥ 80% exact, ≥ 95% exact+fuzzy | Post-validation stats |
| Dedup F1 (book-level) | ≥ 90% | Paires annotées |

### 14.2 Performance

| Métrique | Seuil | Méthode |
|---|---|---|
| Latence / chapitre (Gemini) | ≤ 30s | Timer dans le worker |
| Latence / chapitre (ollama) | ≤ 3 min | Timer dans le worker |
| Coût / livre (Gemini) | ≤ $0.50 | Cost tracker |
| Total temps / livre (ollama) | ≤ 4h | Job duration |

---

## 15. Dépendances

### 15.1 Existantes (pas de changement)

- `instructor` (déjà dans le projet pour reconciliation)
- `langgraph` (simplifié mais conservé)
- `leidenalg` (déjà dans pyproject.toml)
- `structlog`, `tenacity`, `pydantic`, `neo4j`

### 15.2 Ajoutées

| Package | Rôle | Taille |
|---|---|---|
| `igraph` | Graph export pour Leiden (vérifier si transitive dep de leidenalg, sinon ajouter) | ~15 MB |

### 15.3 Supprimées

| Package | Raison |
|---|---|
| `langextract` | Remplacé par Instructor |

---

## 16. Ordre d'implémentation recommandé

1. **Schemas v4** — EntityUnion, RelationExtractionResult, ExtractionState
2. **Prompts unifiés** — extraction_unified.py (entities + relations)
3. **Step 1 node** — entities.py + Instructor integration
4. **Step 2 node** — relations.py + Instructor integration
5. **LangGraph v4** — 5 nœuds, réécriture de `__init__.py`
6. **Adapter reconciler** — flat array input
7. **Adapter mention detector** — flat array input
8. **Adapter graph_builder** — alias_map + relations + relation_end
9. **Adapter entity_repo** — `apply_relation_end()`, temporal updates
10. **Worker v4** — `process_book_extraction_v4()` + endpoint
11. **Book-level** — iterative clustering + entity summaries + community clustering
12. **Tests** — unit + integration + A/B vs v3
13. **Cleanup** — supprimer v3 fichiers après validation
