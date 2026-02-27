"""Prompts V3 pour Phase 1 : Extraction d'Evenements & Arcs narratifs.

Fournit la description de prompt et les exemples few-shot pour extraire
les evenements narratifs, arcs, ordonnancement temporel et significance.
Ontologie cible : Event, Arc, PARTICIPATES_IN, OCCURS_AT, CAUSES, PART_OF.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

import langextract as lx

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/events.py)
# ---------------------------------------------------------------------------

PHASE = 1

PROMPT_DESCRIPTION = """\
Extrais TOUS les evenements narratifs significatifs de ce chapitre.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS ecrire
tous les noms d'evenements, descriptions et attributs en francais.
Ne traduis JAMAIS en anglais.

=== TYPES D'ENTITES CIBLES (Ontologie V3) ===

EVENT :
- name : un nom court et descriptif EN FRANCAIS (2-6 mots)
- description : ce qui s'est passe (1-2 phrases en francais)
- event_type : action, state_change, achievement, process, dialogue
- significance : minor, moderate, major, critical, arc_defining
- participants : liste des noms canoniques de personnages impliques
- location : ou ca s'est passe (si mentionne)
- is_flashback : true si l'evenement est narre comme un souvenir passe
- fabula_order : ordre chronologique dans l'univers si different de l'ordre narratif

ARC (arc narratif) :
- name : nom de l'arc (2-5 mots)
- description : resume de l'arc
- arc_type : main_plot, subplot, character_arc, world_arc
- status : active, completed, abandoned

=== GUIDE DES TYPES D'EVENEMENTS ===
- action : un personnage fait quelque chose (combat, lance un sort, se deplace)
- state_change : un changement d'etat (alliance, pouvoir gagne, lieu change)
- achievement : une etape atteinte (montee de niveau, evolution de classe)
- process : une activite en cours (entrainement, fabrication, voyage)
- dialogue : une conversation significative qui revele des informations

=== GUIDE DE SIGNIFICANCE ===
- minor : evenements de contexte, actions mineures
- moderate : developpement de personnage, utilisation de competence
- major : batailles importantes, revelations cles, montees en puissance
- critical : morts, trahisons majeures, moments qui changent l'arc narratif
- arc_defining : evenements qui definissent ou concluent un arc narratif

=== ORDONNANCEMENT TEMPOREL ===
- Capture les evenements dans l'ORDRE CHRONOLOGIQUE du texte.
- Pour les flashbacks, mets is_flashback=true et estime fabula_order
  pour indiquer quand l'evenement s'est reellement produit.
- Si un evenement CAUSE un autre, cree une relation CAUSES entre eux.
- Si un evenement fait partie d'un arc, cree une relation PART_OF.

=== REGLES D'EXTRACTION ===
- NE SUR-EXTRAIS PAS : combine les micro-actions liees en un seul evenement.
- Chaque evenement doit etre une unite semantiquement complete.
- Inclus TOUS les participants par leur nom canonique.
- Extrais les arcs seulement quand le texte indique clairement un debut,
  une progression majeure ou une conclusion d'arc.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Golden example (combat + achievement + dialogue) ---
    lx.data.ExampleData(
        text=(
            "Le Sanglier Dentdefer chargea, ses defenses luisant dans la penombre. "
            "Jake encocha une fleche, canalisant Powershot. "
            "La fleche transperca ses defenses et toucha au but. "
            "La bete s'effondra, et une notification apparut : "
            "[Boss du tutoriel vaincu]\n"
            "Caroline accourut pour soigner ses blessures. "
            "\u00ab C'etait imprudent \u00bb, dit Casper en emergeant des fourres."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Jake encocha une fleche, canalisant Powershot",
                attributes={
                    "name": "Jake vainc le Sanglier Dentdefer",
                    "event_type": "action",
                    "significance": "major",
                    "participants": "jake, caroline, casper",
                    "description": (
                        "Jake utilise Powershot pour tuer le Sanglier Dentdefer, "
                        "boss du tutoriel"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Boss du tutoriel vaincu",
                attributes={
                    "name": "Boss du tutoriel elimine",
                    "event_type": "achievement",
                    "significance": "major",
                    "participants": "jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="\u00ab C'etait imprudent \u00bb, dit Casper",
                attributes={
                    "name": "Casper critique Jake",
                    "event_type": "dialogue",
                    "significance": "minor",
                    "participants": "casper, jake",
                    "description": "Casper reproche a Jake son imprudence au combat",
                },
            ),
        ],
    ),
    # --- Exemple 2 : Flashback + arc_defining + relation CAUSES ---
    lx.data.ExampleData(
        text=(
            "Jake se rappela le jour ou tout avait change. Le Systeme etait apparu "
            "sans prevenir, plongeant la Terre dans le chaos. Des millions de gens "
            "avaient ete projetes dans le tutoriel. "
            "Maintenant, debout dans la Grande Foret, il jura de survivre. "
            "C'etait le debut de son chemin vers la puissance."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="event",
                extraction_text=(
                    "Le Systeme etait apparu sans prevenir, plongeant la Terre "
                    "dans le chaos"
                ),
                attributes={
                    "name": "Apparition du Systeme sur Terre",
                    "event_type": "state_change",
                    "significance": "arc_defining",
                    "participants": "jake",
                    "is_flashback": "true",
                    "description": (
                        "Le Systeme apparait sur Terre, plongeant le monde dans "
                        "le chaos et envoyant des millions dans le tutoriel"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="debout dans la Grande Foret, il jura de survivre",
                attributes={
                    "name": "Serment de Jake",
                    "event_type": "state_change",
                    "significance": "major",
                    "participants": "jake",
                    "location": "la grande foret",
                    "description": (
                        "Jake jure de survivre dans la Grande Foret du tutoriel"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="arc",
                extraction_text="C'etait le debut de son chemin vers la puissance",
                attributes={
                    "name": "Ascension de Jake",
                    "arc_type": "main_plot",
                    "status": "active",
                    "description": (
                        "Arc principal : la quete de Jake pour devenir plus "
                        "puissant apres l'arrivee du Systeme"
                    ),
                },
            ),
        ],
    ),
    # --- Exemple 3 : Negative example (pas de sur-extraction) ---
    lx.data.ExampleData(
        text=(
            "Jake marcha pendant des heures. Il ramassa quelques baies, "
            "but a un ruisseau et s'assit pour se reposer. "
            "Rien de notable ne se passa."
        ),
        extractions=[
            # Un seul evenement resume, pas de micro-extraction pour chaque action.
            lx.data.Extraction(
                extraction_class="event",
                extraction_text="Jake marcha pendant des heures",
                attributes={
                    "name": "Jake traverse la foret",
                    "event_type": "process",
                    "significance": "minor",
                    "participants": "jake",
                    "description": (
                        "Jake marche longuement a travers la foret, "
                        "s'arretant pour se ravitailler"
                    ),
                },
            ),
        ],
    ),
]
