"""Prompts for Pass 1: Character & Relationship Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting characters, their attributes, and relationships
from narrative text.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extract ALL characters and relationships from this chapter text.

For each CHARACTER, extract:
- name: the primary name used in the text (exact spelling)
- role: protagonist, antagonist, mentor, sidekick, ally, minor, neutral
- species/race if mentioned
- any aliases or nicknames used

For each RELATIONSHIP between characters, extract:
- the two characters involved
- relationship type: ally, enemy, mentor, family, romantic, rival, patron, subordinate
- subtype if applicable (father, mother, sibling, spouse, etc.)
- brief context from the text

IMPORTANT RULES:
- Extract entities in order of appearance in the text.
- Use EXACT character names as they appear (do not normalize or abbreviate).
- Include minor characters who are only mentioned, not just those with dialogue.
- For relationships, only extract those explicitly stated or clearly implied.
- Do NOT extract generic group references as individual characters.
- Attribute each entity to one specific extraction class (character, relationship, etc.).
- Use the 'character_group' attribute to link relationships to their participants.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "Jake drew his bow, channeling Arcane Powershot toward the beast. "
            '"Careful!" Villy warned from within his mind. "That\'s a C-grade Steelback Drake." '
            "Sylphie screeched overhead, diving down to support Jake. "
            "The Sword Saint, Miyamoto, watched from the treeline with an approving nod."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Jake",
                attributes={
                    "canonical_name": "Jake Thayne",
                    "role": "protagonist",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Villy",
                attributes={
                    "canonical_name": "Villy",
                    "role": "mentor",
                    "note": "communicates telepathically",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Sylphie",
                attributes={
                    "canonical_name": "Sylphie",
                    "role": "sidekick",
                    "species": "hawk",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Miyamoto",
                attributes={
                    "canonical_name": "Miyamoto",
                    "role": "ally",
                    "alias": "Sword Saint",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Villy warned from within his mind",
                attributes={
                    "source": "Jake Thayne",
                    "target": "Villy",
                    "type": "patron",
                    "context": "Villy communicates telepathically with Jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Sylphie screeched overhead, diving down to support Jake",
                attributes={
                    "source": "Sylphie",
                    "target": "Jake Thayne",
                    "type": "ally",
                    "context": "Sylphie supports Jake in combat",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Zac slammed his axe into the ground, the shockwave sending the undead flying. "
            "His sister, Thea, would have disapproved of such brute methods. "
            "But she was an ocean away, training under the Radiant Temple."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Zac",
                attributes={
                    "canonical_name": "Zac Atwood",
                    "role": "protagonist",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Thea",
                attributes={
                    "canonical_name": "Thea Atwood",
                    "role": "ally",
                    "note": "Zac's sister",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="His sister, Thea",
                attributes={
                    "source": "Zac Atwood",
                    "target": "Thea Atwood",
                    "type": "family",
                    "subtype": "sibling",
                },
            ),
            lx.data.Extraction(
                extraction_class="faction_membership",
                extraction_text="training under the Radiant Temple",
                attributes={
                    "character": "Thea Atwood",
                    "faction": "Radiant Temple",
                    "role": "member",
                },
            ),
        ],
    ),
]
