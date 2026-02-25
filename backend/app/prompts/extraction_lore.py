"""Prompts for Pass 4: Lore & Worldbuilding Extraction.

Provides the LangExtract prompt description and few-shot examples
for extracting locations, items, creatures, factions, races,
and world concepts from narrative text.
Optimized for French-language LitRPG novels.
"""

from __future__ import annotations

import langextract as lx

PROMPT_DESCRIPTION = """\
Extrais TOUS les éléments de worldbuilding et de lore de ce chapitre.

Ce roman est en FRANÇAIS. Tu DOIS extraire tous les noms, descriptions
et attributs en français, exactement comme dans le texte source.
Ne traduis JAMAIS en anglais.

LIEUX :
- name : nom du lieu tel qu'écrit dans le texte
- type : ville, donjon, royaume, continent, dimension, planète, forêt,
  montagne, bâtiment, région, tutoriel
- description : ce qu'on apprend sur ce lieu
- parent_location : zone plus grande contenant ce lieu (si mentionnée)

OBJETS & ARTEFACTS :
- name : nom de l'objet exactement tel qu'écrit
- type : arme, armure, consommable, artefact, objet clé, outil, matériau
- rareté si mentionnée (commun, peu commun, rare, épique, légendaire, unique)
- effets ou propriétés si décrits
- owner : qui le possède

CRÉATURES & MONSTRES :
- name : nom de la créature ou espèce tel qu'écrit dans le texte
- species : catégorie d'espèce plus large si mentionnée
- threat_level : grade ou niveau de danger si mentionné
- habitat : où elle vit

FACTIONS & ORGANISATIONS :
- name : nom de la faction ou du groupe
- type : guilde, ordre, royaume, clan, alliance, gouvernement, etc.
- alignment ou disposition si claire

CONCEPTS DU MONDE :
- name : nom du concept (systèmes magiques, règles du monde, etc.)
- domain : magie, politique, cosmologie, économie, etc.
- description : comment ce concept fonctionne ou ce qu'il signifie

RÈGLES IMPORTANTES :
- NE CRÉE PAS d'entité pour des lieux génériques (« la forêt », « un arbre »,
  « le bâtiment ») — seuls les lieux NOMMÉS sont des entités.
- NE CRÉE PAS d'entité pour des objets génériques (« une épée », « des flèches »,
  « l'armure ») — seuls les objets NOMMÉS ou UNIQUES sont des entités.
- NE CRÉE PAS d'entité pour des créatures génériques (« les bêtes », « des animaux »)
  — seules les ESPÈCES NOMMÉES sont des entités.
- N'extrais PAS les éléments de système de jeu (compétences, classes, niveaux)
  — ils appartiennent à la Passe 2.
- Extrais dans l'ordre d'apparition.
"""

FEW_SHOT_EXAMPLES = [
    lx.data.ExampleData(
        text=(
            "L'entrée de la Grande Forêt s'ouvrait devant eux, un espace immense "
            "créé par le Système pour le tutoriel. À l'intérieur, chaque zone testait "
            "différents aspects des capacités d'un initié. La première zone était peuplée "
            "de Sangliers Dentdefer et de blaireaux mutants. "
            "Jake serra son Nanoblade, l'arme vibrant d'énergie arcanique."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="location",
                extraction_text="la Grande Forêt",
                attributes={
                    "name": "La Grande Forêt",
                    "location_type": "forêt",
                    "description": (
                        "espace immense créé par le Système pour le tutoriel, "
                        "divisé en zones testant les capacités des initiés"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="creature",
                extraction_text="Sangliers Dentdefer",
                attributes={
                    "name": "Sanglier Dentdefer",
                    "species": "sanglier",
                    "habitat": "La Grande Forêt",
                },
            ),
            lx.data.Extraction(
                extraction_class="item",
                extraction_text="Nanoblade",
                attributes={
                    "name": "Nanoblade",
                    "item_type": "arme",
                    "owner": "Jake",
                    "effects": "vibre d'énergie arcanique",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "Les Terriens étaient la dernière race à avoir été intégrée au Multivers. "
            "Les Races de la Myriade, disséminées à travers des milliers de mondes, "
            "observaient les nouveaux venus avec curiosité. "
            "Le Mana, énergie fondamentale du Multivers, coulait à travers "
            "des lignes invisibles reliant les dimensions."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="faction",
                extraction_text="Les Terriens",
                attributes={
                    "name": "Terriens",
                    "faction_type": "race",
                    "description": "dernière race intégrée au Multivers",
                },
            ),
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="Les Races de la Myriade",
                attributes={
                    "name": "Races de la Myriade",
                    "domain": "cosmologie",
                    "description": "races disséminées à travers des milliers de mondes dans le Multivers",
                },
            ),
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="Le Mana, énergie fondamentale du Multivers",
                attributes={
                    "name": "Mana",
                    "domain": "magie",
                    "description": "énergie fondamentale du Multivers, coule à travers des lignes invisibles reliant les dimensions",
                },
            ),
        ],
    ),
]
