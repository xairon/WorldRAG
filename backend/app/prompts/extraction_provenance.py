"""Prompts V3 pour Phase 2b : Extraction de provenance des competences.

Identifie quels objets, classes, bloodlines ou titres conferent
des competences specifiques.

Optimise pour les romans LitRPG en francais (Primal Hunter).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes exportees (backward-compat avec services/extraction/provenance.py)
# ---------------------------------------------------------------------------

PHASE = 2

PROMPT_DESCRIPTION = """\
Tu es un analyste de systemes LitRPG. Identifie la SOURCE de chaque
competence acquise dans ce chapitre.
"""

PROVENANCE_SYSTEM_PROMPT = """\
Tu es un analyste de systemes LitRPG. Etant donne un extrait de chapitre
et une liste de competences acquises dans ce chapitre, identifie la SOURCE
de chaque competence.

=== TYPES DE SOURCES ===
- item : un equipement ou artefact confere la competence
- class : une classe ou un metier fournit la competence
- bloodline : une bloodline manifeste la competence
- title : un titre confere la competence
- profession : une profession (alchimie, forgerie, etc.) donne la competence
- unknown : la source n'est pas mentionnee ou est floue

=== SCHEMA DE SORTIE (JSON) ===
Pour chaque competence, retourne :
{{
  "skill_name": "<nom exact de la competence>",
  "source_type": "item|class|bloodline|title|profession|unknown",
  "source_name": "<nom de la source>",
  "confidence": <0.0 a 1.0>,
  "context": "<extrait du texte justifiant l'attribution>"
}}

=== REGLES ===
- Ne rapporte que les attributions avec une confiance >= 0.5.
- Si aucune source n'est evidente, utilise "unknown".
- Chaque attribution DOIT avoir un extrait textuel (context) comme preuve.
- Ne confonds pas les competences existantes avec les nouvelles acquisitions.
"""

FEW_SHOT_EXAMPLES = [
    # --- Exemple 1 : Source = objet ---
    {
        "chapter_text": (
            "Jake equipa le Nanoblade, sentant sa puissance affluer en lui.\n"
            "[Competence acquise : Frappe de l'Ombre - Rare]\n"
            "L'enchantement de la lame lui conferait une nouvelle technique de combat."
        ),
        "skills": ["Frappe de l'Ombre"],
        "result": [
            {
                "skill_name": "Frappe de l'Ombre",
                "source_type": "item",
                "source_name": "Nanoblade",
                "confidence": 0.95,
                "context": "L'enchantement de la lame lui conferait une nouvelle technique de combat.",
            },
        ],
    },
    # --- Exemple 2 : Source = evolution de classe ---
    {
        "chapter_text": (
            "Avec son evolution en Chasseur Arcanique Avide, Jake acceda a "
            "tout un nouvel ensemble de capacites.\n"
            "[Competence acquise : Powershot Arcanique - Epique]"
        ),
        "skills": ["Powershot Arcanique"],
        "result": [
            {
                "skill_name": "Powershot Arcanique",
                "source_type": "class",
                "source_name": "Chasseur Arcanique Avide",
                "confidence": 0.9,
                "context": (
                    "Avec son evolution en Chasseur Arcanique Avide, "
                    "Jake acceda a tout un nouvel ensemble de capacites"
                ),
            },
        ],
    },
]

# Legacy alias
PROVENANCE_FEW_SHOT = FEW_SHOT_EXAMPLES
