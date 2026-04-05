"""Co-evolutionary pattern induction — joint ontology + regex discovery.

Runs naive structural captures on early chapters, then asks the LLM to
simultaneously discover entity types AND generate extraction patterns.
This replaces hardcoded genre-specific regex with auto-induced patterns.

References:
- Buitelaar et al. (2005): "On the Need to Bootstrap Ontology Learning
  with Extraction Grammar Learning" — theoretical argument, never built
- Snowball (Agichtein 2000): iterative pattern bootstrapping
- PATTY (Nakashole 2012): patterns organized by semantic types (reversed here)
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Naive structural capture patterns (domain-agnostic) ──────────────

NAIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("bracketed", re.compile(r"\[([^\[\]]{5,500})\]")),
    ("stat_gain", re.compile(r"^[+\-]\d+\s+.{2,50}$", re.MULTILINE)),
    ("progression", re.compile(r"\d+\s*(?:->|→|=>)\s*\d+")),
    (
        "labeled_value",
        re.compile(
            r"^(?:Level|Class|Title|Rank|Status|Skill|Race|Species|HP|MP|Mana|"
            r"Stamina|Strength|Agility|Perception|Vitality|Willpower|Wisdom|"
            r"Toughness|Endurance|Intelligence|Luck|Charisma|Dexterity)"
            r":\s*.+$",
            re.MULTILINE,
        ),
    ),
]


# ── Pydantic response models ────────────────────────────────────────


class InducedRegexPattern(BaseModel):
    """A regex pattern discovered by the LLM from text examples."""

    name: str = Field(description="snake_case pattern name, e.g. 'skill_acquired'")
    description: str = Field(default="", description="What this pattern detects")
    entity_type: str = Field(description="Entity type this pattern extracts, e.g. 'Skill'")
    regex: str = Field(
        description="Python regex with named capture groups, e.g. r'\\[Skill.*?: (?P<name>.+?)\\]'"
    )
    example_matches: list[str] = Field(
        default_factory=list,
        description="2-5 example strings from the text that this regex should match",
    )


class InducedEntityType(BaseModel):
    """An entity type discovered from text (same as ontology_inducer)."""

    name: str = Field(description="PascalCase entity type name")
    description: str = Field(default="", description="What this type represents")
    parent_type: str | None = Field(
        default=None,
        description="If this type is a specialization of an existing type, the parent type name",
    )
    example_instances: list[str] = Field(default_factory=list)
    properties: list[str] = Field(default_factory=list)


class InducedRelationType(BaseModel):
    """A relation type discovered from text."""

    name: str = Field(description="UPPER_SNAKE_CASE relation name")
    source_type: str = Field(description="Source entity type")
    target_type: str = Field(description="Target entity type")
    description: str = Field(default="", description="What this relation represents")


class JointInductionResult(BaseModel):
    """Combined result of joint ontology + pattern induction."""

    entity_types: list[InducedEntityType] = Field(default_factory=list)
    relation_types: list[InducedRelationType] = Field(default_factory=list)
    regex_patterns: list[InducedRegexPattern] = Field(default_factory=list)


# ── Constants ────────────────────────────────────────────────────────

_MAX_SAMPLE_CHARS = 30_000
_MAX_CHAPTERS = 3
_MAX_CAPTURES = 80  # Max naive captures to send to LLM

_SYSTEM_PROMPT = """\
You are an expert in knowledge graph schema design and text pattern analysis for fiction novels.

You will receive:
1. Raw text from the first chapters of a novel
2. A list of "structural captures" — text fragments that appear to be formatted/structured \
(bracketed notifications, stat blocks, progression markers, etc.)

Your job is to SIMULTANEOUSLY:

## A. Discover entity types
Identify entity types that are important in this story. Use PascalCase names.
Focus on types that appear repeatedly and are structurally important to the world-building.

## B. Discover relation types
Identify relationship types between entities. Use UPPER_SNAKE_CASE names.

## C. Generate extraction patterns (regex)
For each structural pattern you see in the captures, generate a Python regex with NAMED \
capture groups that extracts the key information.

Rules for regex:
- Use Python re syntax with named groups: (?P<name>...)
- Use re.IGNORECASE flag (patterns will be compiled case-insensitive)
- Keep patterns specific enough to avoid false positives
- Include 2-5 example strings that the regex should match
- The regex must be a valid Python regex string

## Existing ontology types (DO NOT rediscover these)

### Entity types already defined (with descriptions):
{existing_entity_types}

### Relationship types already defined:
{existing_relation_types}

