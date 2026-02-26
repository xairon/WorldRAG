"""Prompt templates for skill provenance extraction (Pass 2b).

Identifies which items, classes, bloodlines, or titles grant specific skills.
"""

PROVENANCE_SYSTEM_PROMPT = """\
You are a LitRPG system analyst. Given a chapter excerpt and a list of skills
acquired in this chapter, identify the SOURCE of each skill.

Sources can be:
- item: An equipment or artifact grants the skill
- class: A class or job provides the skill
- bloodline: A bloodline ability manifests as the skill
- title: A title confers the skill
- unknown: Source is not mentioned or unclear

For each skill, return the source_type, source_name, and your confidence (0.0-1.0).
Only report confidence >= 0.5. If no source is evident, use "unknown".
"""

PROVENANCE_FEW_SHOT = [
    {
        "chapter_text": (
            "Jake equipped the Nanoblade, feeling its power flow through him.\n"
            "[Skill Acquired: Shadow Strike - Rare]\n"
            "The blade's enchantment granted him a new combat technique."
        ),
        "skills": ["Shadow Strike"],
        "result": [
            {
                "skill_name": "Shadow Strike",
                "source_type": "item",
                "source_name": "Nanoblade",
                "confidence": 0.95,
                "context": "The blade's enchantment granted him a new combat technique.",
            }
        ],
    },
    {
        "chapter_text": (
            "With his evolution to Avaricious Arcane Hunter, Jake gained access to "
            "a whole new set of abilities.\n"
            "[Skill Acquired: Arcane Powershot - Epic]"
        ),
        "skills": ["Arcane Powershot"],
        "result": [
            {
                "skill_name": "Arcane Powershot",
                "source_type": "class",
                "source_name": "Avaricious Arcane Hunter",
                "confidence": 0.9,
                "context": "evolution to Avaricious Arcane Hunter, Jake gained access to a whole new set of abilities",
            }
        ],
    },
]
