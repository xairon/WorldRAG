"""Unified extraction prompts for WorldRAG v4 single-pass pipeline.

Two prompts replace the 4 domain-specific V3 prompts:
- Step 1 (entities): all 15 entity types in a flat array
- Step 2 (relations): all 16 relation types using Step 1 entities as context
"""

from __future__ import annotations

from app.prompts.base import build_extraction_prompt

# ---------------------------------------------------------------------------
# Step 1 — Entity extraction
# ---------------------------------------------------------------------------

ENTITY_PROMPT_DESCRIPTION = """\
Extrais TOUTES les entités narratives de ce chapitre en une seule passe.

Ce roman est en FRANCAIS (LitRPG / progression fantasy). Extraire tous les noms,
descriptions et attributs exactement comme ils apparaissent dans le texte source.
Ne jamais traduire en anglais.

=== TYPES D'ENTITÉS CIBLES (Ontologie V4 — 15 types) ===

--- Couche 1 : Entités narratives universelles ---

CHARACTER :
- name : nom principal utilisé dans le texte (orthographe exacte)
- canonical_name : nom complet en minuscules, sans articles
- role : protagonist | antagonist | mentor | sidekick | ally | minor | neutral
- species : race ou espèce si mentionnée
- aliases : liste de surnoms ou noms alternatifs
- description : brève description dans le contexte du chapitre
- extraction_text : passage source exact d'où l'entité est tirée
- char_start / char_end : offsets de caractères dans le chunk

EVENT :
- name : nom ou titre court de l'événement
- canonical_name : identifiant en minuscules
- event_type : battle | discovery | leveling | death | revelation | encounter | other
- participants : liste de noms de personnages impliqués
- outcome : résultat ou conséquence de l'événement
- chapter_ref : numéro de chapitre si disponible
- extraction_text, char_start, char_end

LOCATION :
- name : nom du lieu tel qu'il apparaît
- canonical_name : identifiant en minuscules
- location_type : city | dungeon | region | building | wilderness | realm | other
- description : caractéristiques notables du lieu
- extraction_text, char_start, char_end

ITEM :
- name : nom de l'objet
- canonical_name : identifiant en minuscules
- item_type : weapon | armor | consumable | artifact | currency | material | other
- rarity : common | uncommon | rare | epic | legendary | unique | mythic
- description : propriétés ou effets notables
- extraction_text, char_start, char_end

ARC :
- name : nom de l'arc narratif
- canonical_name : identifiant en minuscules
- arc_type : main | side | character | world
- status : active | completed | foreshadowed
- description : résumé de l'arc
- extraction_text, char_start, char_end

--- Couche 2 : Entités LitRPG / progression fantasy ---

CLASS :
- name : nom de la classe (ex. "Chasseur Primal", "Berserker")
- canonical_name : identifiant en minuscules
- tier : rang ou niveau de prestige si mentionné
- description : capacités ou traits associés
- extraction_text, char_start, char_end

SKILL :
- name : nom exact de la compétence ou capacité
- canonical_name : identifiant en minuscules
- skill_type : active | passive | aura | ultimate | racial | class_skill
- level : niveau de la compétence si indiqué
- description : effet ou mécanique de la compétence
- owner : nom du personnage possédant cette compétence
- extraction_text, char_start, char_end

STAT :
- name : nom de la statistique (ex. "Force", "Vitalité", "Mana")
- canonical_name : identifiant en minuscules
- value : valeur numérique actuelle si présente
- base_value : valeur de base avant bonus
- owner : nom du personnage associé
- extraction_text, char_start, char_end

TITLE :
- name : titre conféré au personnage (ex. "Tueur de Démons", "Roi des Ombres")
- canonical_name : identifiant en minuscules
- tier : rang du titre si indiqué
- effects : bonus ou pouvoirs conférés par le titre
- owner : nom du personnage ayant reçu ce titre
- extraction_text, char_start, char_end

LEVEL :
- canonical_name : "level_{owner}" en minuscules
- value : niveau numérique (ex. 42)
- owner : nom du personnage
- previous_value : niveau précédent si une montée de niveau est décrite
- extraction_text, char_start, char_end

SYSTEM :
- name : nom du système de jeu ou de magie (ex. "Le Système", "Akashic Records")
- canonical_name : identifiant en minuscules
- system_type : game_system | magic_system | divine_system | other
- description : règles ou mécaniques décrites
- extraction_text, char_start, char_end

FACTION :
- name : nom de la faction ou organisation
- canonical_name : identifiant en minuscules
- faction_type : guild | order | clan | alliance | government | race | church | other
- alignment : disposition si évidente
- description : rôle et caractéristiques de la faction
- extraction_text, char_start, char_end

--- Couche 3 : Entités spécifiques à la série ---

BLOODLINE :
- name : nom du lignage ou héritage (ex. "Lignée des Anciens", "Sang de Dragon")
- canonical_name : identifiant en minuscules
- tier : rang ou puissance du lignage
- abilities : capacités héritées par ce lignage
- owner : personnage porteur de ce lignage
- extraction_text, char_start, char_end

PROFESSION :
- name : nom de la profession ou métier secondaire
- canonical_name : identifiant en minuscules
- profession_type : crafting | gathering | support | combat | other
- level : niveau de la profession si indiqué
- owner : nom du personnage
- extraction_text, char_start, char_end

QUEST :
- name : titre ou description de la quête
- canonical_name : identifiant en minuscules
- quest_type : main | side | daily | hidden | world
- status : active | completed | failed | available
- reward : récompense décrite
- extraction_text, char_start, char_end

=== BOÎTES BLEUES (Phase 0) ===

Si des indices Phase 0 sont fournis dans [CONTEXTE] (regex bluebox), les entités
correspondantes (stats, skills, levels, titles) DOIVENT être extraites en priorité.
Les valeurs numériques précises des boîtes bleues ont la priorité sur le texte narratif.

=== ANCRAGE TEXTUEL ===

- extraction_text : copier EXACTEMENT le passage source sans modification
- char_start / char_end : offsets de caractères depuis le début du chunk
- Si impossible à déterminer avec précision, omettre char_start/char_end plutôt qu'inventer

=== RÈGLES DE QUALITÉ ===

- Extraire uniquement ce qui est explicitement dans le texte (pas d'inférence excessive)
- canonical_name toujours en minuscules, sans articles (le/la/les/un/une/the/a/an)
- Ne jamais fusionner deux entités différentes en une seule
- Un personnage mentionné plusieurs fois = une seule entité CHARACTER
- Chaque skill, stat, title = entité séparée même si lié au même personnage
- Score de confiance (confidence) : 0.0 à 1.0 selon certitude d'extraction
- Retourner un tableau JSON plat : [{entity_type: "character", ...}, ...]
"""

