"""Entity quality filter — reject noise, keep wiki-worthy entities.

Inspired by BookNLP, Wookieepedia, Forgotten Realms Wiki, and SIFT-KG.
Applies heuristic + regex filters to discard:
  - Pronouns and demonstratives (FR + EN)
  - Generic descriptors ("le guerrier", "un soldat")
  - Unnamed/generic items ("une epee", "a sword")
  - Relational descriptors ("Jake's girlfriend", "the hero's friend")
  - LLM commentary artifacts (parenthetical explanations, "null", "unknown")
  - Trivial events
  - Generic real-world concepts ("magie", "combat")

Each entity type has type-specific rules. Filtering runs post-extraction,
pre-persistence, so Neo4j only receives high-quality KG nodes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.schemas.extraction import ChapterExtractionResult

logger = get_logger(__name__)

# ── Max name length — anything longer is LLM hallucination/commentary ──

MAX_ENTITY_NAME_LENGTH = 80

# ── Pronouns (hard reject) ──────────────────────────────────────────

PRONOUNS: set[str] = {
    # French
    "il",
    "elle",
    "ils",
    "elles",
    "je",
    "tu",
    "nous",
    "vous",
    "on",
    "lui",
    "leur",
    "eux",
    "me",
    "te",
    "se",
    "soi",
    "celui",
    "celle",
    "ceux",
    "celles",
    "celui-ci",
    "celle-ci",
    "ceux-ci",
    "celles-ci",
    "celui-la",
    "celle-la",
    "ceux-la",
    "celles-la",
    "celui-là",
    "celle-là",
    "ceux-là",
    "celles-là",
    "ce",
    "ceci",
    "cela",
    "ca",
    "ça",
    "qui",
    "que",
    "quoi",
    "dont",
    "où",
    "y",
    "en",
    # English
    "he",
    "she",
    "it",
    "they",
    "him",
    "her",
    "them",
    "his",
    "hers",
    "its",
    "theirs",
    "this",
    "that",
    "these",
    "those",
    "who",
    "whom",
    "which",
    "what",
    "i",
    "we",
    "you",
    "us",
    "myself",
    "himself",
    "herself",
    "itself",
    "themselves",
}

# ── Garbage / LLM artifacts (hard reject for ALL entity types) ───────

GARBAGE_NAMES: set[str] = {
    "null",
    "none",
    "unknown",
    "n/a",
    "na",
    "undefined",
    "unnamed",
    "???",
    "...",
    "—",
    "-",
    "?",
}

# ── Generic character descriptors (hard reject) ─────────────────────

_GENERIC_CHAR_PATTERNS: list[re.Pattern[str]] = [
    # French article + generic noun: "le guerrier", "un soldat", "la créature"
    re.compile(
        r"^(?:le|la|l['']\s?|les|un|une|des|du|ce|cet|cette|ces|son|sa|ses|leur|leurs)\s+"
        r"(?:homme|femme|guerrier|guerrière|soldat|mage|sorcier|sorcière|"
        r"créature|monstre|ennemi|ennemie|assaillant|assaillante|étranger|étrangère|"
        r"inconnu|inconnue|individu|personne|enfant|vieillard|vieil\s+homme|"
        r"vieille\s+femme|garçon|fille|type|gars|mec|nana|"
        r"chose|bête|bete|animal|silhouette|ombre|figure|voix|"
        r"archer|manieur|lanceur|combattant|combattante|"
        r"blaireau|sanglier|marcassin|cochon|loup|ours|serpent|vipère|"
        r"premier|première|deuxième|troisième|quatrième|dernier|dernière|autre|"
        r"compagnon|compagne|ami|amie|allié|alliée|adversaire|rival|rivale)\b",
        re.IGNORECASE,
    ),
    # French ordinals: "le 2e", "la 3ème"
    re.compile(r"^(?:le|la)\s+\d+(?:er|ère|e|ème|ième)\b", re.IGNORECASE),
    # French demonstrative + noun: "cette chose", "cet homme"
    re.compile(
        r"^(?:ce|cet|cette|ces)\s+\w+",
        re.IGNORECASE,
    ),
    # English article + generic noun
    re.compile(
        r"^(?:the|a|an|some|this|that)\s+"
        r"(?:man|woman|warrior|soldier|mage|sorcerer|sorceress|"
        r"creature|monster|enemy|attacker|stranger|unknown|individual|person|"
        r"child|old\s+man|old\s+woman|boy|girl|guy|figure|shadow|voice|thing|"
        r"archer|axe\s+wielder|fighter|"
        r"beast|badger|boar|wolf|bear|snake|viper|"
        r"first|second|third|fourth|last|other|"
        r"companion|friend|ally|adversary|rival)\b",
        re.IGNORECASE,
    ),
    # English possessive relational descriptors: "Jake's girlfriend"
    re.compile(
        r"^.+[''']s\s+"
        r"(?:friend|best\s+friend|girlfriend|boyfriend|wife|husband|"
        r"ex-girlfriend|ex-boyfriend|ex-wife|ex-husband|ex-best\s+friend|"
        r"father|mother|brother|sister|son|daughter|"
        r"uncle|aunt|cousin|partner|"
        r"ally|companion|mentor|teacher|student|rival)\b",
        re.IGNORECASE,
    ),
    # Generic role words (standalone): "Protagonist", "Unnamed Protagonist"
    re.compile(
        r"^(?:unnamed|unknown|mysterious|anonymous|unidentified)?\s*"
        r"(?:protagonist|antagonist|hero|heroine|villain|narrator|"
        r"silhouette|figure|shadow|voice)\b",
        re.IGNORECASE,
    ),
    # "Parents" (standalone generic group)
    re.compile(r"^(?:parents|family|groupe|group)$", re.IGNORECASE),
]

# ── Generic item names (hard reject) ────────────────────────────────

_GENERIC_ITEM_PATTERNS: list[re.Pattern[str]] = [
    # French: "une épée", "des potions", "l'armure"
    re.compile(
        r"^(?:le|la|l['']\s?|les|un|une|des|du|son|sa|ses)\s+"
        r"(?:épée|epée|arme|potion|armure|bouclier|arc|flèche|fleche|"
        r"bâton|baton|anneau|pendentif|robe|bottes|gants|casque|sac|"
        r"clé|cle|livre|parchemin|pierre|cristal|fiole|baguette|"
        r"dague|lance|hache|masse|marteau|cape|tunique|ceinture|"
        r"épaulières|jambières|plastron|bracelet|collier|"
        r"carquois|munitions|flèches)\b",
        re.IGNORECASE,
    ),
    # English
    re.compile(
        r"^(?:the|a|an|some|his|her|their)\s+"
        r"(?:sword|weapon|potion|armor|shield|bow|arrow|staff|"
        r"ring|pendant|robe|boots|gloves|helmet|bag|key|book|scroll|"
        r"stone|crystal|vial|wand|dagger|spear|axe|mace|hammer|"
        r"cape|tunic|belt|quiver|ammunition)\b",
        re.IGNORECASE,
    ),
]

# ── Generic location names (hard reject) ────────────────────────────

_GENERIC_LOCATION_PATTERNS: list[re.Pattern[str]] = [
    # French article + generic location
    re.compile(
        r"^(?:le|la|l['']\s?|les|un|une|des|du)\s+"
        r"(?:forêt|foret|pièce|piece|salle|grotte|route|chemin|"
        r"ville|village|montagne|rivière|riviere|lac|mer|océan|ocean|"
        r"plaine|champ|colline|vallée|vallee|désert|desert|"
        r"maison|bâtiment|batiment|auberge|taverne|marché|marche|"
        r"arbre|buisson|rocher|pierre|clairière|clairiere|"
        r"sous-bois|bosquet|sentier|pont|mur|porte|"
        r"ascenseur|escalier|couloir|bureau|"
        r"pilier|dôme|dome)\b",
        re.IGNORECASE,
    ),
    # French demonstrative + location: "cette forêt", "ces bois"
    re.compile(
        r"^(?:ce|cet|cette|ces)\s+"
        r"(?:forêt|foret|bois|endroit|lieu|place|monde|"
        r"village|ville|montagne|salle|pièce|cave|grotte)\b",
        re.IGNORECASE,
    ),
    # French small/generic nature: "des arbres", "les bois", "sous-bois"
    re.compile(
        r"^(?:des|les)\s+"
        r"(?:arbres|bois|rochers|pierres|buissons|champs|collines)\b",
        re.IGNORECASE,
    ),
    # French: standalone small generic locations
    re.compile(
        r"^(?:sous-bois|open\s+space|rez-de-chaussée|rez-de-chausse)$",
        re.IGNORECASE,
    ),
    # French: "un(e) + adjective + location" → "une petite clairière"
    re.compile(
        r"^(?:un|une)\s+(?:petit|petite|grand|grande|énorme|immense|vaste|sombre|"
        r"vieux|vieille|ancien|ancienne)\s+",
        re.IGNORECASE,
    ),
    # Relative/directional
    re.compile(
        r"^(?:au\s+nord|au\s+sud|à\s+l['']\s?est|à\s+l['']\s?ouest|"
        r"north|south|east|west|nearby|outside|inside|dehors|dedans|"
        r"ici|là|là-bas|là-haut|ici-bas|ailleurs)\b",
        re.IGNORECASE,
    ),
    # English article + generic location
    re.compile(
        r"^(?:the|a|an)\s+"
        r"(?:forest|room|cave|road|path|city|town|village|"
        r"mountain|river|lake|sea|ocean|plain|field|hill|valley|desert|"
        r"house|building|inn|tavern|market|tree|bush|clearing)\b",
        re.IGNORECASE,
    ),
    # Generic meta-locations
    re.compile(
        r"^(?:current\s+location|unknown\s+|here-below|here|there)\b",
        re.IGNORECASE,
    ),
]

# ── Generic skill descriptions (hard reject) ────────────────────────

_GENERIC_SKILL_PATTERNS: list[re.Pattern[str]] = [
    # French: "compétence de/pour/d'..." (generic skill description, not a named skill)
    re.compile(
        r"^(?:compétence|competence|compétences|competences)\s+"
        r"(?:de|d['']\s?|pour|en)\s+",
        re.IGNORECASE,
    ),
    # French: "maniement d'armes..." (generic weapon proficiency)
    re.compile(
        r"^(?:maniement|maîtrise|maitrise|utilisation)\s+"
        r"(?:de|d['']\s?|des)\s+",
        re.IGNORECASE,
    ),
    # French: standalone weapon type (not a named skill)
    re.compile(
        r"^(?:les?\s+)?(?:armes?\s+(?:de\s+lancer|à\s+(?:deux|une)\s+mains?)|"
        r"(?:l['']\s?)?épée\s+et\s+(?:le\s+)?bouclier|"
        r"double\s+maniement\s+des?\s+armes?)\b",
        re.IGNORECASE,
    ),
    # Generic English skill descriptions
    re.compile(
        r"^(?:skill\s+(?:with|in|for|at)\s+|"
        r"proficiency\s+(?:with|in)\s+|"
        r"ability\s+to\s+)\b",
        re.IGNORECASE,
    ),
]

# ── Generic concepts (hard reject) ──────────────────────────────────

GENERIC_CONCEPTS: set[str] = {
    # French
    "magie",
    "puissance",
    "pouvoir",
    "force",
    "combat",
    "bataille",
    "guerre",
    "mort",
    "vie",
    "amour",
    "haine",
    "peur",
    "colère",
    "temps",
    "espace",
    "lumière",
    "lumiere",
    "obscurité",
    "obscurite",
    "bien",
    "mal",
    "nature",
    "énergie",
    "energie",
    "vitesse",
    "agilité",
    "agilite",
    "endurance",
    "intelligence",
    "sagesse",
    "charisme",
    "chance",
    "destin",
    "mana",
    "survie",
    "évolution",
    "evolution",
    "progression",
    "croissance",
    "récompense",
    "recompense",
    "punition",
    "danger",
    "sécurité",
    "securite",
    # English
    "magic",
    "power",
    "strength",
    "battle",
    "war",
    "death",
    "life",
    "love",
    "hate",
    "fear",
    "anger",
    "time",
    "space",
    "light",
    "darkness",
    "good",
    "evil",
    "energy",
    "speed",
    "agility",
    "wisdom",
    "charisma",
    "luck",
    "fate",
    "health",
    "stamina",
    "perception",
    "willpower",
    "toughness",
    "dexterity",
    "constitution",
    "vitality",
    "survival",
    "growth",
    "reward",
    "punishment",
    "safety",
}


# ── Filtering functions ─────────────────────────────────────────────


def _is_pronoun(name: str) -> bool:
    """Check if entity name is a pronoun or demonstrative."""
    return name.strip().lower() in PRONOUNS


def _is_garbage(name: str) -> bool:
    """Check if entity name is a known garbage/LLM artifact."""
    return name.strip().lower() in GARBAGE_NAMES


def _is_too_short(name: str) -> bool:
    """Names of 1 char or empty are noise."""
    stripped = name.strip()
    return len(stripped) <= 1


def _is_too_long(name: str) -> bool:
    """Names over MAX_ENTITY_NAME_LENGTH are LLM commentary, not entity names."""
    return len(name.strip()) > MAX_ENTITY_NAME_LENGTH


def _has_parenthetical(name: str) -> bool:
    """Names containing parenthetical text are LLM commentary artifacts.

    Examples: "Forest (implied by context...)", "here-below (ici-bas, implied...)"
    """
    return "(" in name and ")" in name


def _matches_any(name: str, patterns: list[re.Pattern[str]]) -> bool:
    """Check if name matches any of the given regex patterns."""
    return any(p.match(name.strip()) for p in patterns)


def _is_all_lowercase_single_word(name: str) -> bool:
    """Single lowercase word without any uppercase = likely not a proper name.

    Exception: known entity types that are lowercase by convention
    (e.g., skill names from system messages may be lowercase).
    """
    stripped = name.strip()
    if " " in stripped or "-" in stripped:
        return False
    return stripped == stripped.lower() and stripped.isalpha()


def _common_reject(name: str) -> bool:
    """Common rejection rules shared across all entity types."""
    if _is_pronoun(name):
        return True
    if _is_garbage(name):
        return True
    if _is_too_short(name):
        return True
    if _is_too_long(name):
        return True
    return bool(_has_parenthetical(name))


def filter_characters(result: ChapterExtractionResult) -> int:
    """Filter out noisy characters. Returns count of removed entities."""
    original = result.characters.characters
    filtered = []
    removed = 0

    for char in original:
        name = char.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        if _matches_any(name, _GENERIC_CHAR_PATTERNS):
            removed += 1
            continue
        # Single lowercase word is suspicious for a character
        if _is_all_lowercase_single_word(name) and len(name) < 4:
            removed += 1
            continue
        filtered.append(char)

    result.characters.characters = filtered

    # Also filter relationships involving removed characters
    kept_names = {c.name.lower() for c in filtered} | {
        c.canonical_name.lower() for c in filtered if c.canonical_name
    }
    original_rels = result.characters.relationships
    filtered_rels = []
    for rel in original_rels:
        src = rel.source.strip().lower()
        tgt = rel.target.strip().lower()
        if src in kept_names and tgt in kept_names:
            filtered_rels.append(rel)
        else:
            removed += 1
    result.characters.relationships = filtered_rels

    return removed


def filter_items(result: ChapterExtractionResult) -> int:
    """Filter out generic/unnamed items."""
    original = result.lore.items
    filtered = []
    removed = 0

    for item in original:
        name = item.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        if _matches_any(name, _GENERIC_ITEM_PATTERNS):
            removed += 1
            continue
        if _is_all_lowercase_single_word(name):
            removed += 1
            continue
        filtered.append(item)

    result.lore.items = filtered
    return removed


def filter_locations(result: ChapterExtractionResult) -> int:
    """Filter out generic/unnamed locations."""
    original = result.lore.locations
    filtered = []
    removed = 0

    for loc in original:
        name = loc.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        if _matches_any(name, _GENERIC_LOCATION_PATTERNS):
            removed += 1
            continue
        if _is_all_lowercase_single_word(name):
            removed += 1
            continue
        filtered.append(loc)

    result.lore.locations = filtered
    return removed


def filter_creatures(result: ChapterExtractionResult) -> int:
    """Filter out generic creature mentions."""
    original = result.lore.creatures
    filtered = []
    removed = 0

    for creature in original:
        name = creature.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        if _is_all_lowercase_single_word(name) and len(name) < 4:
            removed += 1
            continue
        filtered.append(creature)

    result.lore.creatures = filtered
    return removed


def filter_factions(result: ChapterExtractionResult) -> int:
    """Filter out generic group references."""
    original = result.lore.factions
    filtered = []
    removed = 0

    for faction in original:
        name = faction.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        # Generic group references
        if re.match(
            r"^(?:le|la|les|un|une|des|the|a|an)\s+"
            r"(?:soldats|gardes|ennemis|alliés|allies|foule|groupe|"
            r"soldiers|guards|enemies|allies|crowd|group)\b",
            name,
            re.IGNORECASE,
        ):
            removed += 1
            continue
        filtered.append(faction)

    result.lore.factions = filtered
    return removed


def filter_concepts(result: ChapterExtractionResult) -> int:
    """Filter out generic real-world concepts."""
    original = result.lore.concepts
    filtered = []
    removed = 0

    for concept in original:
        name = concept.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        if name.lower() in GENERIC_CONCEPTS:
            removed += 1
            continue
        # Single lowercase word concept is likely generic
        if _is_all_lowercase_single_word(name):
            removed += 1
            continue
        filtered.append(concept)

    result.lore.concepts = filtered
    return removed


def filter_skills(result: ChapterExtractionResult) -> int:
    """Filter out misidentified skills (generic descriptions, not named skills)."""
    original = result.systems.skills
    filtered = []
    removed = 0

    for skill in original:
        name = skill.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        # Generic skill descriptions: "compétence de/pour...", "maniement d'armes..."
        if _matches_any(name, _GENERIC_SKILL_PATTERNS):
            removed += 1
            continue
        # Single lowercase word is suspicious for a skill (likely a verb)
        if _is_all_lowercase_single_word(name) and len(name) < 5:
            removed += 1
            continue
        filtered.append(skill)

    result.systems.skills = filtered
    return removed


def filter_events(result: ChapterExtractionResult) -> int:
    """Filter out trivial events."""
    original = result.events.events
    filtered = []
    removed = 0

    for event in original:
        name = event.name.strip()
        if _common_reject(name):
            removed += 1
            continue
        # Trivial action patterns
        if re.match(
            r"^(?:il|elle|he|she|they|on|ils|elles)\s+"
            r"(?:marche|mange|dort|parle|walked|ate|slept|talked|sat|stood)\b",
            name,
            re.IGNORECASE,
        ):
            removed += 1
            continue
        filtered.append(event)

    result.events.events = filtered
    return removed


def filter_extraction_result(result: ChapterExtractionResult) -> dict[str, int]:
    """Apply all quality filters to a ChapterExtractionResult in-place.

    Returns a dict of removed entity counts per type for logging.
    """
    removed: dict[str, int] = {}
    removed["characters"] = filter_characters(result)
    removed["skills"] = filter_skills(result)
    removed["items"] = filter_items(result)
    removed["locations"] = filter_locations(result)
    removed["creatures"] = filter_creatures(result)
    removed["factions"] = filter_factions(result)
    removed["concepts"] = filter_concepts(result)
    removed["events"] = filter_events(result)

    total_removed = sum(removed.values())
    if total_removed > 0:
        logger.info(
            "entity_quality_filter_applied",
            total_removed=total_removed,
            book_id=result.book_id,
            chapter=result.chapter_number,
            **removed,
        )

    # Recount total entities after filtering
    result.total_entities = result.count_entities()

    return removed
