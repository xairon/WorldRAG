# Cahier des charges : Refondation ontologique sur GOLEM

> **Objectif** : Remplacer l'ontologie core.yaml ad-hoc par une fondation alignee sur GOLEM (v1.1, 2024), l'ontologie narrative la plus complete et recente de la litterature scientifique, sans perte de fonctionnalite.

## 1. Contexte et motivation

### Probleme actuel

L'ontologie `core.yaml` actuelle est un assemblage custom qui cite des references academiques (CIDOC-CRM, SEM, DOLCE, OntoMedia) sans les implementer formellement. Les 9 types core (Character, Event, Location, Item, Creature, Faction, Concept, Arc, Prophecy) ont ete definis empiriquement. Il n'y a pas de fondation theorique rigoureuse.

### Pourquoi GOLEM

GOLEM (General Ontology for Literary and Narrative Entities and Metadata) est :
- La seule ontologie formelle conçue specifiquement pour la fiction (publiee 2024-2025)
- Construite sur 3 standards : DOLCE (upper), CIDOC-CRM (ISO 21127, events/temps), LRMoo (bibliographie)
- Activement maintenue (ERC StG 2023-2027, Univ. Groningen)
- Publiee en OWL 2 avec documentation formelle
- Licence CC BY 4.0

### Principe de la migration

```
AVANT                                    APRES
=====                                    =====
core.yaml (custom, 9 types)             core.yaml (GOLEM-aligned, ~18 types)
  + litrpg.yaml (genre)                   + litrpg.yaml (genre, inchange)
  + series.yaml (serie)                   + series.yaml (serie, inchange)
  + induced (runtime)                     + induced (runtime, inchange)
```

Seule la couche 1 (core) change. Les couches 2 (genre), 3 (serie) et induced restent identiques — GOLEM ne couvre pas les game mechanics, c'est par design.

---

## 2. Mapping complet : GOLEM → WorldRAG

### 2.1 Types conserves (renommage + enrichissement)

Ces types existent deja dans WorldRAG et ont un equivalent GOLEM direct. Ils sont conserves avec enrichissement.

| WorldRAG actuel | GOLEM equivalent | Changements |
|----------------|------------------|-------------|
| **Character** | G1 Character | Ajouter : `agency` (active/passive/ambiguous), retirer `role` (deplace vers NarrativeRole) |
| **Event** | G5 Narrative Event | Ajouter : `event_category` (action/state_change/process/achievement — aligne DOLCE perdurant taxonomy). Renforcer : `significance` reste, `fabula_order` reste |
| **Location** | G13 Narrative Location | Inchange. Ajouter `fictional_status` (real/fictional/semi-fictional — GOLEM distingue les lieux reels qui apparaissent dans la fiction) |
| **Item** | G16 Object | Renommer en **Object** (alignement GOLEM). Proprietes inchangees. |
| **Arc** | — (pas dans GOLEM directement, mais modelable via G7 Narrative Sequence) | Conserver tel quel. GOLEM modelise les arcs narratifs via des sequences ordonnees de Narrative Units, mais c'est trop granulaire pour l'extraction. Arc reste un type WorldRAG sans equivalent GOLEM strict. |
| **Concept** | — (pas de type GOLEM equivalent) | Conserver tel quel. GOLEM n'a pas de type "concept abstrait du monde fictionnel". C'est un type WorldRAG utile (magie, politique, cosmologie). |
| **Prophecy** | — (pas dans GOLEM) | Conserver tel quel. C'est un type narratif specifique utile pour la fantasy/LitRPG. |
| **Creature** | — (pas dans GOLEM) | Conserver tel quel. GOLEM ne distingue pas creatures et personnages (tout est G1 Character ou G16 Object). WorldRAG a besoin de la distinction pour la fiction genre. |
| **Faction** | — (pas dans GOLEM) | Conserver tel quel. GOLEM modelise les groupes via G4 Social Relationship, pas comme des entites first-class. Pour l'extraction, Faction comme noeud est plus pratique. |

### 2.2 Nouveaux types a ajouter (depuis GOLEM)

