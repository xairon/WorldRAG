"""Prompts V3 pour Phase 3 : Auto-decouverte de nouveaux types d'entites.

Identifie des types d'entites recurrents dans le texte qui ne sont PAS
couverts par l'ontologie actuelle (Layers 1-3). Propose des extensions
au schema pour les phases futures.

Ce module sert de mecanisme de feedback pour enrichir l'ontologie
au fil de l'extraction.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes exportees
# ---------------------------------------------------------------------------

PHASE = 3

PROMPT_DESCRIPTION = """\
Tu es un expert en modelisation d'ontologies pour la fiction narrative.

Analyse ce chapitre et identifie les types d'entites recurrents ou
importants qui ne sont PAS couverts par l'ontologie actuelle.

=== ONTOLOGIE ACTUELLE ===
L'ontologie cible est injectee dans le [SYSTEM]. Consulte-la pour
connaitre les types deja couverts.

=== OBJECTIF ===
Detecter les LACUNES de l'ontologie : des concepts recurrents dans le
texte qui meriteraient un type d'entite dedie mais qui n'existent pas
encore dans le schema.

=== TYPES DE DECOUVERTES ===
1. **Nouveau type d'entite** : un concept recurrent qui n'a pas de type
   dedie (ex: "Dungeon" dans un LitRPG qui n'a pas ce type)
2. **Nouvelle propriete** : une propriete manquante sur un type existant
   (ex: "alignment_moral" sur Character)
3. **Nouvelle relation** : un type de relation non couvert
   (ex: "RIVALS_WITH" entre Factions)

=== SCHEMA DE SORTIE (JSON) ===
{{
  "discovered_types": [
    {{
      "name": "<nom du type propose>",
      "category": "entity|property|relationship",
      "layer": "core|genre|series",
      "description": "<pourquoi ce type est necessaire>",
      "evidence_count": <nombre de mentions dans le chapitre>,
      "evidence_samples": ["<extrait 1>", "<extrait 2>"],
      "proposed_schema": {{
        "properties": {{
          "<prop_name>": {{"type": "<type>", "description": "<desc>"}}
        }}
      }}
    }}
  ],
  "confidence": <0.0 a 1.0 pour l'ensemble>
}}

=== REGLES ===
- NE PROPOSE PAS de types deja couverts par l'ontologie.
- Un type doit apparaitre au moins 2 fois dans le chapitre pour etre propose.
- Privilegier les types qui seraient utiles pour PLUSIEURS chapitres.
- Qualite > quantite : preferer 1-2 decouvertes solides plutot que 10 vagues.
- Si aucune lacune n'est detectee, retourner une liste vide.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Decouverte d'un type manquant ---
    {
        "ontology_types": [
            "Character",
            "Skill",
            "Class",
            "Title",
            "Event",
            "Location",
            "Item",
            "Creature",
            "Faction",
            "Concept",
        ],
        "chapter_text": (
            "Jake entra dans le Donjon du Sanglier, un espace cree par le Systeme. "
            "Le donjon avait 3 etages, chacun avec des monstres plus forts. "
            "Au deuxieme etage, il trouva un coffre de donjon contenant une "
            "arme rare. Le troisieme etage abritait le boss, l'Alpha Dentdefer. "
            "Une fois le donjon termine, il recut une recompense de donjon."
        ),
        "result": {
            "discovered_types": [
                {
                    "name": "Dungeon",
                    "category": "entity",
                    "layer": "genre",
                    "description": (
                        "Les donjons sont des instances de combat structurees "
                        "avec des etages, des boss et des recompenses. Concept "
                        "recurrent dans les LitRPG non couvert par Location."
                    ),
                    "evidence_count": 5,
                    "evidence_samples": [
                        "Jake entra dans le Donjon du Sanglier",
                        "Le donjon avait 3 etages",
                        "il recut une recompense de donjon",
                    ],
                    "proposed_schema": {
                        "properties": {
                            "name": {"type": "string", "description": "nom du donjon"},
                            "floor_count": {"type": "integer", "description": "nombre d'etages"},
                            "difficulty_grade": {
                                "type": "string",
                                "description": "grade de difficulte",
                            },
                            "boss_name": {"type": "string", "description": "nom du boss final"},
                            "location_name": {"type": "string", "description": "lieu parent"},
                        },
                    },
                },
            ],
            "confidence": 0.85,
        },
    },
    # --- Exemple 2 : Aucune decouverte necessaire ---
    {
        "ontology_types": [
            "Character",
            "Skill",
            "Class",
            "Title",
            "Event",
            "Location",
            "Item",
            "Creature",
            "Faction",
            "Concept",
            "Bloodline",
            "Profession",
            "PrimordialChurch",
        ],
        "chapter_text": (
            "Jake s'entraina avec son arc, ameliorant sa competence Powershot. "
            "Caroline soigna ses blessures. Ils discuterent de leur prochaine "
            "destination et deciderent de se rendre a la Citadelle."
        ),
        "result": {
            "discovered_types": [],
            "confidence": 0.95,
        },
    },
]
