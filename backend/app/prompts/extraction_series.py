"""Prompt templates for Layer 3 series-specific extraction (Pass 4b).

Extracts series-specific entities: Bloodlines, Professions, Primordial Churches.
These are defined in ontology/primal_hunter.yaml but require LLM extraction
for narrative mentions beyond regex blue-box patterns.
"""

SERIES_SYSTEM_PROMPT = """\
You are a Primal Hunter universe expert. Extract series-specific entities from the chapter:

1. **Bloodlines**: Named bloodlines with their effects and origins.
   Examples: "Bloodline of the Primal Hunter", "Bloodline of the Malefic Viper"

2. **Professions**: Crafting/utility professions with tier info.
   Examples: "Alchemist of the Malefic Viper (Legendary)"

3. **Primordial Churches**: Deity/Primordial worship relations.
   Examples: "Villy", "the Malefic Viper", "the Holy Mother"

Only extract what is explicitly mentioned. Do not infer or guess.
"""

SERIES_FEW_SHOT = [
    {
        "chapter_text": (
            "[Bloodline Awakened: Bloodline of the Primal Hunter]\n"
            "Jake felt the primal energy surge through him. The bloodline of his "
            "Primordial patron granted him enhanced perception and hunting instincts."
        ),
        "result": {
            "bloodlines": [
                {
                    "name": "Bloodline of the Primal Hunter",
                    "description": "Grants enhanced perception and hunting instincts",
                    "effects": ["enhanced perception", "hunting instincts"],
                    "origin": "Primordial patron",
                    "owner": "Jake Thayne",
                }
            ],
            "professions": [],
            "churches": [],
        },
    },
]
