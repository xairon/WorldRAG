"""V3 prompt base template with ontology-driven schema injection.

Every extraction prompt follows a 4-part structure:
[SYSTEM] Role + language + ontology schema
[CONTRAINTES] Extraction rules
[CONTEXTE] Entity registry + previous summary + Phase 0 hints
[EXEMPLES] Few-shot examples
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptLanguage:
    """Language configuration for prompts."""

    code: str
    role_prefix: str
    constraint_label: str
    context_label: str
    examples_label: str
    text_label: str


LANG_FR = PromptLanguage(
    code="fr",
    role_prefix="Tu es",
    constraint_label="CONTRAINTES",
    context_label="CONTEXTE",
    examples_label="EXEMPLES",
    text_label="TEXTE \u00c0 ANALYSER",
)

LANG_EN = PromptLanguage(
    code="en",
    role_prefix="You are",
    constraint_label="CONSTRAINTS",
    context_label="CONTEXT",
    examples_label="EXAMPLES",
    text_label="TEXT TO ANALYZE",
)

_LANGUAGES = {"fr": LANG_FR, "en": LANG_EN}


def get_language_config(language: str = "fr") -> PromptLanguage:
    """Get language configuration. Defaults to French."""
    return _LANGUAGES.get(language, LANG_FR)


def build_extraction_prompt(
    *,
    phase: str | int,
    role_description: str,
    ontology_schema: dict,
    task_instructions: str = "",
    entity_registry_context: str = "",
    previous_summary: str = "",
    phase0_hints: list[dict] | None = None,
    router_hints: list[str] | None = None,
    extracted_entities_json: str | None = None,
    few_shot_examples: str = "",
    negative_examples: str = "",
    language: str = "fr",
    split_for_caching: bool = False,
) -> str | tuple[str, str]:
    """Build a complete extraction prompt with ontology injection.

    Args:
        phase: Extraction phase number or name (e.g. 0-5, "entities", "relations").
        role_description: Role description for the LLM.
        ontology_schema: JSON-serializable dict of target entity types.
        task_instructions: Optional free-form instructions injected after [SYSTEM].
        entity_registry_context: String of known entities for context.
        previous_summary: Summary of previous chapters.
        phase0_hints: Regex-extracted hints from Phase 0.
        router_hints: Optional focus hints injected as [FOCUS] section after [CONTRAINTES].
        extracted_entities_json: JSON string of already-extracted entities (for relation phase).
        few_shot_examples: Formatted few-shot examples string.
        negative_examples: Formatted negative examples string (what NOT to extract).
        language: Prompt language code ('fr' or 'en').
        split_for_caching: If True, return (static_system, dynamic_context) tuple
            where static_system is identical across chapters (cacheable by Gemini)
            and dynamic_context contains registry/hints/chapter-specific data.

    Returns:
        Complete prompt string, or (static_system, dynamic_context) if split_for_caching.
    """
    lang = get_language_config(language)
    schema_json = json.dumps(ontology_schema, ensure_ascii=False, indent=2)

    sections: list[str] = []

    # [SYSTEM]
    sections.append(f"[SYSTEM]\n{lang.role_prefix} {role_description}.")
    sections.append(
        f"Phase d'extraction: {phase}" if language == "fr" else f"Extraction phase: {phase}"
    )
    sections.append(
        f"Ontologie cible:\n```json\n{schema_json}\n```"
        if language == "fr"
        else f"Target ontology:\n```json\n{schema_json}\n```"
    )

    # [TÂCHE] — optional free-form task instructions
    if task_instructions:
        label = "TÂCHE" if language == "fr" else "TASK"
        sections.append(f"\n[{label}]\n{task_instructions}")

    # [CONTRAINTES]
    sections.append(f"\n[{lang.constraint_label}]")
    if language == "fr":
        sections.append(
            "- Avant de lister les entités, raisonner brièvement (dans le champ 'reasoning') "
            "sur les entités clés, événements et relations présents dans le texte"
        )
        sections.append(
            "- Extraire UNIQUEMENT les types d'entit\u00e9s list\u00e9s dans l'ontologie cible"
        )
        sections.append(
            "- Les types entity_type de base sont : character, event, location, object, "
            "creature, faction, concept, narrative_sequence, prophecy, level_change, stat_change, "
            "psychological_state, setting, character_feature, narrative_role, social_relationship. "
            "Pour tout type spécialisé (skill, class, title, system, bloodline, profession, "
            "achievement, race, quest, ou tout type découvert par l'ontologie), "
            "utiliser entity_type='genre_entity' avec le type spécifique dans sub_type."
        )
        sections.append(
            "- Chaque entit\u00e9 DOIT avoir un ancrage textuel (extraction_text) "
            "correspondant EXACTEMENT au texte source"
        )
        sections.append(
            "- Attribuer un score de confiance (0.0 \u00e0 1.0) pour chaque entit\u00e9 extraite"
        )
        sections.append("- NE PAS inventer d'informations absentes du texte")
        sections.append(
            "- NE PAS traduire les noms propres, les conserver tels quels dans le texte source"
        )
        sections.append("- Utiliser le canonical_name en minuscules, sans articles (le/la/les/the)")
        sections.append(
            "- Les entités CHARACTER doivent avoir un nom propre — NE PAS extraire les "
            "descriptions de rôle génériques ('le guerrier', 'le mage', 'vieil homme') "
            "comme personnages. Seuls les individus nommés sont acceptés."
        )
        sections.append(
            "- Si une entité du Registre d'entités connues correspond au personnage "
            "décrit, utiliser le MÊME canonical_name du registre et lister les nouvelles "
            "variantes de nom dans aliases. NE PAS créer de doublons."
        )
    else:
        sections.append(
            "- Before listing entities, briefly reason (in the 'reasoning' field) "
            "about what key entities, events, and relationships are present in the text"
        )
        sections.append("- Extract ONLY entity types listed in the target ontology")
        sections.append(
            "- Base entity_type values: character, event, location, object, "
            "creature, faction, concept, narrative_sequence, prophecy, level_change, stat_change, "
            "psychological_state, setting, character_feature, narrative_role, social_relationship. "
            "For any specialized type (skill, class, title, system, bloodline, profession, "
            "achievement, race, quest, or any ontology-discovered type), "
            "use entity_type='genre_entity' with the specific type in sub_type."
        )
        sections.append("- Each entity MUST have extraction_text matching the source text EXACTLY")
        sections.append("- Assign a confidence score (0.0 to 1.0) for each extracted entity")
        sections.append("- Do NOT invent information absent from the text")
        sections.append("- Do NOT translate proper nouns — keep them as-is from source text")
        sections.append("- Use canonical_name in lowercase, without articles (the/a/an)")
        sections.append(
            "- CHARACTER entities MUST have a proper name — do NOT extract generic role "
            "descriptions ('the warrior', 'the caster', 'old man', 'heavy warrior', 'a scout') "
            "as characters. Only named individuals qualify."
        )
        sections.append(
            "- If an entity from the Known entity registry already matches the character "
            "being described, use the SAME canonical_name from the registry and list any "
            "new name variants in aliases. Do NOT create duplicate entities."
        )

    # [EXEMPLES] — static, goes before dynamic context
    if few_shot_examples:
        sections.append(f"\n[{lang.examples_label}]\n{few_shot_examples}")

    # [NEGATIVE EXAMPLES] — static
    if negative_examples:
        neg_label = "CONTRE-EXEMPLES" if language == "fr" else "NEGATIVE EXAMPLES"
        sections.append(f"\n[{neg_label}]\n{negative_examples}")

    # ── Split point: everything above is static (cacheable by Gemini) ──
    # Everything below is dynamic (changes per chapter).
    dynamic_sections: list[str] = []

    # [FOCUS] — optional router hints (dynamic per chapter)
    if router_hints:
        hints_lines = "\n".join(f"- {h}" for h in router_hints)
        dynamic_sections.append(f"\n[FOCUS]\n{hints_lines}")

    # [ENTITÉS EXTRAITES] — optional previously extracted entities (relation phase)
    if extracted_entities_json:
        label = "ENTITÉS EXTRAITES" if language == "fr" else "EXTRACTED ENTITIES"
        dynamic_sections.append(f"\n[{label}]\n{extracted_entities_json}")

    # [CONTEXTE] — dynamic (registry grows per chapter, hints differ)
    has_context = entity_registry_context or previous_summary or phase0_hints
    if has_context:
        dynamic_sections.append(f"\n[{lang.context_label}]")
        if entity_registry_context:
            label = (
                "Registre d'entit\u00e9s connues" if language == "fr" else "Known entity registry"
            )
            dynamic_sections.append(f"{label}:\n{entity_registry_context}")
        if previous_summary:
            label = (
                "R\u00e9sum\u00e9 des chapitres pr\u00e9c\u00e9dents"
                if language == "fr"
                else "Previous chapters summary"
            )
            dynamic_sections.append(f"\n{label}:\n{previous_summary}")
        if phase0_hints:
            label = "Indices Phase 0 (regex)" if language == "fr" else "Phase 0 hints (regex)"
            hints_json = json.dumps(phase0_hints, ensure_ascii=False)
            dynamic_sections.append(f"\n{label}:\n{hints_json}")

    if split_for_caching:
        static_system = "\n".join(sections)
        dynamic_context = "\n".join(dynamic_sections)
        return static_system, dynamic_context

    # Default: concatenate everything into a single prompt string
    return "\n".join(sections + dynamic_sections)