# ---------------------------------------------------------------------------
# Step 2 — Relation extraction
# ---------------------------------------------------------------------------

RELATION_PROMPT_DESCRIPTION = """\
Extrais TOUTES les relations narratives entre les entités déjà identifiées.

Les entités disponibles sont fournies dans [ENTITÉS EXTRAITES]. Utilise leurs
canonical_name pour les champs source et target. Ne pas créer de nouvelles entités.

=== TYPES DE RELATIONS (16 types) ===

--- Relations entre personnages ---

RELATES_TO (Character → Character) :
- source, target : canonical_name des personnages
- relation_type : ally | enemy | mentor | family | romantic | rival | patron | subordinate
- subtype : père, mère, frère, sœur, époux, etc. si applicable
- sentiment : -1.0 (hostile) à 1.0 (amical)
- context : bref contexte tiré du texte
- extraction_text, char_start, char_end

MEMBER_OF (Character → Faction) :
- source : canonical_name du personnage
- target : canonical_name de la faction
- role : rang ou rôle au sein de la faction
- extraction_text, char_start, char_end

--- Relations personnage ↔ entités de système ---

HAS_SKILL (Character → Skill) :
- source : canonical_name du personnage
- target : canonical_name du skill
- acquisition_chapter : chapitre d'acquisition si précisé
- extraction_text, char_start, char_end

HAS_CLASS (Character → Class) :
- source : canonical_name du personnage
- target : canonical_name de la classe
- acquisition_chapter : chapitre si précisé
- extraction_text, char_start, char_end

HAS_TITLE (Character → Title) :
- source : canonical_name du personnage
- target : canonical_name du titre
- extraction_text, char_start, char_end

HAS_BLOODLINE (Character → Bloodline) :
- source : canonical_name du personnage
- target : canonical_name du lignage
- extraction_text, char_start, char_end

HAS_PROFESSION (Character → Profession) :
- source : canonical_name du personnage
- target : canonical_name de la profession
- extraction_text, char_start, char_end

OWNS (Character → Item) :
- source : canonical_name du personnage
- target : canonical_name de l'objet
- acquisition_method : looted | crafted | gifted | purchased | other
- extraction_text, char_start, char_end

PARTICIPATES_IN (Character → Event) :
- source : canonical_name du personnage
- target : canonical_name de l'événement
- role : protagonist | antagonist | witness | victim | other
- extraction_text, char_start, char_end

LOCATED_IN (Character | Faction | Event → Location) :
- source : canonical_name de l'entité
- target : canonical_name du lieu
- extraction_text, char_start, char_end

--- Relations structurelles ---

PART_OF (Location | Faction → Location | Faction) :
- source : canonical_name de l'entité enfant
- target : canonical_name de l'entité parente
- extraction_text, char_start, char_end

LEADS_TO (Event → Event) :
- source : canonical_name de l'événement déclencheur
- target : canonical_name de l'événement résultant
- extraction_text, char_start, char_end

PART_OF_ARC (Event | Character → Arc) :
- source : canonical_name de l'entité
- target : canonical_name de l'arc
- extraction_text, char_start, char_end

GOVERNED_BY (Location | Faction → Character | Faction) :
- source : entité gouvernée
- target : entité qui gouverne
- extraction_text, char_start, char_end

QUEST_GIVER (Character → Quest) :
- source : canonical_name du personnage donneur de quête
- target : canonical_name de la quête
- extraction_text, char_start, char_end

QUEST_TARGET (Character → Quest) :
- source : canonical_name du personnage ciblé par la quête
- target : canonical_name de la quête
- extraction_text, char_start, char_end

=== INVALIDATION TEMPORELLE ===

Si le texte indique explicitement qu'une relation prend fin dans ce chapitre
(mort, rupture, trahison, fin de contrat, etc.), ajouter un objet RelationEnd :

RelationEnd :
- relation_type : type de relation terminée (HAS_SKILL, RELATES_TO, etc.)
- source : canonical_name de la source
- target : canonical_name de la cible
- end_reason : death | betrayal | skill_lost | quest_completed | other
- end_chapter : numéro du chapitre si disponible
- extraction_text, char_start, char_end

Retourner deux tableaux JSON :
{
  "relations": [...],
  "ended_relations": [...]
}

=== RÈGLES SOURCE/TARGET ===

- source et target doivent correspondre EXACTEMENT à un canonical_name des entités extraites
- Ne pas créer de relations vers des entités non présentes dans [ENTITÉS EXTRAITES]
- Ne pas dupliquer les relations (même source + target + type = une seule relation)
- Confidence : 0.0 à 1.0 selon certitude de la relation dans le texte
"""

