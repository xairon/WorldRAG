"""Progressive extraction router — decides which passes to run.

Analyzes chapter text with cheap heuristics (keyword detection, regex match
density, text structure) to determine which extraction passes are worth running.

This is a cost optimization: not every chapter has system notifications,
not every chapter has significant lore dumps. Skip unnecessary LLM calls.

Routing decision is a LangGraph conditional edge.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.agents.state import ExtractionPipelineState

logger = get_logger(__name__)

# ── Keyword indicators for each pass ────────────────────────────────────

# Pass 1 (Characters) — always runs, characters appear in every chapter
# Pass 2 (Systems) — LitRPG progression signals (EN + FR)
SYSTEM_KEYWORDS = re.compile(
    r"\b(?:"
    # ── English ──
    r"skill|level|class|title|stat|ability|evolution|upgrade|breakthrough|"
    r"acquired|learned|gained|earned|obtained|evolves?|rank(?:ed)?|tier|"
    r"profession|bloodline|blessing|notification|system\s+message|"
    # ── French ──
    r"compétence|classe|titre|niveau|amélioration|évolution|"
    r"acquis|appris|obtenu|déverrouillé|débloqué|"
    r"grade|rang|bénédiction|aptitude|maîtrise|"
    r"profession|lignée|notification|message\s+système|"
    r"montée\s+de\s+niveau|gain\s+de\s+niveau|"
    # ── Patterns (language-agnostic) ──
    r"\+\d+\s+\w+|"  # +5 Perception / +5 Force
    r"Level:\s*\d+|Niveau\s*:\s*\d+|"  # Level: 87 / Niveau : 87
    r"\[(?:Skill|Ability|Class|Title|Compétence|Classe|Titre)"  # [Skill Acquired: ...]
    r")\b",
    re.IGNORECASE,
)

# Pass 3 (Events) — narrative event signals (EN + FR)
EVENT_KEYWORDS = re.compile(
    r"\b(?:"
    # ── English ──
    r"battle|fight|killed|defeated|died|death|attacked|ambush|"
    r"discovered|revealed|betrayed|alliance|war|peace|"
    r"quest|mission|escaped|captured|saved|rescued|"
    r"ceremony|ritual|awakened|transformed|"
    r"arrived|departed|journeyed|traveled|fled|"
    r"swore|promised|decided|agreed|refused|"
    # ── French ──
    r"combat|batail|tué|vaincu|mort|attaqué|embuscade|"
    r"découvert|révélé|trahi|alliance|guerre|paix|"
    r"quête|mission|échappé|capturé|sauvé|secouru|"
    r"cérémonie|rituel|éveillé|transformé|"
    r"arrivé|parti|voyagé|fui|enfui|"
    r"juré|promis|décidé|accepté|refusé|"
    r"affronté|blessé|survécu|détruit|rencontré"
    r")\b",
    re.IGNORECASE,
)

# Pass 4 (Lore) — worldbuilding signals (EN + FR)
LORE_KEYWORDS = re.compile(
    r"\b(?:"
    # ── English ──
    r"dungeon|realm|dimension|continent|kingdom|city|temple|forest|tower|"
    r"artifact|weapon|potion|elixir|enchant|rune|"
    r"creature|monster|beast|dragon|demon|spirit|"
    r"guild|order|faction|clan|church|empire|council|"
    r"mana|energy|dao|cultivation|magic|law|rule|"
    r"race|species|elf|dwarf|goblin|orc|undead|"
    r"ancient|prophecy|legend|myth|lore|"
    # ── French ──
    r"donjon|royaume|dimension|continent|ville|temple|forêt|tour|"
    r"artefact|arme|potion|élixir|enchant|rune|"
    r"créature|monstre|bête|dragon|démon|esprit|"
    r"guilde|ordre|faction|clan|église|empire|conseil|"
    r"mana|énergie|magie|loi|règle|"
    r"race|espèce|elfe|nain|gobelin|orc|mort-vivant|"
    r"ancien|prophétie|légende|mythe|savoir|"
    r"tutoriel|univers|système|initiation"
    r")\b",
    re.IGNORECASE,
)

# Thresholds for pass activation
SYSTEM_THRESHOLD = 2  # Need 2+ system keywords to trigger Pass 2
EVENT_THRESHOLD = 2  # Need 2+ event keywords to trigger Pass 3
LORE_THRESHOLD = 3  # Need 3+ lore keywords to trigger Pass 4

# Short chapters get all passes (not enough signal to decide)
SHORT_CHAPTER_CHARS = 2000


def route_extraction_passes(state: ExtractionPipelineState) -> dict[str, Any]:
    """LangGraph node: Determine which extraction passes to run.

    Analyzes chapter text and regex match density to decide which
    of the 4 passes are worth the LLM cost.

    Always runs Pass 1 (Characters) — characters appear everywhere.
    Conditionally runs Passes 2-4 based on keyword density.

    Args:
        state: ExtractionPipelineState with chapter_text.

    Returns:
        State update with passes_to_run list.
    """
    chapter_text = state["chapter_text"]  # type: ignore[typeddict-item]
    book_id = state["book_id"]  # type: ignore[typeddict-item]
    chapter_number = state["chapter_number"]  # type: ignore[typeddict-item]
    genre = state.get("genre", "litrpg")

    passes: list[str] = ["characters"]  # Always run Pass 1

    # Short chapters: run everything (not enough signal to filter)
    if len(chapter_text) < SHORT_CHAPTER_CHARS:
        passes = ["characters", "systems", "events", "lore"]
        logger.info(
            "extraction_routing_short_chapter",
            book_id=book_id,
            chapter=chapter_number,
            passes=passes,
        )
        return {"passes_to_run": passes}

    # Count keyword hits
    system_hits = len(SYSTEM_KEYWORDS.findall(chapter_text))
    event_hits = len(EVENT_KEYWORDS.findall(chapter_text))
    lore_hits = len(LORE_KEYWORDS.findall(chapter_text))

    # Check regex match density (Passe 0 pre-extraction)
    regex_json = state.get("regex_matches_json", "")
    has_regex_matches = regex_json and regex_json != "[]" and len(regex_json) > 10

    # Pass 2 (Systems): triggered by keywords OR regex matches
    is_progression_genre = genre.lower() in (
        "litrpg",
        "progression_fantasy",
        "cultivation",
    )
    if (
        system_hits >= SYSTEM_THRESHOLD
        or has_regex_matches
        or (is_progression_genre and system_hits >= 1)
    ):
        passes.append("systems")

    # Pass 3 (Events): triggered by event keywords
    if event_hits >= EVENT_THRESHOLD:
        passes.append("events")

    # Pass 4 (Lore): triggered by lore keywords
    if lore_hits >= LORE_THRESHOLD:
        passes.append("lore")

    # Safety: at minimum run characters + events (narrative is always present)
    if "events" not in passes and event_hits >= 1:
        passes.append("events")

    logger.info(
        "extraction_routing_decided",
        book_id=book_id,
        chapter=chapter_number,
        passes=passes,
        system_hits=system_hits,
        event_hits=event_hits,
        lore_hits=lore_hits,
        has_regex=has_regex_matches,
        genre=genre,
    )

    return {"passes_to_run": passes}
