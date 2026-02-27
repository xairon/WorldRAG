"""Prompts V3 pour Phase 6 : Analyse narrative avancee.

Identifie les developpements de personnages, progressions de puissance,
indices de prefiguration (foreshadowing) et themes recurrents.

Inclut le schema de sortie structure et des exemples few-shot.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/narrative.py)
# ---------------------------------------------------------------------------

PHASE = 6

PROMPT_DESCRIPTION = """\
Tu es un expert en analyse litteraire specialise dans la fiction
LitRPG et fantasy. Analyse le chapitre et identifie les elements
narratifs avances.
"""

NARRATIVE_ANALYSIS_PROMPT = """\
Tu es un expert en analyse litteraire specialise dans la fiction
LitRPG et progression fantasy. Analyse le chapitre suivant et identifie
les elements narratifs avances.

=== REGISTRE D'ENTITES CONNUES ===
{entity_context}

=== TEXTE DU CHAPITRE ===
{chapter_text}

=== CATEGORIES D'ANALYSE ===

1. **Developpements de personnages** : changements de personnalite,
   croissance emotionnelle, evolution des motivations, moments de
   prise de conscience, changements d'alignement moral.

2. **Progressions de puissance** : montees de niveau, acquisition
   de competences, changement de classe, gains de stats significatifs,
   eveil de bloodline, evolution de rang.

3. **Indices de prefiguration (foreshadowing)** : elements narratifs
   qui annoncent des evenements futurs, mysteres non resolus,
   promesses narratives, details suspects ou inhabituels.

4. **Themes recurrents** : motifs narratifs, themes philosophiques
   ou moraux qui traversent le recit, symboles repetes.

=== SCHEMA DE SORTIE (JSON) ===
{{
  "character_developments": [
    {{
      "character": "<canonical_name>",
      "development_type": "personality|motivation|moral|emotional|power",
      "description": "<description en francais>",
      "evidence": "<extrait du texte>",
      "significance": "minor|moderate|major|critical"
    }}
  ],
  "power_progressions": [
    {{
      "character": "<canonical_name>",
      "progression_type": "level_up|skill_gain|class_change|stat_boost|bloodline|rank_up",
      "description": "<description en francais>",
      "evidence": "<extrait du texte>"
    }}
  ],
  "foreshadowing": [
    {{
      "description": "<ce qui est presage>",
      "evidence": "<extrait du texte>",
      "confidence": 0.0-1.0,
      "possible_payoff": "<ce qui pourrait se realiser>"
    }}
  ],
  "themes": [
    {{
      "name": "<nom du theme>",
      "description": "<comment il se manifeste>",
      "evidence": "<extrait du texte>"
    }}
  ]
}}

=== REGLES ===
- Sois precis et ne liste que les elements identifies avec confiance.
- Qualite > quantite.
- Chaque element DOIT avoir un extrait textuel (evidence) comme preuve.
- Ne confonds pas foreshadowing avec speculation gratuite.
- Les progressions de puissance doivent etre des changements concrets,
  pas des descriptions de capacites existantes.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Developpement de personnage + foreshadowing ---
    {
        "entity_context": (
            "- jake (Character, protagonist)\n"
            "- jacob (Character, mentor)\n"
            "- le vilain vipere (Character, patron)"
        ),
        "chapter_text": (
            "Jake contempla le cadavre du Sanglier Dentdefer. Il avait change. "
            "Avant le tutoriel, la simple idee de tuer le revulsait. Maintenant, "
            "il ressentait une excitation primitive, un plaisir de predateur. "
            "Jacob murmura dans son esprit : \u00ab Le sang des Primordiaux coule "
            "en toi, plus fort que tu ne le crois. \u00bb "
            "Jake ignora la remarque, mais une lueur etrange brilla dans ses yeux."
        ),
        "result": {
            "character_developments": [
                {
                    "character": "jake",
                    "development_type": "moral",
                    "description": (
                        "Jake evolue d'une aversion pour la violence vers un plaisir "
                        "predateur au combat, marquant un tournant moral."
                    ),
                    "evidence": (
                        "Avant le tutoriel, la simple idee de tuer le revulsait. "
                        "Maintenant, il ressentait une excitation primitive, "
                        "un plaisir de predateur."
                    ),
                    "significance": "major",
                },
            ],
            "power_progressions": [],
            "foreshadowing": [
                {
                    "description": (
                        "Jacob fait allusion a un heritage primordial chez Jake, "
                        "suggere un lien de sang avec les Primordiaux."
                    ),
                    "evidence": (
                        "Le sang des Primordiaux coule en toi, plus fort "
                        "que tu ne le crois."
                    ),
                    "confidence": 0.85,
                    "possible_payoff": (
                        "Eveil d'une Bloodline ou revelation de la connexion "
                        "de Jake avec un Primordial."
                    ),
                },
                {
                    "description": (
                        "La lueur etrange dans les yeux de Jake pourrait "
                        "presager une transformation physique ou un eveil de pouvoir."
                    ),
                    "evidence": "une lueur etrange brilla dans ses yeux",
                    "confidence": 0.6,
                    "possible_payoff": "Manifestation visible d'un pouvoir latent.",
                },
            ],
            "themes": [
                {
                    "name": "Perte d'humanite",
                    "description": (
                        "Le theme de la deshumanisation progressive au contact "
                        "du Systeme se manifeste par le plaisir que Jake "
                        "prend au combat."
                    ),
                    "evidence": (
                        "il ressentait une excitation primitive, un plaisir "
                        "de predateur"
                    ),
                },
            ],
        },
    },
    # --- Exemple 2 : Progression de puissance + theme ---
    {
        "entity_context": "- jake (Character, protagonist)",
        "chapter_text": (
            "[Bloodline Awakened: Bloodline of the Primal Hunter]\n"
            "Jake sentit une energie primordiale affluer en lui. Sa perception "
            "s'aiguisa d'un coup, chaque bruit, chaque odeur devenant net. "
            "Il etait un chasseur. Il l'avait toujours ete."
        ),
        "result": {
            "character_developments": [
                {
                    "character": "jake",
                    "development_type": "emotional",
                    "description": (
                        "Jake accepte sa nature de chasseur avec la conviction "
                        "que c'est son identite profonde."
                    ),
                    "evidence": (
                        "Il etait un chasseur. Il l'avait toujours ete."
                    ),
                    "significance": "major",
                },
            ],
            "power_progressions": [
                {
                    "character": "jake",
                    "progression_type": "bloodline",
                    "description": (
                        "Eveil de la Bloodline of the Primal Hunter, "
                        "conferant une perception accrue."
                    ),
                    "evidence": (
                        "[Bloodline Awakened: Bloodline of the Primal Hunter]"
                    ),
                },
            ],
            "foreshadowing": [],
            "themes": [
                {
                    "name": "Identite predeterminee",
                    "description": (
                        "Le theme du destin ou de la nature innee : Jake decouvre "
                        "que sa nature de chasseur etait inherente, pas acquise."
                    ),
                    "evidence": "Il etait un chasseur. Il l'avait toujours ete.",
                },
            ],
        },
    },
]