| Nouveau type | GOLEM source | Ce qu'il modelise | Pourquoi c'est necessaire |
|-------------|-------------|-------------------|--------------------------|
| **PsychologicalState** | G3 | Etat mental temporel d'un personnage : emotion, motivation, croyance, objectif | Permet de tracer l'arc emotionnel : Jake passe de "curious" a "determined" a "desperate". Actuellement perdu. |
| **Setting** | G12 | Univers narratif / contexte global (pas un lieu physique) | "The Tutorial", "The Multiverse", "Nevermore" sont des Settings, pas des Locations. Distinction importante pour le worldbuilding. |
| **CharacterFeature** | G17 | Trait de personnage qui peut changer dans le temps : biographique, physique, psychologique | Permet de tracer : "Jake est humain" (biographique), "Jake a les yeux verts" (physique), "Jake est solitaire" (psychologique). Les traits evoluent — temporal. |
| **NarrativeRole** | G11 | Role narratif d'un personnage dans l'histoire, temporel | Actuellement `Character.role = protagonist` est statique. Avec NarrativeRole : Jake est "hero" dans le Tutorial (ch1-30), "mentor" pour Miranda (ch31-50), "anti-hero" dans l'arc politique (ch51+). |
| **SocialRelationship** | G4 | Relation entre personnages reifiee comme noeud | Actuellement RELATES_TO est un edge. Comme noeud : la relation Jake-Casper est "amitie" (ch1-20) puis "mentor" (ch21+), causee par l'Event "Battle of the Clearing". La relation a une histoire. |
| **RelationshipRole** | G6 | Role d'un personnage dans une relation sociale | Jake est "mentee" dans la relation Jake-Villy. Villy est "patron". Chacun a un role different dans la meme relation. |

### 2.3 Types enrichis (proprietes ajoutees depuis GOLEM)

| Type existant | Proprietes ajoutees | Source GOLEM |
|--------------|---------------------|-------------|
| **Character** | `agency: enum [active, passive, ambiguous]` | DOLCE agentive/non-agentive distinction |
| **Character** | `fictional_status: enum [fictional, semi-fictional, historical]` | GOLEM G1 |
| **Event** | `event_category: enum [action, state_change, process, achievement, dialogue, encounter, discovery, revelation, transition, combat]` | DOLCE perdurant taxonomy (rename de event_type actuel) |
| **Location** | `fictional_status: enum [fictional, real, semi_fictional]` | GOLEM G13 |

### 2.4 Relations ajoutees (depuis GOLEM)

| Nouvelle relation | Source → Target | GOLEM source | Ce qu'elle modelise |
|------------------|----------------|-------------|-------------------|
| **HAS_STATE** | Character → PsychologicalState | G1 → G3 via has-state | Etat mental a un moment donne |
| **STATE_TRIGGERED_BY** | PsychologicalState → Event | G3 follows G5 | L'event qui a cause cet etat |
| **IN_SETTING** | Character/Event/Location → Setting | participant-in → G12 | Rattachement a un univers narratif |
| **HAS_FEATURE** | Character → CharacterFeature | G1 → G17 via GP0 | Trait de personnage (temporel) |
| **PLAYS_ROLE** | Character → NarrativeRole | G1 → G11 via plays | Role narratif temporel |
| **INVOLVED_IN** | Character → SocialRelationship | G1 → G4 | Participation a une relation sociale |
| **RELATIONSHIP_CAUSED_BY** | SocialRelationship → Event | G4 → G5 | Event qui a cree/modifie la relation |

### 2.5 Relations existantes conservees

Toutes les relations actuelles de core.yaml sont conservees :

```
CONTAINS_WORK, HAS_CHAPTER, HAS_CHUNK (bibliographiques)
PARTICIPATES_IN, OCCURS_AT, OCCURS_BEFORE, CAUSES, ENABLES (evenementielles)
LOCATED_AT, LOCATION_PART_OF (spatiales)
POSSESSES (objets)
MEMBER_OF (factions)
PERCEIVED_BY (epistemique)
MENTIONED_IN, FIRST_MENTIONED_IN, GROUNDED_IN (ancrage textuel)
```

### 2.6 Relations deprecees

| Relation | Remplacement | Raison |
|----------|-------------|--------|
| **RELATES_TO** (edge Character→Character) | **INVOLVED_IN** (Character→SocialRelationship) + **INVOLVED_IN** (Character→SocialRelationship) | Reification GOLEM G4. RELATES_TO etait un fourre-tout. SocialRelationship permet l'evolution temporelle. |

**Migration** : les edges RELATES_TO existants deviennent des noeuds SocialRelationship avec deux edges INVOLVED_IN. C'est un changement de schema majeur.