# ---------------------------------------------------------------------------
# Few-shot examples
# ---------------------------------------------------------------------------

ENTITY_FEW_SHOT_FR = """\
Exemple d'entrée :
---
Jake ouvrit les yeux. Son niveau venait de passer à 42. Une nouvelle compétence
"Frappe Foudroyante" apparut dans sa liste. Il se trouvait dans la Caverne des Ombres,
un donjon de rang B réputé pour ses pièges mortels.
[Niveau 42 atteint !]
[Nouvelle compétence : Frappe Foudroyante (Active) — Déclenche une attaque chargée
d'éclairs infligeant 300% des dégâts de base.]
---

Exemple de sortie :
```json
[
  {
    "entity_type": "character",
    "name": "Jake",
    "canonical_name": "jake",
    "role": "protagonist",
    "confidence": 0.98,
    "extraction_text": "Jake ouvrit les yeux.",
    "char_start": 0,
    "char_end": 21
  },
  {
    "entity_type": "level",
    "canonical_name": "level_jake",
    "value": 42,
    "owner": "jake",
    "confidence": 0.99,
    "extraction_text": "Son niveau venait de passer à 42.",
    "char_start": 22,
    "char_end": 55
  },
  {
    "entity_type": "skill",
    "name": "Frappe Foudroyante",
    "canonical_name": "frappe foudroyante",
    "skill_type": "active",
    "description": "Déclenche une attaque chargée d'éclairs infligeant 300% des dégâts de base.",
    "owner": "jake",
    "confidence": 0.99,
    "extraction_text": "Frappe Foudroyante (Active) — Déclenche une attaque chargée d'éclairs infligeant 300% des dégâts de base.",
    "char_start": 180,
    "char_end": 284
  },
  {
    "entity_type": "location",
    "name": "Caverne des Ombres",
    "canonical_name": "caverne des ombres",
    "location_type": "dungeon",
    "description": "Donjon de rang B réputé pour ses pièges mortels.",
    "confidence": 0.95,
    "extraction_text": "la Caverne des Ombres, un donjon de rang B réputé pour ses pièges mortels.",
    "char_start": 102,
    "char_end": 174
  },
  {
    "entity_type": "event",
    "name": "Montée au niveau 42",
    "canonical_name": "montée au niveau 42",
    "event_type": "leveling",
    "participants": ["jake"],
    "outcome": "Jake atteint le niveau 42 et acquiert la compétence Frappe Foudroyante.",
    "confidence": 0.97,
    "extraction_text": "Son niveau venait de passer à 42. Une nouvelle compétence \"Frappe Foudroyante\" apparut dans sa liste.",
    "char_start": 22,
    "char_end": 121
  }
]
```
"""

