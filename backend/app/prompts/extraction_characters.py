"""Prompts V3 pour Phase 1 : Extraction de Personnages & Relations.

Fournit la description de prompt et les exemples few-shot pour extraire
les personnages, factions, et relations (RELATES_TO, MEMBER_OF) du texte
narratif. Ontologie cible : Character, Faction, RELATES_TO, MEMBER_OF.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

import langextract as lx

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/characters.py)
# ---------------------------------------------------------------------------

PHASE = 1

PROMPT_DESCRIPTION = """\
Extrais TOUS les personnages, factions et relations de ce chapitre.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Tu DOIS extraire
tous les noms, descriptions et attributs en francais, exactement comme ils
apparaissent dans le texte source. Ne traduis JAMAIS en anglais.

=== TYPES D'ENTITES CIBLES (Ontologie V3) ===

CHARACTER :
- name : le nom principal utilise dans le texte (orthographe exacte)
- canonical_name : le nom complet du personnage en minuscules, sans articles
- role : protagonist, antagonist, mentor, sidekick, ally, minor, neutral
- species : race ou espece si mentionnee
- aliases : liste de surnoms ou noms alternatifs
- description : breve description du personnage dans le contexte

FACTION :
- name : nom exact de la faction ou organisation
- type : guilde, ordre, clan, alliance, gouvernement, race, eglise
- alignment : disposition ou alignement si evident
- description : ce qu'on apprend sur cette faction

RELATES_TO (relation entre personnages) :
- source : nom du personnage source
- target : nom du personnage cible
- type : ally, enemy, mentor, family, romantic, rival, patron, subordinate
- subtype : precision (pere, mere, frere, soeur, epoux, etc.) si applicable
- sentiment : valeur de -1.0 (hostile) a 1.0 (amical) si estimable
- context : bref contexte tire du texte

MEMBER_OF (appartenance a une faction) :
- source : nom du personnage
- target : nom de la faction
- role : leader, member, founder, defector

=== REGLES D'EXTRACTION ===
- Extrais les entites dans l'ordre d'apparition dans le texte.
- Utilise les noms EXACTS tels qu'ils apparaissent dans le texte.
- NE CREE PAS d'entites pour des references generiques (le guerrier, l'ennemi, il, elle).
  Seuls les personnages NOMMES sont des entites.
- NE CREE PAS d'entites pour des descriptions relationnelles (la copine de Jake,
  le pere de Caroline). Utilise plutot une RELATION entre les personnages nommes.
- Inclus les personnages mineurs seulement mentionnes, pas uniquement ceux qui parlent.
- Pour les relations, extrais uniquement celles explicitement declarees ou clairement impliquees.
- Si un personnage est deja dans le registre d'entites, REFERENCIE-LE par son
  canonical_name existant plutot que d'en creer un nouveau.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Golden example (cas standard, multiple personnages + relations) ---
    lx.data.ExampleData(
        text=(
            "Jake banda son arc, canalisant Powershot vers la bete. "
            "\u00ab Attention ! \u00bb avertit Jacob dans son esprit. "
            "\u00ab C'est un Sanglier Dentdefer. \u00bb "
            "Caroline observait depuis la clairiere, prete a intervenir "
            "avec ses sorts de soin. "
            "Casper, lui, restait en retrait, son bouclier leve. "
            "Tous les quatre faisaient partie du Groupe de Survivants "
            "forme au debut du tutoriel."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Jake",
                attributes={
                    "canonical_name": "jake",
                    "role": "protagonist",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Jacob",
                attributes={
                    "canonical_name": "jacob",
                    "role": "mentor",
                    "description": "communique par telepathie avec Jake",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Caroline",
                attributes={
                    "canonical_name": "caroline",
                    "role": "ally",
                    "description": "soigneuse, capable de sorts de soin",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Casper",
                attributes={
                    "canonical_name": "casper",
                    "role": "ally",
                },
            ),
            lx.data.Extraction(
                extraction_class="faction",
                extraction_text="Groupe de Survivants",
                attributes={
                    "name": "Groupe de Survivants",
                    "type": "alliance",
                    "description": "groupe forme au debut du tutoriel",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Jacob dans son esprit",
                attributes={
                    "source": "jacob",
                    "target": "jake",
                    "type": "mentor",
                    "context": "Jacob guide Jake par telepathie",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Caroline observait depuis la clairiere, prete a intervenir",
                attributes={
                    "source": "caroline",
                    "target": "jake",
                    "type": "ally",
                    "sentiment": "0.7",
                    "context": "Caroline soutient Jake en combat avec ses soins",
                },
            ),
            lx.data.Extraction(
                extraction_class="membership",
                extraction_text="Tous les quatre faisaient partie du Groupe de Survivants",
                attributes={
                    "source": "jake",
                    "target": "Groupe de Survivants",
                    "role": "member",
                },
            ),
        ],
    ),
    # --- Exemple 2 : Edge case (mentions indirectes, personnage absent) ---
    lx.data.ExampleData(
        text=(
            "Dennis frappa le sol de sa hache, l'onde de choc repoussant les blaireaux. "
            "Sa collegue, Joanna, aurait desapprouve de telles methodes. "
            "Mais elle etait a l'autre bout de la foret, s'entrainant avec Bertram. "
            "Les trois avaient ete recrutes par la Guilde des Veilleurs, "
            "bien que Dennis n'en soit pas encore membre officiel."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Dennis",
                attributes={
                    "canonical_name": "dennis",
                    "role": "ally",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Joanna",
                attributes={
                    "canonical_name": "joanna",
                    "role": "ally",
                    "description": "collegue de Dennis",
                },
            ),
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="Bertram",
                attributes={
                    "canonical_name": "bertram",
                    "role": "ally",
                },
            ),
            lx.data.Extraction(
                extraction_class="faction",
                extraction_text="Guilde des Veilleurs",
                attributes={
                    "name": "Guilde des Veilleurs",
                    "type": "guilde",
                },
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Sa collegue, Joanna",
                attributes={
                    "source": "dennis",
                    "target": "joanna",
                    "type": "ally",
                    "subtype": "collegue",
                },
            ),
            lx.data.Extraction(
                extraction_class="membership",
                extraction_text="recrutes par la Guilde des Veilleurs",
                attributes={
                    "source": "joanna",
                    "target": "Guilde des Veilleurs",
                    "role": "member",
                },
            ),
            lx.data.Extraction(
                extraction_class="membership",
                extraction_text="recrutes par la Guilde des Veilleurs",
                attributes={
                    "source": "bertram",
                    "target": "Guilde des Veilleurs",
                    "role": "member",
                },
            ),
        ],
    ),
]