---

## 3. Impact sur le pipeline d'extraction

### 3.1 Schemas Pydantic (`extraction_v4.py`)

**Ajouts** (nouveaux modeles Instructor) :

```python
class ExtractedPsychologicalState(BaseModel):
    entity_type: Literal["psychological_state"]
    character: str          # personnage concerne
    state_type: str         # emotion | motivation | belief | goal
    name: str               # "determination", "fear", "desire for revenge"
    description: str = ""
    trigger_event: str = "" # nom de l'event declencheur

class ExtractedSetting(BaseModel):
    entity_type: Literal["setting"]
    name: str               # "The Tutorial", "Nevermore"
    description: str = ""

class ExtractedCharacterFeature(BaseModel):
    entity_type: Literal["character_feature"]
    character: str
    feature_type: str       # biographical | physical | psychological
    name: str               # "green eyes", "human", "loner"
    description: str = ""

class ExtractedNarrativeRole(BaseModel):
    entity_type: Literal["narrative_role"]
    character: str
    role_type: str          # protagonist | antagonist | mentor | trickster | herald | guardian | shadow
    context: str = ""       # dans quel arc/contexte

class ExtractedSocialRelationship(BaseModel):
    entity_type: Literal["social_relationship"]
    participants: list[str]  # 2+ personnages
    relationship_type: str   # friendship | rivalry | romance | family | mentorship | patron | alliance | enmity
    description: str = ""
    trigger_event: str = ""  # event declencheur
```

**Modifications** :

- `EntityUnion` : ajouter les 5 nouveaux types au discriminated union
- `ExtractedCharacter` : retirer `role` (deplace vers NarrativeRole), ajouter `agency`
- `ExtractedEvent` : renommer `event_type` en `event_category` (alignement DOLCE)
- `ExtractedItem` : renommer en `ExtractedObject` (alignement GOLEM G16)
- `ExtractedRelation` : ajouter support pour les relations impliquant SocialRelationship

### 3.2 Prompts d'extraction (`entity_descriptions.yaml`)

**Ajouter** les descriptions des 5 nouveaux types avec exemples positifs et negatifs.

**Modifier** les descriptions existantes :
- CHARACTER : retirer la mention de `role` statique, ajouter `agency`
- EVENT : utiliser `event_category` avec la taxonomie DOLCE
- ITEM → OBJECT : renommer partout

**Negative examples** a ajouter :
- "Jake was determined" → NE PAS extraire comme Event. C'est un PsychologicalState.
- "The Tutorial" → NE PAS extraire comme Location. C'est un Setting.
- "Jake has green eyes" → NE PAS extraire comme Event. C'est un CharacterFeature.

### 3.3 Noeud de verification (`verify.py`)

**Nouvelles regles** :
- PsychologicalState doit referencer un Character connu
- CharacterFeature doit referencer un Character connu
- NarrativeRole doit referencer un Character connu
- SocialRelationship doit avoir au moins 2 participants connus
- Setting ne doit pas etre un lieu specifique (distinction Setting/Location)

### 3.4 Reconciliation (`reconciler.py`)

**Cross-type dedup** — nouveau priority map :

```python
_TYPE_PRIORITY = {
    "character": 10,
    "social_relationship": 9,
    "location": 9,
    "setting": 8,
    "creature": 8,
    "object": 7,     # ex-item
    "faction": 7,
    "psychological_state": 6,
    "character_feature": 6,
    "narrative_role": 6,
    "level_change": 6,
    "stat_change": 6,
    "event": 5,
    "arc": 4,
    "prophecy": 4,
    "concept": 3,
    "genre_entity": 2,
}
```

### 3.5 Validation des relations (`validation.py`)

**Nouvelles contraintes domain/range** (dans core.yaml) :

```yaml
validation_rules:
  domain_range:
    HAS_STATE:
      from: [Character]
      to: [PsychologicalState]
    STATE_TRIGGERED_BY:
      from: [PsychologicalState]
      to: [Event]
    IN_SETTING:
      from: [Character, Event, Location, Object, Creature, Faction]
      to: [Setting]
    HAS_FEATURE:
      from: [Character]
      to: [CharacterFeature]
    PLAYS_ROLE:
      from: [Character]
      to: [NarrativeRole]
    INVOLVED_IN:
      from: [Character]
      to: [SocialRelationship]
    RELATIONSHIP_CAUSED_BY:
      from: [SocialRelationship]
      to: [Event]
```