RELATION_FEW_SHOT_FR = """\
Exemple d'entrée (entités déjà extraites) :
```json
[
  {"entity_type": "character", "canonical_name": "jake"},
  {"entity_type": "character", "canonical_name": "aria"},
  {"entity_type": "skill", "canonical_name": "frappe foudroyante"},
  {"entity_type": "faction", "canonical_name": "guilde des chasseurs"},
  {"entity_type": "event", "canonical_name": "siège de la forteresse"}
]
```

Texte : Jake et Aria étaient alliés au sein de la Guilde des Chasseurs. Jake venait
de maîtriser la Frappe Foudroyante durant le siège de la forteresse. Hélas, Aria
perdit sa compétence "Bouclier Arcanique" après avoir été maudite.

Exemple de sortie :
```json
{
  "relations": [
    {
      "relation_type": "RELATES_TO",
      "source": "jake",
      "target": "aria",
      "relation_subtype": "ally",
      "sentiment": 0.8,
      "context": "Jake et Aria étaient alliés",
      "confidence": 0.92,
      "extraction_text": "Jake et Aria étaient alliés au sein de la Guilde des Chasseurs."
    },
    {
      "relation_type": "MEMBER_OF",
      "source": "jake",
      "target": "guilde des chasseurs",
      "confidence": 0.95,
      "extraction_text": "au sein de la Guilde des Chasseurs"
    },
    {
      "relation_type": "MEMBER_OF",
      "source": "aria",
      "target": "guilde des chasseurs",
      "confidence": 0.90,
      "extraction_text": "Jake et Aria étaient alliés au sein de la Guilde des Chasseurs."
    },
    {
      "relation_type": "HAS_SKILL",
      "source": "jake",
      "target": "frappe foudroyante",
      "confidence": 0.97,
      "extraction_text": "Jake venait de maîtriser la Frappe Foudroyante"
    },
    {
      "relation_type": "PARTICIPATES_IN",
      "source": "jake",
      "target": "siège de la forteresse",
      "role": "protagonist",
      "confidence": 0.88,
      "extraction_text": "durant le siège de la forteresse"
    }
  ],
  "ended_relations": [
    {
      "relation_type": "HAS_SKILL",
      "source": "aria",
      "target": "bouclier arcanique",
      "end_reason": "skill_lost",
      "end_chapter": null,
      "confidence": 0.85,
      "extraction_text": "Aria perdit sa compétence \"Bouclier Arcanique\" après avoir été maudite."
    }
  ]
}
```
"""

# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_entity_prompt(
    registry_context: str = "",
    phase0_hints: list[dict] | None = None,
    router_hints: list[str] | None = None,
    language: str = "fr",
) -> str:
    """Build the Step 1 entity extraction prompt."""
    return build_extraction_prompt(
        phase="entities",
        role_description=(
            "un expert en extraction d'information pour Knowledge Graphs narratifs, "
            "spécialisé dans la fiction LitRPG et progression fantasy"
        ),
        ontology_schema={},  # types described inline in task_instructions
        task_instructions=ENTITY_PROMPT_DESCRIPTION if language == "fr" else "",
        entity_registry_context=registry_context,
        phase0_hints=phase0_hints,
        router_hints=router_hints,
        few_shot_examples=ENTITY_FEW_SHOT_FR if language == "fr" else "",
        language=language,
    )


def build_relation_prompt(
    chapter_text: str = "",
    entities_json: str = "",
    language: str = "fr",
) -> str:
    """Build the Step 2 relation extraction prompt."""
    return build_extraction_prompt(
        phase="relations",
        role_description="un expert en analyse de relations narratives pour Knowledge Graphs",
        ontology_schema={},
        task_instructions=RELATION_PROMPT_DESCRIPTION if language == "fr" else "",
        extracted_entities_json=entities_json,
        few_shot_examples=RELATION_FEW_SHOT_FR if language == "fr" else "",
        language=language,
    )
