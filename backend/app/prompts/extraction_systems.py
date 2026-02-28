"""Prompts V3 pour Phase 2 : Extraction de Systemes & Progression.

Fournit la description de prompt et les exemples few-shot pour extraire
les competences, classes, titres, niveaux, et changements de stats.
Ontologie cible : Skill, Class, Title, Level, StatBlock.

Inclut le guidage pour le parsing des blue boxes et la reference croisee
avec les indices Phase 0 (regex).

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

import langextract as lx

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/systems.py)
# ---------------------------------------------------------------------------

PHASE = 2

PROMPT_DESCRIPTION = """\
Extrais TOUS les elements de systeme de jeu et de progression de ce chapitre.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms de competences, classes, titres en francais, exactement comme
ils apparaissent dans le texte source. Ne traduis JAMAIS en anglais.

=== TYPES D'ENTITES CIBLES (Ontologie V3) ===

SKILL (competence / aptitude) :
- name : nom exact de la competence tel qu'ecrit dans le texte
- skill_type : active, passive, racial, class, profession, unique
- rank : common, uncommon, rare, epic, legendary, transcendent, divine
- owner : personnage qui possede ou acquiert la competence
- effects : description de ce que fait la competence
- system_name : nom du systeme si mentionne

CLASS (classe / profession de combat) :
- name : nom exact de la classe
- tier : niveau de la classe si mentionne (entier)
- owner : qui possede cette classe
- requirements : conditions d'obtention si mentionnees
- description : details supplementaires

TITLE (titre) :
- name : nom exact du titre
- effects : effets du titre si mentionnes
- owner : qui a gagne le titre
- requirements : conditions si indiquees

LEVEL (changement de niveau) :
- character : personnage qui a gagne un niveau
- old_level : ancien niveau (entier)
- new_level : nouveau niveau (entier)
- realm : grade/rang si mentionne (F-grade, E-grade, etc.)

STAT_CHANGE (changement de statistique) :
- stat_name : nom de la stat (Force, Agilite, Intelligence, Perception, etc.)
- value : montant du changement (entier)
- character : personnage affecte

=== GUIDE BLUE BOXES ===
Les romans LitRPG contiennent des notifications systeme entre crochets [] ou
dans des blocs encadres. Ces blue boxes sont des sources de haute confiance :
- [Skill Acquired: Nom - Rarete] => Skill
- Level: X -> Y => Level change
- +N Stat => Stat change
- [Title earned: Nom] => Title
- Class: Nom (Tier) => Class

IMPORTANT : Les indices Phase 0 (regex) dans le CONTEXTE contiennent des
extractions automatiques de ces blue boxes. Utilise-les pour CONFIRMER tes
extractions narratives mais ne les copie pas aveuglement. Le texte narratif
autour des blue boxes contient souvent des details supplementaires (owner,
effets, contexte).

=== REGLES D'EXTRACTION ===
- Extrais des NOTIFICATIONS (blue boxes) ET du texte narratif.
- Utilise les noms EXACTS tels qu'ecrits (preserve majuscules, espaces, accents).
- Lie chaque competence/classe/titre a son proprietaire.
- NE CREE PAS d'entite pour des descriptions generiques (competence de combat,
  maniement d'armes) — seuls les noms PROPRES de competences sont des entites.
- Distingue les nouvelles acquisitions des references a des elements existants.
- Extrais dans l'ordre d'apparition.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Golden example (blue box + narration + stats) ---
    lx.data.ExampleData(
        text=(
            "[Competence acquise : \u0152il de l'Archer \u2013 Rare]\n"
            "Jake sentit le pouvoir affluer en lui. Sa perception s'aiguisa, "
            "chaque detail de la foret devenant net.\n\n"
            "+5 Perception\n+3 Agilite\n\n"
            "Sa classe d'Archer bourdonna en approbation. Au niveau 12, "
            "il debloquait enfin cette aptitude passive tant attendue."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="skill",
                extraction_text="\u0152il de l'Archer",
                attributes={
                    "name": "\u0152il de l'Archer",
                    "rank": "rare",
                    "owner": "jake",
                    "skill_type": "passive",
                    "effects": "aiguise la perception, chaque detail devient net",
                },
            ),
            lx.data.Extraction(
                extraction_class="stat_change",
                extraction_text="+5 Perception",
                attributes={
                    "stat_name": "Perception",
                    "value": "5",
                    "character": "jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="stat_change",
                extraction_text="+3 Agilite",
                attributes={
                    "stat_name": "Agilite",
                    "value": "3",
                    "character": "jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="class",
                extraction_text="Archer",
                attributes={
                    "name": "Archer",
                    "owner": "jake",
                    "description": "classe existante, pas nouvellement acquise",
                },
            ),
        ],
    ),
    # --- Exemple 2 : Evolution de classe + titre (blue box formel) ---
    lx.data.ExampleData(
        text=(
            "Niveau : 3 -> 5\n"
            "Classe : Chasseur Ambitieux\n\n"
            "Titre obtenu : Pionnier du Nouveau Monde\n"
            "Effet : +10% de degats contre les creatures du tutoriel.\n\n"
            "Jake sourit. Le titre confirmait ce que le Vilain Vipere "
            "lui avait laisse entendre : il etait special."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="level_change",
                extraction_text="Niveau : 3 -> 5",
                attributes={
                    "character": "jake",
                    "old_level": "3",
                    "new_level": "5",
                },
            ),
            lx.data.Extraction(
                extraction_class="class",
                extraction_text="Chasseur Ambitieux",
                attributes={
                    "name": "Chasseur Ambitieux",
                    "owner": "jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="title",
                extraction_text="Pionnier du Nouveau Monde",
                attributes={
                    "name": "Pionnier du Nouveau Monde",
                    "owner": "jake",
                    "effects": "+10% de degats contre les creatures du tutoriel",
                },
            ),
        ],
    ),
]