### 3.6 Persistance Neo4j (`entity_repo.py`)

**Nouveaux handlers d'upsert** pour chaque type :

- `_upsert_psychological_states()` : MERGE sur (character + name + chapter_start)
- `_upsert_settings()` : MERGE sur (name + book_id)
- `_upsert_character_features()` : MERGE sur (character + name + book_id)
- `_upsert_narrative_roles()` : MERGE sur (character + role_type + book_id) avec valid_from/to
- `_upsert_social_relationships()` : MERGE sur (name + book_id), puis INVOLVED_IN edges

**Migration RELATES_TO → SocialRelationship** :

Script Cypher de migration pour le graphe existant :
```cypher
// Pour chaque edge RELATES_TO existant, creer un noeud SocialRelationship
MATCH (a:Character)-[r:RELATES_TO]->(b:Character)
WHERE r.book_id IS NOT NULL
CREATE (sr:SocialRelationship {
    name: a.canonical_name + " - " + b.canonical_name,
    relationship_type: coalesce(r.subtype, "relates_to"),
    book_id: r.book_id,
    valid_from_chapter: r.valid_from_chapter,
    description: coalesce(r.context, "")
})
CREATE (a)-[:INVOLVED_IN {role: "participant", valid_from_chapter: r.valid_from_chapter}]->(sr)
CREATE (b)-[:INVOLVED_IN {role: "participant", valid_from_chapter: r.valid_from_chapter}]->(sr)
DELETE r
```

### 3.7 Neo4j schema (`init_neo4j.cypher`)

**Nouvelles contraintes** :
```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (s:Setting) REQUIRE s.name IS NOT NULL;
CREATE CONSTRAINT IF NOT EXISTS FOR (ps:PsychologicalState) REQUIRE ps.name IS NOT NULL;
CREATE CONSTRAINT IF NOT EXISTS FOR (cf:CharacterFeature) REQUIRE cf.name IS NOT NULL;
CREATE CONSTRAINT IF NOT EXISTS FOR (nr:NarrativeRole) REQUIRE nr.role_type IS NOT NULL;
CREATE CONSTRAINT IF NOT EXISTS FOR (sr:SocialRelationship) REQUIRE sr.name IS NOT NULL;
```

**Nouveaux index fulltext** :
```cypher
CREATE FULLTEXT INDEX setting_fulltext IF NOT EXISTS FOR (s:Setting) ON EACH [s.name, s.description];
CREATE FULLTEXT INDEX social_rel_fulltext IF NOT EXISTS FOR (sr:SocialRelationship) ON EACH [sr.name, sr.description];
```

---

## 4. Impact sur le frontend

### 4.1 Graph Explorer

- **Nouvelles couleurs** dans `constants.ts` pour les 5 nouveaux types
- **SocialRelationship** apparait comme noeud intermediaire dans le graphe (pas comme edge direct). La visualisation doit gerer : Character → INVOLVED_IN → SocialRelationship → INVOLVED_IN → Character
- **Setting** comme noeud conteneur (peut etre visualise en arriere-plan ou comme cluster)

### 4.2 Review step

- La table des entites doit supporter les 5 nouveaux types
- La table des relations doit gerer INVOLVED_IN vers SocialRelationship
- Filtres par type mis a jour

### 4.3 Ontology viewer

- Le schema graph doit afficher les nouveaux types et relations
- Les tables entity/relation mises a jour

### 4.4 Chat RAG

- Les requetes hybrides (vector + graph) doivent traverser les nouveaux noeuds
- Exemple : "Comment la relation entre Jake et Casper evolue ?" → traverse SocialRelationship nodes avec valid_from/to

---

## 5. Impact sur les tests

### Tests a modifier

| Fichier test | Modification |
|-------------|-------------|
| `test_extraction_schemas_v4.py` | Ajouter tests pour les 5 nouveaux modeles Pydantic |
| `test_extraction_graph_v4.py` | Mock les nouveaux types dans le graph e2e |
| `test_entity_extraction.py` | Tester extraction de PsychologicalState, Setting, etc. |
| `test_verify_node.py` | Tester les nouvelles regles de verification |
| `test_reconciler_v4.py` | Tester le nouveau priority map avec les nouveaux types |
| `test_validation.py` | Tester les nouvelles contraintes domain/range |
| `test_consistency_checks.py` | Ajouter checks pour les nouveaux types |
| `test_book_level.py` | Tester clustering/summaries avec les nouveaux types |

