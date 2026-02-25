"""Prompts for Pass 1: Character & Relationship Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting characters, their attributes, and relationships
from narrative text. Optimized for French-language LitRPG novels.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extrais TOUS les personnages et relations de ce chapitre.

Ce roman est en FRANÇAIS. Tu DOIS extraire tous les noms, descriptions
et attributs en français, exactement comme ils apparaissent dans le texte source.
Ne traduis JAMAIS en anglais.

Pour chaque PERSONNAGE, extrais :
- name : le nom principal utilisé dans le texte (orthographe exacte)
- canonical_name : le nom complet du personnage (prénom + nom si connu)
- role : protagonist, antagonist, mentor, sidekick, ally, minor, neutral
- species/race si mentionné
- aliases ou surnoms utilisés

Pour chaque RELATION entre personnages, extrais :
- les deux personnages impliqués (source et target)
- type : ally, enemy, mentor, family, romantic, rival, patron, subordinate, colleague, neutral
- subtype si applicable (père, mère, frère, sœur, etc.)
- contexte bref tiré du texte

RÈGLES IMPORTANTES :
- Extrais les entités dans l'ordre d'apparition dans le texte.
- Utilise les noms EXACTS tels qu'ils apparaissent dans le texte français.
- NE CRÉE PAS de nœuds pour des références génériques (« le guerrier », « l'ennemi »,
  « il », « elle ») — seuls les personnages NOMMÉS sont des entités.
- NE CRÉE PAS de nœuds pour des descriptions relationnelles (« la copine de Jake »,
  « le père de Caroline ») — utilise plutôt une RELATION entre les personnages nommés.
- Inclus les personnages mineurs seulement mentionnés, pas uniquement ceux qui parlent.
- Pour les relations, extrais uniquement celles explicitement déclarées ou clairement impliquées.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "Jake banda son arc, canalisant Powershot vers la bête. "
            "« Attention ! » avertit Jacob dans son esprit. « C'est un Sanglier Dentdefer. » "
            "Caroline observait depuis la clairière, prête à intervenir avec ses sorts de soin. "
            "Casper, lui, restait en retrait, son bouclier levé."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Jake",
                attributes={
                    "canonical_name": "Jake",
                    "role": "protagonist",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Jacob",
                attributes={
                    "canonical_name": "Jacob",
                    "role": "mentor",
                    "note": "communique par télépathie",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Caroline",
                attributes={
                    "canonical_name": "Caroline",
                    "role": "ally",
                    "note": "soigneuse",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Casper",
                attributes={
                    "canonical_name": "Casper",
                    "role": "ally",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Jacob dans son esprit",
                attributes={
                    "source": "Jake",
                    "target": "Jacob",
                    "type": "mentor",
                    "context": "Jacob guide Jake par télépathie",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Caroline observait depuis la clairière, prête à intervenir",
                attributes={
                    "source": "Caroline",
                    "target": "Jake",
                    "type": "ally",
                    "context": "Caroline soutient Jake en combat avec ses soins",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Dennis frappa le sol de sa hache, l'onde de choc repoussant les blaireaux. "
            "Sa collègue, Joanna, aurait désapprouvé de telles méthodes. "
            "Mais elle était à l'autre bout de la forêt, s'entraînant avec Bertram."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Dennis",
                attributes={
                    "canonical_name": "Dennis",
                    "role": "ally",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Joanna",
                attributes={
                    "canonical_name": "Joanna",
                    "role": "ally",
                    "note": "collègue de Dennis",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Bertram",
                attributes={
                    "canonical_name": "Bertram",
                    "role": "ally",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Sa collègue, Joanna",
                attributes={
                    "source": "Dennis",
                    "target": "Joanna",
                    "type": "colleague",
                },
            ),
        ],
    ),
]