## Instructions
1. Analyze the structural captures to understand the notification/system patterns in this novel
2. Group similar captures and generate ONE regex per group
3. Also identify entity and relation types not covered by the existing ontology
4. Be conservative — only propose types and patterns that appear multiple times
5. If a discovered type is a SPECIALIZATION of an existing type, set parent_type to the \
existing type's name (e.g. a "SkillEmotion" is a specialization of "PsychologicalState")
"""


# ── Public API ───────────────────────────────────────────────────────


def naive_structural_capture(text: str) -> list[dict[str, Any]]:
    """Run domain-agnostic regex to capture all structured text fragments.

    Returns list of dicts with 'text', 'pattern_type', 'start', 'end'.
    """
    captures: list[dict[str, Any]] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern_name, pattern in NAIVE_PATTERNS:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            # Skip overlapping captures
            if any(s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1] for s in seen_spans):
                continue
            seen_spans.add(span)
            captures.append(
                {
                    "text": match.group(0).strip(),
                    "pattern_type": pattern_name,
                    "start": span[0],
                    "end": span[1],
                }
            )

    # Sort by position
    captures.sort(key=lambda c: c["start"])

    logger.info(
        "naive_capture_completed",
        total_captures=len(captures),
        by_type={
            pt: sum(1 for c in captures if c["pattern_type"] == pt)
            for pt in {c["pattern_type"] for c in captures}
        },
    )

    return captures


_SEMANTIC_SIMILARITY_THRESHOLD = 0.85


def _filter_semantic_duplicates(
    proposed: list[InducedEntityType],
    existing_context: list[dict[str, str]],
) -> list[InducedEntityType]:
    """Filter proposed types that are semantically too similar to existing GOLEM types.

    Uses sentence-transformers cosine similarity with BGE-m3. Falls back to
    keeping all types if embeddings are unavailable.
    """
    try:
        from sentence_transformers import SentenceTransformer, util as st_util

        model = SentenceTransformer("BAAI/bge-m3")
    except Exception:
        logger.warning("semantic_filter_unavailable", reason="sentence-transformers not loaded")
        return proposed

    # Build text representations
    existing_texts = [f"{entry['name']}: {entry['description']}" for entry in existing_context]
    existing_embeddings = model.encode(existing_texts, convert_to_tensor=True)

    filtered: list[InducedEntityType] = []
    for et in proposed:
        proposed_text = f"{et.name}: {et.description}"
        proposed_embedding = model.encode(proposed_text, convert_to_tensor=True)
        similarities = st_util.cos_sim(proposed_embedding, existing_embeddings)[0]
        max_sim = float(similarities.max())
        best_match_idx = int(similarities.argmax())

        if max_sim >= _SEMANTIC_SIMILARITY_THRESHOLD:
            # Map to existing type as parent instead of creating duplicate
            parent_name = existing_context[best_match_idx]["name"]
            if et.parent_type is None:
                et.parent_type = parent_name
            logger.info(
                "semantic_duplicate_detected",
                proposed=et.name,
                existing=parent_name,
                similarity=round(max_sim, 3),
                action="set_parent_type",
            )
            filtered.append(et)
        else:
            filtered.append(et)

    return filtered


async def induce_patterns_and_ontology(
    chapters_text: list[str],
    existing_ontology: Any,  # OntologyLoader
    model_override: str | None = None,
) -> dict[str, Any]:
    """Joint induction of entity types, relation types, AND regex patterns.

    Replaces the separate ontology_inducer. Runs naive structural captures
    on the first 3 chapters, then asks the LLM to simultaneously discover
    types and patterns.

    Args:
        chapters_text: List of chapter text strings.
        existing_ontology: Currently loaded OntologyLoader.
        model_override: Optional 'provider:model' override.

    Returns:
        Dict compatible with OntologyLoader.extend_with_induced() plus
        a "regex_patterns" key with validated patterns.
    """
    from app.llm.providers import get_instructor_for_extraction

    # 1. Build sample text
    sample_chapters = chapters_text[:_MAX_CHAPTERS]
    sample_text = "\n\n---\n\n".join(sample_chapters)
    if len(sample_text) > _MAX_SAMPLE_CHARS:
        sample_text = sample_text[:_MAX_SAMPLE_CHARS]

    # 2. Run naive structural captures
    captures = naive_structural_capture(sample_text)

    # Deduplicate similar captures (keep unique text)
    unique_texts = list(dict.fromkeys(c["text"] for c in captures))
    capture_list = unique_texts[:_MAX_CAPTURES]

    if not capture_list:
        logger.info("no_structural_captures_found", chapters=len(sample_chapters))
        # Fall through — LLM can still induce entity/relation types from text

    # 3. Build existing ontology context (with descriptions for GOLEM-awareness)
    existing_entity_names = sorted(existing_ontology.get_node_type_names())
    existing_relation_names = sorted(existing_ontology.get_relationship_type_names())

    # Use descriptions so the LLM understands semantic coverage (§6ter.2)
    induction_context = existing_ontology.to_induction_context()
    if induction_context:
        entity_types_str = "\n".join(
            f"- {entry['name']}: {entry['description']}" for entry in induction_context
        )
    else:
        entity_types_str = ", ".join(existing_entity_names) if existing_entity_names else "(none)"
    relation_types_str = ", ".join(existing_relation_names) if existing_relation_names else "(none)"
    system_prompt = _SYSTEM_PROMPT.format(
        existing_entity_types=entity_types_str,
        existing_relation_types=relation_types_str,
    )

    # 4. Build user message
    captures_section = ""
    if capture_list:
        captures_section = (
            "## Structural captures found in the text:\n\n"
            + "\n".join(f"- `{c}`" for c in capture_list)
            + "\n\n"
        )

    user_message = (
        f"{captures_section}## Novel text (first {len(sample_chapters)} chapters):\n\n{sample_text}"
    )

    # 5. Call LLM
    client, model = get_instructor_for_extraction(model_override)

    logger.info(
        "joint_induction_started",
        sample_chapters=len(sample_chapters),
        sample_chars=len(sample_text),
        structural_captures=len(capture_list),
        existing_entity_types=len(existing_entity_names),
        existing_relation_types=len(existing_relation_names),
        model=model,
    )

    result: JointInductionResult = await client.chat.completions.create(
        model=model,
        response_model=JointInductionResult,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_retries=2,
    )

    # 6. Filter out rediscovered types (lexical)
    existing_entity_set = {n.lower() for n in existing_entity_names}
    existing_relation_set = {n.lower() for n in existing_relation_names}

    new_entity_types = [
        et for et in result.entity_types if et.name.lower() not in existing_entity_set
    ]
    new_relation_types = [
        rt for rt in result.relation_types if rt.name.lower() not in existing_relation_set
    ]

    # 6b. Semantic similarity filter (§6ter.2) — catch semantic duplicates
    # like "EmotionalState" vs "PsychologicalState" that lexical filter misses
    if new_entity_types and induction_context:
        new_entity_types = _filter_semantic_duplicates(new_entity_types, induction_context)

    # 7. Validate induced regex patterns
    validated_patterns = _validate_induced_patterns(result.regex_patterns)

    logger.info(
        "joint_induction_completed",
        induced_entity_types=[et.name for et in new_entity_types],
        induced_relation_types=[rt.name for rt in new_relation_types],
        induced_patterns_raw=len(result.regex_patterns),
        induced_patterns_validated=len(validated_patterns),
        rejected_patterns=[
            p.name
            for p in result.regex_patterns
            if p.name not in {v["name"] for v in validated_patterns}
        ],
    )

    return {
        "node_types": [
            {
                "name": et.name,
                "description": et.description,
                "parent_type": et.parent_type,
                "example_instances": et.example_instances,
                "properties": et.properties,
            }
            for et in new_entity_types
        ],
        "relationship_types": [
            {
                "name": rt.name,
                "source_type": rt.source_type,
                "target_type": rt.target_type,
                "description": rt.description,
            }
            for rt in new_relation_types
        ],
        "regex_patterns": validated_patterns,
    }


def _validate_induced_patterns(
    patterns: list[InducedRegexPattern],
) -> list[dict[str, Any]]:
    """Validate and compile LLM-generated regex patterns.

    A pattern is accepted if:
    1. It compiles without error
    2. It matches at least 80% of its own example_matches
    3. It has at least 1 example match

    Returns list of validated pattern dicts ready for RegexExtractor.
    """
    validated: list[dict[str, Any]] = []

    for pattern in patterns:
        if not pattern.example_matches:
            logger.debug("pattern_rejected_no_examples", name=pattern.name)
            continue

        try:
            compiled = re.compile(pattern.regex, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            logger.debug(
                "pattern_rejected_invalid_regex",
                name=pattern.name,
                regex=pattern.regex,
                error=str(e),
            )
            continue

        # Check matches against examples
        hits = sum(1 for ex in pattern.example_matches if compiled.search(ex))
        match_rate = hits / len(pattern.example_matches)

        if match_rate < 0.8:
            logger.debug(
                "pattern_rejected_low_match_rate",
                name=pattern.name,
                match_rate=match_rate,
                hits=hits,
                total=len(pattern.example_matches),
            )
            continue

        # Extract named capture groups
        capture_names = list(compiled.groupindex.keys())

        validated.append(
            {
                "name": pattern.name,
                "pattern": pattern.regex,
                "entity_type": pattern.entity_type,
                "captures": {name: idx for name, idx in compiled.groupindex.items()},
                "description": pattern.description,
                "example_matches": pattern.example_matches,
            }
        )

        logger.info(
            "pattern_validated",
            name=pattern.name,
            entity_type=pattern.entity_type,
            match_rate=match_rate,
            capture_groups=capture_names,
        )

    return validated