### Tests a creer

| Nouveau fichier | Ce qu'il teste |
|----------------|---------------|
| `test_social_relationship_reification.py` | Migration RELATES_TO → SocialRelationship, INVOLVED_IN edges |
| `test_golem_alignment.py` | Verification que le schema WorldRAG est bien aligne avec GOLEM |

---

## 6. Plan de migration

### Phase A : Preparation (sans casser l'existant)

1. Creer le nouveau `core.yaml` GOLEM-aligned
2. Ajouter les 5 nouveaux modeles Pydantic
3. Ajouter les descriptions de types dans `entity_descriptions.yaml`
4. Ajouter les negative examples dans `few_shots.yaml`
5. Mettre a jour les validation rules
6. **Tester** : les anciens types continuent de fonctionner, les nouveaux sont extraits en plus

### Phase B : Migration des donnees existantes

1. Script Cypher de migration RELATES_TO → SocialRelationship
2. Renommer Item → Object dans le graphe existant
3. Renommer event_type → event_category sur les Event existants
4. Verifier l'integrite du graphe apres migration

### Phase C : Pipeline full (extraction complete)

1. Modifier entity_repo.py pour les nouveaux handlers d'upsert
2. Modifier le reconciler pour les nouveaux types
3. Modifier le verify node pour les nouvelles regles
4. Re-extraire le Primal Hunter complet avec le nouveau schema
5. Comparer la qualite avant/apres

### Phase D : Frontend

1. Ajouter couleurs et labels pour les nouveaux types
2. Adapter le graph explorer pour SocialRelationship comme noeud
3. Adapter le chat RAG pour les nouvelles traversees
4. Adapter l'ontology viewer

---

## 7. Ce qui ne change PAS

| Composant | Pourquoi il ne change pas |
|-----------|--------------------------|
| Couche 2 (genre) — `litrpg.yaml` | GOLEM ne couvre pas les game mechanics. Skill, Class, Level, Stat restent tels quels. |
| Couche 3 (serie) — `primal_hunter.yaml` | Idem — Bloodline, Profession sont serie-specifiques. |
| Induction ontologique | Le pattern_inducer continue de decouvrir des types supplementaires. |
| Regex Passe 0 | Les captures naives sont independantes de l'ontologie. |
| Chunking narratif | Independant du schema ontologique. |
| Deduplication 5-tier | Les mecanismes de dedup sont type-agnostiques. |
| EntityRegistry | Structure inchangee (canonical_name, entity_type, aliases). Supporte les nouveaux types nativement. |
| Embedding pipeline | Independant du schema (vectorise des textes, pas des types). |
| Architecture LangGraph | 6 noeuds identiques, contenu different dans les prompts. |

---

## 8. References

| Source | Utilisation |
|--------|-----------|
| GOLEM v1.1 (Pianzola et al., 2024) | Ontologie de reference pour la couche core |
| GOLEM GitHub — `GOLEM-lab/golem-ontology` | OWL source, documentation formelle |
| DOLCE-Lite-Plus (LOA, ISTC-CNR) | Upper ontology — categories fondamentales |
| CIDOC-CRM v7.3 (ISO 21127) | Modele evenement-temporel |
| LRMoo v1.0 (IFLA/CIDOC) | Hierarchie bibliographique (Work/Expression) |
| SEM (VU Amsterdam) | Modele evenementiel simple (Actor→Event→Place→Time) |
| Bamman et al. (2014) | Modele computationnel de personnage |

---

## 9. Criteres de succes

| Critere | Mesure |
|---------|--------|
| Aucune perte de fonctionnalite | Les 9 types actuels sont conserves ou enrichis. Aucune entite existante n'est perdue. |
| Alignement GOLEM verifiable | Chaque type core mappe a un type GOLEM avec reference dans le YAML. |
| Extraction des nouveaux types | PsychologicalState, Setting, CharacterFeature extraits sur le Primal Hunter. |
| Relations reifiees | SocialRelationship remplace RELATES_TO pour les relations Character↔Character. |
| Tests verts | 1069+ tests passent apres migration. |
| Qualite KG amelioree | Moins de "jake" comme Event, plus de structure narrative riche. |
| Documentation alignee | core.yaml documente la correspondance GOLEM pour chaque type. |
