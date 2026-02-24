"""Golden ground truth data from The Primal Hunter wiki.

Source: https://the-primal-hunter.fandom.com/wiki/The_Primal_Hunter_Wiki

This module provides verified entity data scraped from the official wiki.
Used as ground truth for extraction pipeline validation: if our pipeline
can't find Jake Thayne or the Malefic Viper in chapter text that mentions
them, something is broken.

These are NOT exhaustive — they are representative samples chosen to cover
every entity type the extraction pipeline handles.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Characters ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenCharacter:
    """Verified character data from the wiki."""

    name: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    species: str = "Human"
    role: str = "minor"
    grade: str = ""
    faction: str = ""


CHARACTERS: list[GoldenCharacter] = [
    GoldenCharacter(
        name="Jake Thayne",
        canonical_name="Jake Thayne",
        aliases=(
            "The Hunter",
            "Harbinger of Primeval Origins",
            "Lord Thayne",
            "Doomfoot",
            "Doombringer",
            "Progenitor",
        ),
        species="Human",
        role="protagonist",
        grade="B",
        faction="Haven",
    ),
    GoldenCharacter(
        name="Vilastromoz",
        canonical_name="Vilastromoz",
        aliases=(
            "The Malefic Viper",
            "Villy",
            "The Malefic One",
            "Vilas",
            "Strolas",
        ),
        species="Primordial",
        role="mentor",
        grade="God",
        faction="Order of the Malefic Viper",
    ),
    GoldenCharacter(
        name="Miranda Wells",
        canonical_name="Miranda Wells",
        aliases=("Miranda",),
        species="Human",
        role="ally",
        grade="B",
        faction="Haven",
    ),
    GoldenCharacter(
        name="Caleb Thayne",
        canonical_name="Caleb Thayne",
        aliases=("CT", "The Judge", "Cal"),
        species="Human",
        role="ally",
        grade="C",
        faction="Court of Shadows",
    ),
    GoldenCharacter(
        name="Sylphie",
        canonical_name="Sylphie",
        aliases=(),
        species="Sylphian Eyas",
        role="sidekick",
    ),
    GoldenCharacter(
        name="Duskleaf",
        canonical_name="Duskleaf",
        aliases=(),
        species="Unknown",
        role="mentor",
        faction="Order of the Malefic Viper",
    ),
    GoldenCharacter(
        name="Hank",
        canonical_name="Hank",
        aliases=(),
        species="Human",
        role="ally",
        faction="Haven",
    ),
    GoldenCharacter(
        name="Arnold",
        canonical_name="Arnold",
        aliases=(),
        species="Human",
        role="ally",
        faction="Haven",
    ),
    GoldenCharacter(
        name="Carmen",
        canonical_name="Carmen",
        aliases=(),
        species="Human",
        role="ally",
    ),
    GoldenCharacter(
        name="Ell'Hakan",
        canonical_name="Ell'Hakan",
        aliases=(),
        species="Unknown",
        role="antagonist",
    ),
    GoldenCharacter(
        name="Eversmile",
        canonical_name="Eversmile",
        aliases=(),
        species="God",
        role="neutral",
    ),
]

CHARACTER_NAMES: frozenset[str] = frozenset(c.canonical_name for c in CHARACTERS)

# Characters that MUST be found when their name appears in text (high recall targets)
MUST_FIND_CHARACTERS: frozenset[str] = frozenset(
    {
        "Jake Thayne",
        "Vilastromoz",
        "Miranda Wells",
        "Caleb Thayne",
        "Sylphie",
    }
)


# ── Skills ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenSkill:
    """Verified skill data from the wiki."""

    name: str
    owner: str = ""
    rank: str = ""
    skill_type: str = ""


SKILLS: list[GoldenSkill] = [
    GoldenSkill(name="Gaze of the Apex Predator", owner="Jake Thayne"),
    GoldenSkill(name="Archer's Eye", owner="Jake Thayne"),
    GoldenSkill(name="Basic Archery", owner="Jake Thayne", rank="Inferior"),
    GoldenSkill(name="Mark of the Ambitious Hunter", owner="Jake Thayne"),
    GoldenSkill(name="Touch of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Scales of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Palate of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Fangs of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Blood of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Wings of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Sense of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Sagacity of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Pride of the Malefic Viper", owner="Jake Thayne"),
    GoldenSkill(name="Shroud of the Primordial", owner="Vilastromoz"),
    GoldenSkill(name="One Step Mile", owner="Jake Thayne"),
    GoldenSkill(name="Identify", owner="Jake Thayne"),
    GoldenSkill(name="Alchemical Flame", owner="Jake Thayne"),
    GoldenSkill(
        name="Dreams of the Verdant Lagoon",
        owner="Miranda Wells",
        rank="Legendary",
    ),
    GoldenSkill(name="Moment of the Primal Hunter", owner="Jake Thayne"),
    GoldenSkill(name="Event Horizon", owner="Jake Thayne"),
]

SKILL_NAMES: frozenset[str] = frozenset(s.name for s in SKILLS)


# ── Classes ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenClass:
    """Verified class data from the wiki."""

    name: str
    owner: str = ""
    grade: str = ""


CLASSES: list[GoldenClass] = [
    GoldenClass(name="Archer", owner="Jake Thayne", grade="F"),
    GoldenClass(name="Ambitious Hunter", owner="Jake Thayne", grade="E"),
    GoldenClass(name="Avaricious Arcane Hunter", owner="Jake Thayne", grade="D"),
    GoldenClass(name="Arcane Hunter of Horizon's Edge", owner="Jake Thayne", grade="C"),
    GoldenClass(
        name="Arcane Hunter of the Boundless Horizon",
        owner="Jake Thayne",
        grade="B",
    ),
    GoldenClass(name="Caster", owner="Miranda Wells", grade="F"),
    GoldenClass(name="Legacy Class of Tenlucis", owner="Caleb Thayne", grade="C"),
    GoldenClass(name="Healer"),
    GoldenClass(name="Metal Savant"),
    GoldenClass(name="Warrior (Heavy)"),
    GoldenClass(name="Warrior (Light)"),
    GoldenClass(name="Warrior (Medium)"),
]

CLASS_NAMES: frozenset[str] = frozenset(c.name for c in CLASSES)


# ── Titles ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenTitle:
    """Verified title data from the wiki."""

    name: str
    owner: str = ""


TITLES: list[GoldenTitle] = [
    GoldenTitle(name="Forerunner of the New World", owner="Jake Thayne"),
    GoldenTitle(name="Bloodline Patriarch", owner="Jake Thayne"),
    GoldenTitle(name="Holder of a Primordial's True Blessing", owner="Jake Thayne"),
    GoldenTitle(name="Kingslayer", owner="Jake Thayne"),
    GoldenTitle(name="Premier Treasure Hunter", owner="Jake Thayne"),
    GoldenTitle(name="Myth Originator", owner="Jake Thayne"),
    GoldenTitle(name="Dragonslayer", owner="Jake Thayne"),
    GoldenTitle(name="Peerless Conqueror of Nevermore", owner="Jake Thayne"),
    GoldenTitle(name="Progenitor of the 93rd Universe", owner="Jake Thayne"),
    GoldenTitle(name="Perfect Evolution (D-grade)", owner="Jake Thayne"),
    GoldenTitle(name="Perfect Evolution (C-grade)", owner="Jake Thayne"),
    GoldenTitle(name="Perfect Evolution (B-grade)", owner="Jake Thayne"),
    GoldenTitle(name="Sacred Prodigy", owner="Jake Thayne"),
    GoldenTitle(name="Forerunner of the New World", owner="Miranda Wells"),
    GoldenTitle(
        name="Holder of a Godqueen's Divine Blessing",
        owner="Miranda Wells",
    ),
    GoldenTitle(name="Forerunner of the New World", owner="Caleb Thayne"),
]

TITLE_NAMES: frozenset[str] = frozenset(t.name for t in TITLES)


# ── Factions ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenFaction:
    """Verified faction data from the wiki."""

    name: str
    faction_type: str = ""
    leader: str = ""


FACTIONS: list[GoldenFaction] = [
    GoldenFaction(
        name="Haven",
        faction_type="city",
        leader="Jake Thayne",
    ),
    GoldenFaction(
        name="Order of the Malefic Viper",
        faction_type="organization",
        leader="Vilastromoz",
    ),
    GoldenFaction(
        name="Court of Shadows",
        faction_type="organization",
        leader="Caleb Thayne",
    ),
    GoldenFaction(name="The Holy Church", faction_type="organization"),
    GoldenFaction(name="Valhal", faction_type="organization"),
    GoldenFaction(name="Pantheon of Life", faction_type="organization"),
    GoldenFaction(name="Empire of Blight", faction_type="organization"),
]

FACTION_NAMES: frozenset[str] = frozenset(f.name for f in FACTIONS)


# ── Locations ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenLocation:
    """Verified location data from the wiki."""

    name: str
    location_type: str = ""


LOCATIONS: list[GoldenLocation] = [
    GoldenLocation(name="Haven", location_type="city"),
    GoldenLocation(name="Nevermore", location_type="dungeon"),
    GoldenLocation(name="Earth", location_type="planet"),
    GoldenLocation(name="Skyggen", location_type="city"),
]

LOCATION_NAMES: frozenset[str] = frozenset(loc.name for loc in LOCATIONS)


# ── Relationships ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class GoldenRelationship:
    """Verified relationship from the wiki."""

    source: str
    target: str
    rel_type: str
    subtype: str = ""


RELATIONSHIPS: list[GoldenRelationship] = [
    GoldenRelationship(
        source="Jake Thayne",
        target="Vilastromoz",
        rel_type="patron",
        subtype="True Blessing",
    ),
    GoldenRelationship(
        source="Jake Thayne",
        target="Caleb Thayne",
        rel_type="family",
        subtype="brothers",
    ),
    GoldenRelationship(
        source="Jake Thayne",
        target="Sylphie",
        rel_type="family",
        subtype="creator",
    ),
    GoldenRelationship(
        source="Jake Thayne",
        target="Miranda Wells",
        rel_type="ally",
        subtype="political",
    ),
    GoldenRelationship(
        source="Jake Thayne",
        target="Duskleaf",
        rel_type="mentor",
    ),
    GoldenRelationship(
        source="Jake Thayne",
        target="Artemis",
        rel_type="romantic",
    ),
    GoldenRelationship(
        source="Vilastromoz",
        target="Duskleaf",
        rel_type="patron",
        subtype="former blessed",
    ),
    GoldenRelationship(
        source="Caleb Thayne",
        target="Maja",
        rel_type="romantic",
        subtype="married",
    ),
    GoldenRelationship(
        source="Miranda Wells",
        target="Hank",
        rel_type="ally",
        subtype="friendship",
    ),
]


# ── Concepts ────────────────────────────────────────────────────────────


CONCEPTS: list[dict[str, str]] = [
    {
        "name": "The System",
        "domain": "magic",
        "description": "The multiverse system that governs classes, skills, and levels",
    },
    {
        "name": "Grades",
        "domain": "progression",
        "description": "Power tiers from F through S-grade and God",
    },
    {
        "name": "Blessing",
        "domain": "divine",
        "description": (
            "Divine blessing from gods with tiers: "
            "Minor, Lesser, Intermediate, Major, Greater, Divine, True"
        ),
    },
    {
        "name": "Bloodline",
        "domain": "racial",
        "description": "Innate bloodline ability, Jake's is Bloodline of the Primal Hunter",
    },
    {
        "name": "Transcendent",
        "domain": "progression",
        "description": "Highest form of skill mastery",
    },
    {
        "name": "Tutorial",
        "domain": "system",
        "description": "Initial survival event when a new universe is integrated",
    },
]


# ── Aggregate helpers ───────────────────────────────────────────────────


ALL_ENTITY_NAMES: frozenset[str] = (
    CHARACTER_NAMES | SKILL_NAMES | CLASS_NAMES | TITLE_NAMES | FACTION_NAMES | LOCATION_NAMES
)


@dataclass(frozen=True)
class GoldenChapterExpectation:
    """What we expect the pipeline to extract from a specific chapter."""

    chapter_number: int
    expected_characters: frozenset[str] = field(default_factory=frozenset)
    expected_skills: frozenset[str] = field(default_factory=frozenset)
    expected_classes: frozenset[str] = field(default_factory=frozenset)
    expected_titles: frozenset[str] = field(default_factory=frozenset)
    expected_events: frozenset[str] = field(default_factory=frozenset)
    expected_locations: frozenset[str] = field(default_factory=frozenset)
    expected_factions: frozenset[str] = field(default_factory=frozenset)
    min_entity_count: int = 1
