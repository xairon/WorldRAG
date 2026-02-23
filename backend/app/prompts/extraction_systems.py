"""Prompts for Pass 2: Systems & Progression Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting LitRPG game-like systems: skills, classes, titles,
levels, stats, and progression events.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extract ALL game system / progression elements from this chapter text.

This is a LitRPG / progression fantasy novel with structured power systems.
Extract the following entity types:

SKILLS & ABILITIES:
- name: exact skill name as written
- type: active, passive, racial, class, profession, unique
- rank/rarity if mentioned (common, uncommon, rare, epic, legendary, etc.)
- owner: character who possesses or acquires the skill
- effects: what the skill does

CLASSES & PROFESSIONS:
- name: exact class/profession name
- tier if mentioned
- owner: who has this class
- whether it's a new acquisition or existing

TITLES:
- name: exact title name
- effects if mentioned
- owner: who earned the title
- requirements if stated

LEVEL CHANGES:
- character who leveled up
- old level and new level
- realm/grade/stage if mentioned

STAT CHANGES:
- stat name (Strength, Agility, Intelligence, etc.)
- amount of change
- character affected

IMPORTANT RULES:
- Extract from BOTH blue box notifications AND narrative text.
- If regex matches (Passe 0) already captured an entity, still extract it
  but add richer context from the narrative.
- Use EXACT names as written (preserve capitalization, spacing).
- Link every skill/class/title to its owner character.
- Extract entities in order of appearance.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "[Skill Acquired: Mark of the Ambitious Hunter - Legendary]\n"
            "Jake felt the power flow through him as the skill settled. "
            "It resonated with his Bloodline, amplifying his perception.\n\n"
            "+5 Perception\n+3 Agility\n\n"
            "His Arcane Hunter class hummed in approval."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="skill",
                extraction_text="Mark of the Ambitious Hunter",
                attributes={
                    "rank": "legendary",
                    "owner": "Jake Thayne",
                    "skill_type": "unique",
                    "effects": "amplifies perception, resonates with Bloodline",
                },
            ),
            lx.data.Extraction(
                extraction_class="stat_change",
                extraction_text="+5 Perception",
                attributes={
                    "stat_name": "Perception",
                    "value": "5",
                    "character": "Jake Thayne",
                },
            ),
            lx.data.Extraction(
                extraction_class="stat_change",
                extraction_text="+3 Agility",
                attributes={
                    "stat_name": "Agility",
                    "value": "3",
                    "character": "Jake Thayne",
                },
            ),
            lx.data.Extraction(
                extraction_class="class",
                extraction_text="Arcane Hunter",
                attributes={
                    "owner": "Jake Thayne",
                    "note": "existing class, not newly acquired",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Level: 87 -> 89\n"
            "Class: Arcane Hunter (D-grade)\n\n"
            "Title earned: Slayer of the Monarch\n"
            "Effect: +10% damage against creatures above your grade."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="level_change",
                extraction_text="Level: 87 -> 89",
                attributes={
                    "character": "Jake Thayne",
                    "old_level": "87",
                    "new_level": "89",
                },
            ),
            lx.data.Extraction(
                extraction_class="class",
                extraction_text="Arcane Hunter (D-grade)",
                attributes={
                    "name": "Arcane Hunter",
                    "owner": "Jake Thayne",
                    "tier_info": "D-grade",
                },
            ),
            lx.data.Extraction(
                extraction_class="title",
                extraction_text="Slayer of the Monarch",
                attributes={
                    "owner": "Jake Thayne",
                    "effects": "+10% damage against creatures above your grade",
                },
            ),
        ],
    ),
]
