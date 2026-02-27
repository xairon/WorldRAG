"""Prompts V3 pour Phase 3 : Extraction d'entites specifiques a la serie.

Fournit la description de prompt et les exemples few-shot pour extraire
les entites definies dans l'ontologie Layer 3 (serie). Le schema est
injecte dynamiquement depuis le fichier YAML de la serie.

Exemple : Pour Primal Hunter, extrait Bloodline, Profession, PrimordialChurch,
AlchemyRecipe, Floor.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat)
# ---------------------------------------------------------------------------

PHASE = 3

PROMPT_DESCRIPTION = """\
Extrais TOUTES les entites specifiques a cette serie de ce chapitre.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms et descriptions en francais, exactement comme dans le texte
source. Ne traduis JAMAIS en anglais.

=== ENTITES SPECIFIQUES A LA SERIE ===
Le schema cible est injecte dynamiquement depuis l'ontologie Layer 3.
Consulte la section [SYSTEM] > Ontologie cible pour les types exacts.

=== GUIDE GENERAL ===

BLOODLINE (lignee de sang) :
- name : nom exact de la bloodline
- description : effets et nature de la bloodline
- owner_name : canonical_name du proprietaire
- effects : liste des effets
- origin : source ou patron lié

PROFESSION (profession / metier) :
- name : nom exact de la profession
- tier : tier si mentionne (common, uncommon, rare, epic, legendary, etc.)
- type : crafting, combat, utility, social
- description : ce que fait la profession
- owner : qui la possede

PRIMORDIAL_CHURCH (eglise / culte primordial) :
- deity_name : nom de la divinite ou du Primordial
- domain : domaine de la divinite
- blessing_effects : effets de la benediction si mentionnes

ALCHEMY_RECIPE (recette d'alchimie) :
- name : nom de la recette ou potion
- ingredients : liste des ingredients si mentionnes
- effects : effets de la potion / recette
- rarity : rarete si mentionnee

FLOOR (etage de donjon / instance) :
- number : numero de l'etage
- name : nom de l'etage si mentionne
- description : description ou caracteristiques
- dungeon_name : nom du donjon parent

=== REGLES D'EXTRACTION ===
- N'extrais QUE les types definis dans l'ontologie Layer 3 de cette serie.
- Les entites deja couvertes par les phases 1-2 (Character, Skill, etc.)
  ne doivent PAS etre re-extraites ici.
- Extrais dans l'ordre d'apparition.
- Si un type n'apparait pas dans le texte, ne l'invente pas.
"""

# Prompt systeme legacy (pour compatibilite)
SERIES_SYSTEM_PROMPT = PROMPT_DESCRIPTION

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Bloodline + Profession ---
    {
        "chapter_text": (
            "[Bloodline Awakened: Bloodline of the Primal Hunter]\n"
            "Jake sentit l'energie primordiale affluer en lui. La bloodline "
            "de son patron Primordial lui conferait une perception accrue "
            "et des instincts de chasseur. "
            "Plus tard, il verfia son statut de profession : "
            "Alchimiste du Vipere Malefique (Legendaire). "
            "Sa maitrise de l'alchimie progressait lentement mais surement."
        ),
        "result": {
            "bloodlines": [
                {
                    "name": "Bloodline of the Primal Hunter",
                    "description": "confere une perception accrue et des instincts de chasseur",
                    "effects": ["perception accrue", "instincts de chasseur"],
                    "origin": "patron Primordial",
                    "owner_name": "jake",
                },
            ],
            "professions": [
                {
                    "name": "Alchimiste du Vipere Malefique",
                    "tier": "legendary",
                    "type": "crafting",
                    "description": "profession d'alchimie liee au Vipere Malefique",
                    "owner": "jake",
                },
            ],
            "churches": [],
        },
    },
    # --- Exemple 2 : PrimordialChurch + Floor ---
    {
        "chapter_text": (
            "Le temple de Villy le Vipere Malefique se dressait au coeur "
            "de la cite. Ses fideles portaient des robes ecarlates. "
            "La benediction du Vipere conferait une resistance aux poisons. "
            "Jake atteignit le 57eme etage de Nevermore, un dedale "
            "peuple de golems d'obsidienne."
        ),
        "result": {
            "churches": [
                {
                    "deity_name": "Villy le Vipere Malefique",
                    "domain": "poison, alchimie",
                    "blessing_effects": ["resistance aux poisons"],
                },
            ],
            "floors": [
                {
                    "number": 57,
                    "name": "Etage 57",
                    "description": "dedale peuple de golems d'obsidienne",
                    "dungeon_name": "Nevermore",
                },
            ],
            "bloodlines": [],
            "professions": [],
        },
    },
    # --- Exemple 3 : Negative example ---
    {
        "chapter_text": (
            "Jake combattit pendant des heures, utilisant ses competences "
            "et sa classe pour progresser. Rien de specifique a sa lignee "
            "ou a sa profession ne se manifesta."
        ),
        "result": {
            "bloodlines": [],
            "professions": [],
            "churches": [],
            "floors": [],
        },
    },
]

# Legacy alias
SERIES_FEW_SHOT = FEW_SHOT_EXAMPLES
