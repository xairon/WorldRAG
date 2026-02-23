"""Prompts for Pass 4: Lore & Worldbuilding Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting locations, items, creatures, factions, races,
and world concepts from narrative text.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extract ALL worldbuilding and lore elements from this chapter text.

Extract the following entity types:

LOCATIONS:
- name: place name as written
- type: city, dungeon, realm, continent, pocket_dimension, planet, forest,
  mountain, building, region
- description: what we learn about this place
- parent_location: larger area containing this location (if mentioned)

ITEMS & ARTIFACTS:
- name: item name exactly as written
- type: weapon, armor, consumable, artifact, key_item, tool, material
- rarity if mentioned (common, uncommon, rare, epic, legendary, unique)
- effects or properties if described
- owner: who possesses it

CREATURES & MONSTERS:
- name: creature name or species
- species: broader species category if mentioned
- threat_level: grade or danger level if mentioned
- habitat: where it lives

FACTIONS & ORGANIZATIONS:
- name: faction or group name
- type: guild, church, kingdom, clan, alliance, government, etc.
- alignment or disposition if clear

WORLD CONCEPTS:
- name: concept name (magic systems, rules of the world, etc.)
- domain: magic, politics, cosmology, economics, etc.
- description: how this concept works or what it means

IMPORTANT RULES:
- Extract locations even when only briefly mentioned.
- For items, capture both named/unique items AND generic types if relevant.
- Creatures include both named individuals and species references.
- World concepts capture the RULES and SYSTEMS of the universe.
- Do NOT extract game system elements (skills, classes, levels) — those belong
  to Pass 2.
- Extract entities in order of appearance.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "The entrance to Nevermore loomed before them, a pocket dimension "
            "created by the Architect eons ago. Inside, each floor tested different "
            "aspects of a cultivator's abilities. The first floor was a vast forest "
            "filled with D-grade Steelback Drakes and lesser beasts. "
            "Jake gripped his Nanoblade, the weapon humming with arcane energy."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="location",
                extraction_text="Nevermore",
                attributes={
                    "location_type": "dungeon",
                    "description": (
                        "pocket dimension created by the Architect, multi-floor test of abilities"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="location",
                extraction_text="first floor was a vast forest",
                attributes={
                    "name": "Nevermore Floor 1",
                    "location_type": "dungeon",
                    "parent_location": "Nevermore",
                    "description": "vast forest filled with D-grade beasts",
                },
            ),
            lx.data.Extraction(
                extraction_class="creature",
                extraction_text="Steelback Drakes",
                attributes={
                    "species": "Drake",
                    "threat_level": "D-grade",
                    "habitat": "Nevermore Floor 1",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Architect",
                attributes={
                    "note": "creator of Nevermore, mentioned historically",
                    "role": "minor",
                },
            ),
            lx.data.Extraction(
                extraction_class="item",
                extraction_text="Nanoblade",
                attributes={
                    "item_type": "weapon",
                    "owner": "Jake Thayne",
                    "effects": "humming with arcane energy",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "The Order of the Boundless Vault controlled trade across the multiverse. "
            "Their reach extended to every C-grade world and beyond. "
            "Mana, the fundamental energy of the multiverse, flowed through "
            "invisible ley lines that connected realms. Understanding these flows "
            "was key to spatial magic."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="faction",
                extraction_text="Order of the Boundless Vault",
                attributes={
                    "faction_type": "trade organization",
                    "description": "controls trade across the multiverse",
                },
            ),
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="Mana, the fundamental energy of the multiverse",
                attributes={
                    "name": "Mana",
                    "domain": "magic",
                    "description": "fundamental energy of the multiverse, flows through ley lines",
                },
            ),
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="ley lines that connected realms",
                attributes={
                    "name": "Ley Lines",
                    "domain": "magic",
                    "description": (
                        "invisible connections between realms "
                        "through which mana flows, "
                        "key to spatial magic"
                    ),
                },
            ),
        ],
    ),
]
