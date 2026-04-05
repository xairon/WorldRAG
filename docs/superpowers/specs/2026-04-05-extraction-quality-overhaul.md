# Extraction Pipeline Quality Overhaul — SOTA Alignment

## Context

Audit of the V4 extraction pipeline reveals 8 compounding failures causing severe KG quality degradation:
- Character "Jake" fragmented into 100+ nodes across Event, Arc, Concept, GenreEntity, Item, StateChange
- Level-ups extracted as Events instead of level_change entities
- Generic game mechanics (stamina, mana, free points) as standalone Concepts
- No cross-type deduplication in reconciler
- Weak verify node (doesn't catch type mismatches)
- Schema coercer silently masks hallucinations

## SOTA Techniques Applied

Based on KGGen (Microsoft/Stanford 2024), GraphRAG (Microsoft 2024), and computational narratology literature:

1. **Negative examples** — domain-specific counter-examples reduce hallucination 40-60%
2. **Type rationale field** — forces LLM to reason about type before committing
3. **Continuation context** — known entities injected into prompt prevent re-extraction as wrong types
4. **Relation type constraints** — validate source/target types against ontology rules
5. **Cross-type dedup** — detect same name with different entity types
6. **Post-extraction faithfulness check** — batch NLI verification
7. **Graph-level consistency** — Cypher queries to detect orphans, self-loops, type violations

---

## Phase 1: Prompt & Schema Hardening (immediate)

### 1.1 Add negative examples to extraction prompts

**File:** `backend/app/prompts/extraction_unified.py` (or YAML templates)

Add to entity extraction prompt:

```
DO NOT extract:
- Character names as Events. "Jake levels to 24" is a level_change, NOT an Event.
  WRONG: {"entity_type": "event", "name": "jake levels to 24"}
  RIGHT: {"entity_type": "level_change", "character": "jake", "new_level": 24}

- Character names as Concepts/Items/Arcs.
  WRONG: {"entity_type": "concept", "name": "jake"}
  RIGHT: Already extracted as Character, do not duplicate.

- Game mechanics as Concepts. Stamina, mana, HP, free points, XP are SYSTEM properties.
  WRONG: {"entity_type": "concept", "name": "stamina"}
  RIGHT: Do not extract — these are attributes of the game system, not narrative concepts.

- Single character actions as Events. One character doing one thing is NOT an Event.
  WRONG: {"entity_type": "event", "name": "jake shoots arrow"}
  RIGHT: Not an entity at all, or captured as a relation (jake -[USES]-> bow).
  Events are world-level happenings: battles, discoveries, system announcements.
```

### 1.2 Add type rationale field to Pydantic models

**File:** `backend/app/schemas/extraction_v4.py`

Add `type_rationale` field to EntityExtractionResult:

```python
class EntityExtractionResult(BaseModel):
    reasoning: str = ""
    entities: list[EntityUnion] = Field(default_factory=list)
    chapter_number: int = 0
```

Add to each entity base:

```python
# In each entity model (ExtractedCharacter, ExtractedEvent, etc.)
type_rationale: str = Field(
    default="",
    description="One sentence: WHY is this entity this type and not another?"
)
```

This forces the LLM to articulate why "jake" is a character and not an event.

### 1.3 Change schema coercer: reject instead of silently coerce

**File:** `backend/app/schemas/extraction_v4.py` (model_validator)

Current behavior: unknown `entity_type` → silently converted to `genre_entity`.
New behavior: log warning and **drop** the entity from the list (don't create garbage).

```python
@model_validator(mode="before")
@classmethod
def coerce_unknown_entity_types(cls, data: Any) -> Any:
    if isinstance(data, dict) and "entities" in data:
        valid = []
        for entity in data.get("entities", []):
            if isinstance(entity, dict):
                et = entity.get("entity_type", "")
                if et in _VALID_ENTITY_TYPES:
                    valid.append(entity)
                else:
                    # Drop invalid types instead of coercing
                    logger.warning("entity_dropped_invalid_type",
                                   name=entity.get("name", "?"),
                                   invalid_type=et)
        data["entities"] = valid
    return data
```

### 1.4 Strengthen registry context injection

**File:** `backend/app/services/extraction/entity_registry.py`

Enhance `to_prompt_context()` to add explicit type constraints:

```python
def to_prompt_context(self, max_tokens: int = 2000) -> str:
    lines = []
    # ... existing entity listing ...
    
    # Add type constraint block
    lines.append("\n## TYPE CONSTRAINTS — Do NOT re-extract these as other types:")
    for entry in self._entities.values():
        if entry.significance in ("protagonist", "major"):
            lines.append(
                f"- '{entry.canonical_name}' is a {entry.entity_type}. "
                f"Do NOT extract as Event, Concept, Item, or any other type."
            )
    return "\n".join(lines)
```

---

## Phase 2: Verify Node + Reconciler Hardening

### 2.1 Add type mismatch checks to verify node

**File:** `backend/app/services/extraction/verify.py`

New checks in `_verify_single_entity()`:

```python
_GENERIC_MECHANICS = frozenset({
    "stamina", "mana", "health", "hp", "mp", "free points",
    "skill points", "experience", "xp", "level", "attribute",
    "stat", "stat points", "agility", "strength", "perception",
    "vitality", "willpower", "wisdom", "toughness", "endurance",
})

def _verify_single_entity(entity, chapter_text_lower, chapter_text,
                          known_character_names=None):
    # ... existing checks ...
    
    # NEW Check: Events should not use character names
    if entity_type == "event" and known_character_names:
        if name_lower in known_character_names:
            return False, f"event_named_after_character:{name}"
        # Also check if name STARTS with a character name
        for char_name in known_character_names:
            if name_lower.startswith(char_name + " "):
                return False, f"event_starts_with_character:{name}"
    
    # NEW Check: Generic game mechanics should not be concepts
    if entity_type in ("concept", "genre_entity") and name_lower in _GENERIC_MECHANICS:
        return False, f"generic_mechanic_as_entity:{name}"
    
    # NEW Check: Same name as known character but different type
    if known_character_names and name_lower in known_character_names:
        if entity_type != "character":
            return False, f"known_character_wrong_type:{name}:{entity_type}"
```

Update `verify_extractions_node()` to pass known character names from registry.

### 2.2 Cross-type dedup in reconciler

**File:** `backend/app/services/extraction/reconciler.py`

Add a pre-dedup pass before the per-type grouping:

```python
async def reconcile_flat_entities(entities, client=None, model=""):
    # NEW: Cross-type dedup pass
    by_name: dict[str, list[dict]] = {}
    for e in entities:
        name = (_get_name_from_flat_entity(e) or "").lower().strip()
        if name:
            by_name.setdefault(name, []).append(e)
    
    # For names with multiple types: keep the highest-priority type
    TYPE_PRIORITY = {
        "character": 10, "location": 9, "skill": 8, "class": 8,
        "item": 7, "creature": 7, "faction": 7, "event": 5,
        "concept": 3, "genre_entity": 2, "arc": 4, "prophecy": 4,
        "level_change": 6, "stat_change": 6,
    }
    
    deduped = []
    for name, ents in by_name.items():
        types = {e.get("entity_type") for e in ents}
        if len(types) > 1:
            # Same name, multiple types — keep highest priority
            best = max(ents, key=lambda e: TYPE_PRIORITY.get(e.get("entity_type", ""), 0))
            deduped.append(best)
            logger.info("cross_type_dedup",
                        name=name, types=list(types),
                        kept_type=best.get("entity_type"))
        else:
            deduped.extend(ents)
    
    entities = deduped
    # ... continue with existing per-type dedup ...
```

### 2.3 Relation type constraint validation

**File:** `backend/app/services/extraction/relations.py` (or new `validation.py`)

Add post-extraction relation validation:

```python
RELATION_TYPE_CONSTRAINTS = {
    "HAS_SKILL": ({"character"}, {"genre_entity", "skill"}),
    "HAS_CLASS": ({"character"}, {"genre_entity", "class"}),
    "LOCATED_AT": ({"character", "item", "event", "creature"}, {"location"}),
    "MEMBER_OF": ({"character"}, {"faction"}),
    "PARTICIPATES_IN": ({"character"}, {"event"}),
    "HAS_TITLE": ({"character"}, {"genre_entity", "title"}),
}

def validate_relation(relation, entity_map):
    """Validate source/target types match expected constraints."""
    rel_type = relation.get("relation_type", "")
    if rel_type not in RELATION_TYPE_CONSTRAINTS:
        return True  # No constraint defined, allow
    
    expected_src, expected_tgt = RELATION_TYPE_CONSTRAINTS[rel_type]
    src = entity_map.get(relation.get("source", "").lower())
    tgt = entity_map.get(relation.get("target", "").lower())
    
    if src and src.get("entity_type") not in expected_src:
        return False
    if tgt and tgt.get("entity_type") not in expected_tgt:
        return False
    return True
```

---

## Phase 3: Post-Extraction Quality Gates

### 3.1 Batch faithfulness verification

New LangGraph node after reconcile, before persist. Batch-verify entities against source text:

```python
async def batch_verify_faithfulness(entities, chapter_text, client, model):
    """Verify entities are grounded in source text via batch NLI."""
    entity_list = "\n".join(
        f"{i+1}. {e.get('name')} ({e.get('entity_type')}): {e.get('extraction_text', 'N/A')}"
        for i, e in enumerate(entities)
    )
    
    result = await client.chat.completions.create(
        response_model=FaithfulnessResult,
        messages=[{
            "role": "user",
            "content": f"""Source text:
{chapter_text[:3000]}

Extracted entities:
{entity_list}

For each entity, is it actually mentioned or clearly implied in the source text?
Return the index numbers of entities that are NOT grounded (hallucinated)."""
        }]
    )
    
    # Remove ungrounded entities
    hallucinated_indices = set(result.ungrounded_indices)
    return [e for i, e in enumerate(entities) if i not in hallucinated_indices]
```

### 3.2 Graph-level consistency checks (post-processing)

**File:** `backend/app/services/extraction/book_level.py` (add new function)

Run after all chapters extracted, as part of book-level post-processing:

```python
async def run_consistency_checks(driver, book_id):
    """Run graph-level quality checks and return issues."""
    checks = []
    async with driver.session() as session:
        # 1. Orphan entities (no relations except MENTIONED_IN)
        result = await session.run("""
            MATCH (e {book_id: $book_id})
            WHERE NOT 'Chapter' IN labels(e) AND NOT 'Book' IN labels(e)
              AND NOT 'Chunk' IN labels(e) AND NOT 'Paragraph' IN labels(e)
              AND NOT 'Community' IN labels(e) AND NOT 'StateChange' IN labels(e)
            OPTIONAL MATCH (e)-[r]-()
            WHERE NOT type(r) IN ['MENTIONED_IN', 'FIRST_MENTIONED_IN', 'BELONGS_TO_COMMUNITY']
            WITH e, count(r) AS rel_count
            WHERE rel_count = 0
            RETURN e.name AS name, labels(e)[0] AS label, e.canonical_name AS canonical
        """, {"book_id": book_id})
        orphans = [r async for r in result]
        if orphans:
            checks.append({"type": "orphan_entities", "count": len(orphans),
                          "entities": [o["name"] for o in orphans[:20]]})
        
        # 2. Type violations in relations
        result = await session.run("""
            MATCH (a {book_id: $book_id})-[r:HAS_SKILL]->(b)
            WHERE NOT 'Skill' IN labels(b) AND NOT 'GenreEntity' IN labels(b)
            RETURN a.name AS source, type(r) AS rel, b.name AS target, labels(b) AS labels
            LIMIT 20
        """, {"book_id": book_id})
        violations = [r async for r in result]
        if violations:
            checks.append({"type": "relation_type_violations", "count": len(violations),
                          "examples": [{"source": v["source"], "rel": v["rel"],
                                       "target": v["target"]} for v in violations]})
        
        # 3. Duplicate names across types
        result = await session.run("""
            MATCH (e {book_id: $book_id})
            WHERE e.canonical_name IS NOT NULL
            WITH e.canonical_name AS name, collect(DISTINCT labels(e)[0]) AS types
            WHERE size(types) > 1
            RETURN name, types
        """, {"book_id": book_id})
        dupes = [r async for r in result]
        if dupes:
            checks.append({"type": "cross_type_duplicates", "count": len(dupes),
                          "entities": [{"name": d["name"], "types": d["types"]} for d in dupes]})
    
    return checks
```

Expose via API: `GET /admin/quality-checks/{book_id}`.

---

## Files Modified / Created

### Modified
| File | Changes |
|------|---------|
| `backend/app/prompts/extraction_unified.py` | Add negative examples block |
| `backend/app/schemas/extraction_v4.py` | Add `type_rationale` field, change coercer to drop invalid types |
| `backend/app/services/extraction/entity_registry.py` | Enhance `to_prompt_context()` with type constraints |
| `backend/app/services/extraction/verify.py` | Add type mismatch checks, game mechanic filter, character name collision |
| `backend/app/services/extraction/reconciler.py` | Add cross-type dedup pre-pass |
| `backend/app/services/extraction/relations.py` | Add relation type constraint validation |
| `backend/app/services/extraction/book_level.py` | Add `run_consistency_checks()` |
| `backend/app/services/extraction/__init__.py` | Wire verify node to pass known character names |

### Created
| File | Purpose |
|------|---------|
| `backend/app/services/extraction/validation.py` | Relation type constraints, faithfulness batch check |
| `backend/app/api/routes/admin.py` | Quality checks endpoint |
| `backend/tests/services/extraction/test_quality_checks.py` | Tests for all new validation logic |

### Not Changed (already correct)
- `entity_repo.py` — relation MERGE fix already applied
- `mention_detector.py` — working correctly
- `grounding.py` — working correctly

---

## Out of Scope (future phases)

- Proposition decomposition (KGGen-style) — requires extra LLM call per chunk
- Self-consistency voting (3x extraction) — too expensive for all chapters
- Advanced iterative clustering with connected components — current clustering is sufficient
- Temporal state snapshots — already partially implemented via StateChange nodes
