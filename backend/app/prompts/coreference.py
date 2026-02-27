"""Prompts V3 pour Phase 5b : Resolution de coreferences.

Resout les pronoms et references anaphoriques dans le texte narratif
en les associant aux entites connues du registre.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/coreference.py)
# ---------------------------------------------------------------------------

PHASE = 5

PROMPT_DESCRIPTION = """\
Tu es un expert en analyse linguistique et resolution de coreferences.

Resous les pronoms et references anaphoriques dans le texte suivant
en les associant au personnage ou entite correct du registre.
"""

COREFERENCE_PROMPT = """\
Tu es un expert en analyse linguistique specialise dans la fiction LitRPG.
Resous les pronoms et references anaphoriques dans le texte suivant
en les associant au personnage ou entite correct.

=== REGISTRE D'ENTITES CONNUES ===
{entity_context}

=== TEXTE A ANALYSER ===
{text}

=== INSTRUCTIONS ===
Pour chaque pronom ou reference anaphorique (il, elle, ils, elles, lui, leur,
son, sa, ses, celui-ci, celle-ci, ce dernier, cette derniere, le premier, etc.),
indique a quel personnage ou entite il fait reference.

Format de sortie attendu (JSON) :
{{
  "resolutions": [
    {{
      "pronom": "<le pronom tel qu'il apparait>",
      "position": <index du caractere dans le texte>,
      "referent": "<canonical_name de l'entite>",
      "confiance": <0.0 a 1.0>
    }}
  ]
}}

=== REGLES ===
- Ne resous que les pronoms pour lesquels tu es confiant (>= 0.8).
- Ignore les pronoms ambigus ou les pronoms impersonnels (il pleut, il faut).
- Prefere le referent le plus recent dans le contexte narratif (principe de proximite).
- Pour les pronoms possessifs (son, sa, ses), lie au possesseur le plus probable.
- Si plusieurs personnages du meme genre sont en scene, ne resous PAS le pronom.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Resolution standard avec multiple personnages ---
    {
        "entity_context": (
            "- jake (Character, protagonist)\n"
            "- caroline (Character, ally, soigneuse)\n"
            "- casper (Character, ally)"
        ),
        "text": (
            "Jake banda son arc. Il visa la bete et tira. "
            "Caroline accourut vers lui pour soigner ses blessures. "
            "Elle utilisa ses sorts les plus puissants."
        ),
        "result": {
            "resolutions": [
                {"pronom": "son", "position": 12, "referent": "jake", "confiance": 0.95},
                {"pronom": "Il", "position": 22, "referent": "jake", "confiance": 0.95},
                {"pronom": "lui", "position": 67, "referent": "jake", "confiance": 0.90},
                {"pronom": "ses", "position": 83, "referent": "jake", "confiance": 0.85},
                {"pronom": "Elle", "position": 97, "referent": "caroline", "confiance": 0.95},
                {"pronom": "ses", "position": 111, "referent": "caroline", "confiance": 0.90},
            ],
        },
    },
    # --- Exemple 2 : Cas ambigu (deux personnages masculins, certains non resolus) ---
    {
        "entity_context": (
            "- dennis (Character, ally)\n"
            "- bertram (Character, ally)"
        ),
        "text": (
            "Dennis et Bertram combattaient cote a cote. "
            "Il frappa de sa hache tandis que l'autre esquivait. "
            "Ils etaient epuises."
        ),
        "result": {
            "resolutions": [
                # "Il" est ambigu (Dennis ou Bertram?) => non resolu
                {"pronom": "Ils", "position": 88, "referent": "dennis, bertram", "confiance": 0.95},
            ],
        },
    },
]
