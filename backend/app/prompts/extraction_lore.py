"""Prompts V3 pour Phase 1 : Extraction de Lore & Worldbuilding.

Fournit la description de prompt et les exemples few-shot pour extraire
les lieux, objets, concepts et propheties du texte narratif.
Ontologie cible : Location, Item, Concept, Prophecy.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

import langextract as lx

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/lore.py)
# ---------------------------------------------------------------------------

PHASE = 1

PROMPT_DESCRIPTION = """\
Extrais TOUS les elements de worldbuilding et de lore de ce chapitre.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms, descriptions et attributs en francais, exactement comme
dans le texte source. Ne traduis JAMAIS en anglais.

=== TYPES D'ENTITES CIBLES (Ontologie V3) ===

LOCATION (lieu) :
- name : nom du lieu tel qu'ecrit dans le texte
- location_type : city, dungeon, realm, continent, pocket_dimension, planet,
  forest, mountain, building, region
- description : ce qu'on apprend sur ce lieu
- parent_location_name : zone plus grande contenant ce lieu (si mentionnee)

ITEM (objet / artefact) :
- name : nom de l'objet exactement tel qu'ecrit
- item_type : weapon, armor, consumable, artifact, key_item, tool, material
- rarity : common, uncommon, rare, epic, legendary, unique (si mentionnee)
- effects : effets ou proprietes si decrits
- owner : qui le possede

CONCEPT (concept du monde) :
- name : nom du concept (systemes magiques, regles du monde, etc.)
- domain : magie, politique, cosmologie, economie, theologie, etc.
- description : comment ce concept fonctionne ou ce qu'il signifie

PROPHECY (prophetie / prediction) :
- name : nom ou designation de la prophetie
- description : contenu ou formulation de la prophetie
- status : unfulfilled, fulfilled, subverted

=== REGLES D'EXTRACTION ===
- NE CREE PAS d'entite pour des lieux generiques (la foret, un arbre, le batiment).
  Seuls les lieux NOMMES sont des entites.
- NE CREE PAS d'entite pour des objets generiques (une epee, des fleches, l'armure).
  Seuls les objets NOMMES ou UNIQUES sont des entites.
- N'extrais PAS les elements de systeme de jeu (competences, classes, niveaux).
  Ils appartiennent a la Phase 2.
- N'extrais PAS les creatures ou races. Elles appartiennent a la Phase 2 (Creatures).
- N'extrais PAS les factions. Elles appartiennent a la Phase 1 (Characters).
- Extrais les propheties seulement quand le texte les formule explicitement
  (pas de simples pressentiments).
- Extrais dans l'ordre d'apparition.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Golden example (lieu + creature + objet + concept) ---
    lx.data.ExampleData(
        text=(
            "L'entree de la Grande Foret s'ouvrait devant eux, un espace immense "
            "cree par le Systeme pour le tutoriel. A l'interieur, chaque zone testait "
            "differents aspects des capacites d'un initie. "
            "Jake serra son Nanoblade, l'arme vibrant d'energie arcanique. "
            "Plus loin, la Citadelle de l'Ecorche se dressait au sommet de la colline, "
            "la ou le boss final attendait."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="location",
                extraction_text="la Grande Foret",
                attributes={
                    "name": "La Grande Foret",
                    "location_type": "forest",
                    "description": (
                        "espace immense cree par le Systeme pour le tutoriel, "
                        "divise en zones testant les capacites des inities"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="item",
                extraction_text="Nanoblade",
                attributes={
                    "name": "Nanoblade",
                    "item_type": "weapon",
                    "owner": "jake",
                    "effects": "vibre d'energie arcanique",
                },
            ),
            lx.data.Extraction(
                extraction_class="location",
                extraction_text="Citadelle de l'Ecorche",
                attributes={
                    "name": "Citadelle de l'Ecorche",
                    "location_type": "dungeon",
                    "description": "lieu du boss final, au sommet de la colline",
                    "parent_location_name": "La Grande Foret",
                },
            ),
        ],
    ),
    # --- Exemple 2 : Concepts cosmologiques + prophetie ---
    lx.data.ExampleData(
        text=(
            "Les Terriens etaient la derniere race a avoir ete integree au Multivers. "
            "Les Races de la Myriade, disseminees a travers des milliers de mondes, "
            "observaient les nouveaux venus avec curiosite. "
            "Le Mana, energie fondamentale du Multivers, coulait a travers "
            "des lignes invisibles reliant les dimensions. "
            "Selon l'Ancienne Prophetie des Primordiaux, une race tardive "
            "bouleverserait l'equilibre du Multivers."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="Les Races de la Myriade",
                attributes={
                    "name": "Races de la Myriade",
                    "domain": "cosmologie",
                    "description": (
                        "races disseminees a travers des milliers de mondes "
                        "dans le Multivers"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="Le Mana, energie fondamentale du Multivers",
                attributes={
                    "name": "Mana",
                    "domain": "magie",
                    "description": (
                        "energie fondamentale du Multivers, coule a travers "
                        "des lignes invisibles reliant les dimensions"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="concept",
                extraction_text="Multivers",
                attributes={
                    "name": "Multivers",
                    "domain": "cosmologie",
                    "description": (
                        "ensemble des mondes et dimensions relies par le Mana, "
                        "ou les Races de la Myriade coexistent"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="prophecy",
                extraction_text=(
                    "Ancienne Prophetie des Primordiaux, une race tardive "
                    "bouleverserait l'equilibre du Multivers"
                ),
                attributes={
                    "name": "Ancienne Prophetie des Primordiaux",
                    "description": (
                        "une race tardive bouleverserait l'equilibre du Multivers"
                    ),
                    "status": "unfulfilled",
                },
            ),
        ],
    ),
    # --- Exemple 3 : Negative example (generiques => pas d'entite) ---
    lx.data.ExampleData(
        text=(
            "Il ramassa une epee rouilee par terre et la rangea dans son sac. "
            "La foret etait sombre et humide. Un batiment en ruine "
            "se dressait au loin, mais rien n'indiquait son nom."
        ),
        extractions=[
            # Aucune extraction : "une epee rouillee", "la foret",
            # "un batiment en ruine" sont des references generiques
            # sans noms propres.
        ],
    ),
]
