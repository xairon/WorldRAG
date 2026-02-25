"""Prompts for Pass 2: Systems & Progression Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting LitRPG game-like systems: skills, classes, titles,
levels, stats, and progression events. Optimized for French LitRPG.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extrais TOUS les éléments de système de jeu / progression de ce chapitre.

Ce roman est en FRANÇAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms de compétences, classes, titres en français, exactement comme
ils apparaissent dans le texte source. Ne traduis JAMAIS en anglais.

COMPÉTENCES & APTITUDES :
- name : nom exact de la compétence tel qu'écrit dans le texte
- type : active, passive, raciale, de classe, de profession, unique
- rank/rareté si mentionnée (commun, peu commun, rare, épique, légendaire, etc.)
- owner : personnage qui possède ou acquiert la compétence
- effects : ce que fait la compétence

CLASSES & PROFESSIONS :
- name : nom exact de la classe/profession
- tier si mentionné
- owner : qui possède cette classe
- si c'est une nouvelle acquisition ou une classe existante

TITRES :
- name : nom exact du titre
- effects si mentionnés
- owner : qui a gagné le titre
- conditions si indiquées

CHANGEMENTS DE NIVEAU :
- personnage qui a gagné un niveau
- ancien et nouveau niveau
- grade/rang si mentionné

CHANGEMENTS DE STATS :
- nom de la stat (Force, Agilité, Intelligence, etc.)
- montant du changement
- personnage affecté

RÈGLES IMPORTANTES :
- Extrais des NOTIFICATIONS (blue boxes/encadrés) ET du texte narratif.
- Utilise les noms EXACTS tels qu'écrits (préserve majuscules, espaces, accents).
- Lie chaque compétence/classe/titre à son propriétaire.
- NE CRÉE PAS d'entité pour des descriptions génériques comme « compétence de combat »
  ou « maniement d'armes » — seuls les noms PROPRES de compétences sont des entités.
- Extrais dans l'ordre d'apparition.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "[Compétence acquise : Œil de l'Archer – Rare]\n"
            "Jake sentit le pouvoir affluer en lui. Sa perception s'aiguisa.\n\n"
            "+5 Perception\n+3 Agilité\n\n"
            "Sa classe d'Archer bourdonna en approbation."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="skill",
                extraction_text="Œil de l'Archer",
                attributes={
                    "rank": "rare",
                    "owner": "Jake",
                    "skill_type": "passive",
                    "effects": "aiguise la perception",
                },
            ),
            lx.data.Extraction(
                extraction_class="stat_change",
                extraction_text="+5 Perception",
                attributes={
                    "stat_name": "Perception",
                    "value": "5",
                    "character": "Jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="stat_change",
                extraction_text="+3 Agilité",
                attributes={
                    "stat_name": "Agilité",
                    "value": "3",
                    "character": "Jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="class",
                extraction_text="Archer",
                attributes={
                    "owner": "Jake",
                    "note": "classe existante, pas nouvellement acquise",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Niveau : 3 -> 5\n"
            "Classe : Chasseur Ambitieux\n\n"
            "Titre obtenu : Pionnier du Nouveau Monde\n"
            "Effet : +10% de dégâts contre les créatures du tutoriel."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="level_change",
                extraction_text="Niveau : 3 -> 5",
                attributes={
                    "character": "Jake",
                    "old_level": "3",
                    "new_level": "5",
                },
            ),
            lx.data.Extraction(
                extraction_class="class",
                extraction_text="Chasseur Ambitieux",
                attributes={
                    "name": "Chasseur Ambitieux",
                    "owner": "Jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="title",
                extraction_text="Pionnier du Nouveau Monde",
                attributes={
                    "owner": "Jake",
                    "effects": "+10% de dégâts contre les créatures du tutoriel",
                },
            ),
        ],
    ),
]
