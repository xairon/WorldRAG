"""Prompts V3 pour Phase 2 : Extraction de Creatures & Races.

Fournit la description de prompt et les exemples few-shot pour extraire
les creatures, races, monstres et bestiaire du texte narratif.
Ontologie cible : Creature, Race, System (quand lie aux creatures).

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

import langextract as lx

# ---------------------------------------------------------------------------
# Constantes exportees
# ---------------------------------------------------------------------------

PHASE = 2

PROMPT_DESCRIPTION = """\
Extrais TOUTES les creatures, races et monstres de ce chapitre.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms et descriptions en francais, exactement comme dans le texte
source. Ne traduis JAMAIS en anglais.

=== TYPES D'ENTITES CIBLES (Ontologie V3) ===

CREATURE (creature / monstre) :
- name : nom de la creature ou espece tel qu'ecrit dans le texte
- description : description physique ou comportementale si disponible
- species : categorie d'espece plus large si mentionnee
- threat_level : grade ou niveau de danger si mentionne (F-grade, E-grade, etc.)
- habitat : ou elle vit si mentionne

RACE (race intelligente) :
- name : nom de la race
- description : caracteristiques principales
- traits : traits distinctifs de la race si mentionnes
- typical_abilities : capacites typiques de la race si mentionnees

SYSTEM (systeme lie aux creatures, si mentionne) :
- name : nom du systeme regissant les creatures
- description : comment le systeme interagit avec les creatures
- system_type : cultivation, class_based, skill_based, stat_based, hybrid

=== REGLES D'EXTRACTION ===
- NE CREE PAS d'entite pour des creatures generiques (les betes, des animaux,
  les monstres). Seules les ESPECES NOMMEES sont des entites.
- NE CREE PAS d'entite pour des individus uniques si leur espece est deja
  extraite. Extrais l'ESPECE, pas l'individu (sauf boss nommes).
- Si une creature est un boss avec un nom unique, extrais-la comme Creature
  avec son nom propre.
- Distingue les RACES (intelligentes, civilisees) des CREATURES (non-intelligentes).
- Si le grade de danger (F-grade, E-grade, D-grade, etc.) est mentionne,
  inclus-le dans threat_level.
- Extrais dans l'ordre d'apparition.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Golden example (creatures + race + boss nomme) ---
    lx.data.ExampleData(
        text=(
            "Les Sangliers Dentdefer grognaient dans les fourres, leurs defenses "
            "luisant d'un eclat metallique. C'etaient des creatures de grade F, "
            "les plus faibles du tutoriel. "
            "Plus loin, un Alpha Dentdefer massif gardait le passage. "
            "D'apres Jacob, les Elfes de l'Ether avaient jadis apprivoise "
            "ces betes pour la guerre."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="creature",
                extraction_text="Sangliers Dentdefer",
                attributes={
                    "name": "Sanglier Dentdefer",
                    "species": "sanglier",
                    "threat_level": "F-grade",
                    "description": "defenses metalliques luisantes, creatures du tutoriel",
                },
            ),
            lx.data.Extraction(
                extraction_class="creature",
                extraction_text="Alpha Dentdefer",
                attributes={
                    "name": "Alpha Dentdefer",
                    "species": "Sanglier Dentdefer",
                    "description": "specimen massif gardant le passage, boss",
                },
            ),
            lx.data.Extraction(
                extraction_class="race",
                extraction_text="Elfes de l'Ether",
                attributes={
                    "name": "Elfes de l'Ether",
                    "description": "race ayant jadis apprivoise les Sangliers Dentdefer",
                    "typical_abilities": "dressage de creatures",
                },
            ),
        ],
    ),
    # --- Exemple 2 : Creature de haut grade + systeme ---
    lx.data.ExampleData(
        text=(
            "La Vouivre Ecarlate deployait ses ailes, chaque battement "
            "generant des bourrasques brulantes. C'etait une creature de grade D, "
            "bien au-dessus du niveau de Jake. "
            "Le Systeme classifiait automatiquement les creatures selon leur "
            "puissance en grades, de F a SSS."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="creature",
                extraction_text="Vouivre Ecarlate",
                attributes={
                    "name": "Vouivre Ecarlate",
                    "species": "vouivre",
                    "threat_level": "D-grade",
                    "description": (
                        "creature ailee generant des bourrasques brulantes, "
                        "bien au-dessus du niveau de Jake"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="system",
                extraction_text=("Le Systeme classifiait automatiquement les creatures"),
                attributes={
                    "name": "Systeme de classification des creatures",
                    "description": (
                        "classifie automatiquement les creatures par grade de puissance, de F a SSS"
                    ),
                    "system_type": "stat_based",
                },
            ),
        ],
    ),
    # --- Exemple 3 : Negative example (generiques) ---
    lx.data.ExampleData(
        text=(
            "Des betes sauvages rodaient dans la foret. Il croisa quelques "
            "insectes geants et des animaux etranges, mais rien de memorable."
        ),
        extractions=[
            # Aucune extraction : "betes sauvages", "insectes geants",
            # "animaux etranges" sont des descriptions generiques sans
            # noms d'especes propres.
        ],
    ),
]
