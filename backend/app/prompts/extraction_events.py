"""Prompts for Pass 3: Events & Timeline Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting narrative events, battles, discoveries, deaths,
and arc developments with temporal anchoring.
Optimized for French-language LitRPG novels.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extrais TOUS les événements narratifs significatifs de ce chapitre.

Ce roman est en FRANÇAIS. Tu DOIS écrire tous les noms d'événements,
descriptions et attributs en français. Ne traduis JAMAIS en anglais.

Pour chaque ÉVÉNEMENT, extrais :
- name : un nom court et descriptif EN FRANÇAIS (2-6 mots)
- description : ce qui s'est passé (1-2 phrases en français)
- event_type : action, state_change, achievement, process, dialogue
- significance : minor, moderate, major, critical, arc_defining
- participants : liste des noms de personnages impliqués
- location : où ça s'est passé (si mentionné)
- is_flashback : true si l'événement est narré comme un souvenir passé

GUIDE DES TYPES :
- action : un personnage fait quelque chose (combat, lance un sort, se déplace)
- state_change : un changement d'état (alliance, pouvoir gagné, lieu changé)
- achievement : une étape atteinte (montée de niveau, évolution de classe)
- process : une activité en cours (entraînement, fabrication, voyage)
- dialogue : une conversation significative qui révèle des informations

GUIDE DE SIGNIFICANCE :
- minor : événements de contexte, actions mineures
- moderate : développement de personnage, utilisation de compétence
- major : batailles importantes, révélations clés, montées en puissance
- critical : morts, trahisons majeures, moments qui changent l'arc narratif
- arc_defining : événements qui définissent ou concluent un arc narratif

RÈGLES IMPORTANTES :
- Capture les événements dans l'ORDRE CHRONOLOGIQUE du texte.
- Pour les flashbacks, mets is_flashback=true.
- Inclus TOUS les participants par nom.
- NE SUR-EXTRAIS PAS : combine les micro-actions liées en un seul événement.
- Chaque événement doit être une unité sémantiquement complète.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "Le Sanglier Dentdefer chargea, ses défenses luisant dans la pénombre. "
            "Jake encocha une flèche, canalisant Powershot. "
            "La flèche transperça ses défenses et toucha au but. "
            "La bête s'effondra, et une notification apparut : "
            "[Boss du tutoriel vaincu]\n"
            "Caroline accourut pour soigner ses blessures. "
            "« C'était imprudent », dit Casper en émergeant des fourrés."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Jake encocha une flèche, canalisant Powershot",
                attributes={
                    "name": "Jake vainc le Sanglier Dentdefer",
                    "event_type": "action",
                    "significance": "major",
                    "participants": "Jake, Caroline, Casper",
                    "description": (
                        "Jake utilise Powershot pour tuer le Sanglier Dentdefer, boss du tutoriel"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Boss du tutoriel vaincu",
                attributes={
                    "name": "Boss du tutoriel éliminé",
                    "event_type": "achievement",
                    "significance": "major",
                    "participants": "Jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="« C'était imprudent », dit Casper",
                attributes={
                    "name": "Casper critique Jake",
                    "event_type": "dialogue",
                    "significance": "minor",
                    "participants": "Casper, Jake",
                    "description": "Casper reproche à Jake son imprudence au combat",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Jake se rappela le jour où tout avait changé. Le Système était apparu "
            "sans prévenir, plongeant la Terre dans le chaos. Des millions de gens "
            "avaient été projetés dans le tutoriel. "
            "Maintenant, debout dans la Grande Forêt, il jura de survivre."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="event",
                extraction_text=(
                    "Le Système était apparu sans prévenir, plongeant la Terre dans le chaos"
                ),
                attributes={
                    "name": "Apparition du Système sur Terre",
                    "event_type": "state_change",
                    "significance": "arc_defining",
                    "participants": "Jake",
                    "is_flashback": "true",
                    "description": (
                        "Le Système apparaît sur Terre, plongeant le monde dans le chaos "
                        "et envoyant des millions de personnes dans le tutoriel"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="debout dans la Grande Forêt, il jura de survivre",
                attributes={
                    "name": "Serment de Jake",
                    "event_type": "state_change",
                    "significance": "major",
                    "participants": "Jake",
                    "location": "La Grande Forêt",
                    "description": "Jake jure de survivre dans la Grande Forêt du tutoriel",
                },
            ),
        ],
    ),
]
