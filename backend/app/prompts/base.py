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
    phase: int,
    role_description: str,
    ontology_schema: dict,
    entity_registry_context: str = "",
    previous_summary: str = "",
    phase0_hints: list[dict] | None = None,
    few_shot_examples: str = "",
    language: str = "fr",
) -> str:
    """Build a complete extraction prompt with ontology injection.

    Args:
        phase: Extraction phase number (0-5).
        role_description: Role description for the LLM.
        ontology_schema: JSON-serializable dict of target entity types.
        entity_registry_context: String of known entities for context.
        previous_summary: Summary of previous chapters.
        phase0_hints: Regex-extracted hints from Phase 0.
        few_shot_examples: Formatted few-shot examples string.
        language: Prompt language code ('fr' or 'en').

    Returns:
        Complete prompt string.
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

    # [CONTRAINTES]
    sections.append(f"\n[{lang.constraint_label}]")
    if language == "fr":
        sections.append(
            "- Extraire UNIQUEMENT les types d'entit\u00e9s list\u00e9s dans l'ontologie cible"
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
    else:
        sections.append("- Extract ONLY entity types listed in the target ontology")
        sections.append("- Each entity MUST have extraction_text matching the source text EXACTLY")
        sections.append("- Assign a confidence score (0.0 to 1.0) for each extracted entity")
        sections.append("- Do NOT invent information absent from the text")
        sections.append("- Do NOT translate proper nouns \u2014 keep them as-is from source text")
        sections.append("- Use canonical_name in lowercase, without articles (the/a/an)")

    # [CONTEXTE]
    has_context = entity_registry_context or previous_summary or phase0_hints
    if has_context:
        sections.append(f"\n[{lang.context_label}]")
        if entity_registry_context:
            label = (
                "Registre d'entit\u00e9s connues" if language == "fr" else "Known entity registry"
            )
            sections.append(f"{label}:\n{entity_registry_context}")
        if previous_summary:
            label = (
                "R\u00e9sum\u00e9 des chapitres pr\u00e9c\u00e9dents"
                if language == "fr"
                else "Previous chapters summary"
            )
            sections.append(f"\n{label}:\n{previous_summary}")
        if phase0_hints:
            label = "Indices Phase 0 (regex)" if language == "fr" else "Phase 0 hints (regex)"
            hints_json = json.dumps(phase0_hints, ensure_ascii=False)
            sections.append(f"\n{label}:\n{hints_json}")

    # [EXEMPLES]
    if few_shot_examples:
        sections.append(f"\n[{lang.examples_label}]\n{few_shot_examples}")

    return "\n".join(sections)
