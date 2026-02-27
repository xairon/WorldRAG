"""Second pass cleanup — remove remaining noise entities.

Targets:
  - Creatures-as-characters (Vipère Maléfique, Cochon géant, etc.)
  - Generic items (armure de cuir, arc en bois)
  - Generic creatures (animaux, bêtes, insectes)
  - Generic classes (guerriers, null, évolution de classe)
  - Duplicate characters (Jake Thayne = Jake)
  - Long descriptive names
  - Plurals (blaireaux/blaireau)
  - Generic locations (Tree, Forêt, chez ses parents)

Usage: uv run python scripts/cleanup_entities_v2.py
"""

from __future__ import annotations

import asyncio

from neo4j import AsyncGraphDatabase

from app.config import settings


async def run_cleanup(s, label: str, description: str, query: str, params: dict | None = None):
    """Run a cleanup query and report results."""
    r = await s.run(query, params or {})
    data = await r.data()
    cnt = data[0]["removed"] if data else 0
    if cnt > 0:
        print(f"  [{label}] Removed {cnt}: {description}")
    return cnt


async def main() -> None:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    total = 0

    async with driver.session() as s:
        # ══════════════════════════════════════════════════════════
        # CHARACTERS
        # ══════════════════════════════════════════════════════════
        print("=== Characters ===")

        # Creatures mis-classified as characters
        creature_chars = [
            "Vipère Maléfique",
            "Cochon géant II – édition Dentdacier",
            "Mère Tanière",
            "Crocdevenin",
            "Blaireau",
            "Blaireautin",
        ]
        total += await run_cleanup(
            s,
            "Character",
            "creature-as-character",
            "MATCH (c:Character) WHERE c.canonical_name IN $names "
            "DETACH DELETE c RETURN count(c) as removed",
            {"names": creature_chars},
        )

        # Long descriptive character names (>40 chars)
        total += await run_cleanup(
            s,
            "Character",
            "long descriptive names (>40 chars)",
            "MATCH (c:Character) WHERE size(c.canonical_name) > 40 "
            "DETACH DELETE c RETURN count(c) as removed",
        )

        # Duplicate: Jake Thayne = Jake (merge relationships into Jake)
        total += await run_cleanup(
            s,
            "Character",
            "Jake Thayne duplicate (keep Jake)",
            "MATCH (c:Character {canonical_name: 'Jake Thayne'}) "
            "DETACH DELETE c RETURN count(c) as removed",
        )

        # ══════════════════════════════════════════════════════════
        # LOCATIONS
        # ══════════════════════════════════════════════════════════
        print("\n=== Locations ===")

        bad_locs = [
            "Tree",
            "Perch",
            "Forêt",
            "chez ses parents",
            "grandes villes",
            "bureaux de la société",
        ]
        total += await run_cleanup(
            s,
            "Location",
            "generic/relative locations",
            "MATCH (l:Location) WHERE l.name IN $names DETACH DELETE l RETURN count(l) as removed",
            {"names": bad_locs},
        )

        # All-lowercase multi-word location names are likely generic
        total += await run_cleanup(
            s,
            "Location",
            "all-lowercase locations (generic descriptions)",
            "MATCH (l:Location) WHERE l.name = toLower(l.name) "
            "AND l.name CONTAINS ' ' "
            "DETACH DELETE l RETURN count(l) as removed",
        )

        # ══════════════════════════════════════════════════════════
        # ITEMS
        # ══════════════════════════════════════════════════════════
        print("\n=== Items ===")

        bad_items = [
            "Le pilier",  # location, not item
            "feuilles de tableurs",  # not a game item
            "chemises habillées",  # not a game item
        ]
        total += await run_cleanup(
            s,
            "Item",
            "non-items by name",
            "MATCH (i:Item) WHERE i.name IN $names DETACH DELETE i RETURN count(i) as removed",
            {"names": bad_items},
        )

        # Generic all-lowercase items (arc en bois, armure de cuir, etc.)
        total += await run_cleanup(
            s,
            "Item",
            "all-lowercase generic items",
            "MATCH (i:Item) WHERE i.name = toLower(i.name) "
            "AND i.name CONTAINS ' ' "
            "DETACH DELETE i RETURN count(i) as removed",
        )

        # ══════════════════════════════════════════════════════════
        # CREATURES
        # ══════════════════════════════════════════════════════════
        print("\n=== Creatures ===")

        bad_creatures = [
            "Humain",
            "Humain (G)",
            "humains",
            "race humaine",
            "la bête",
            "bêtes",
            "animaux de petite taille",
            "petits animaux",
            "insectes",
            "larves",
            "gros rongeurs",
            "oiseaux",
        ]
        total += await run_cleanup(
            s,
            "Creature",
            "generic/human creatures",
            "MATCH (cr:Creature) WHERE cr.name IN $names "
            "DETACH DELETE cr RETURN count(cr) as removed",
            {"names": bad_creatures},
        )

        # LLM uncertainty artifact
        total += await run_cleanup(
            s,
            "Creature",
            "LLM uncertainty artifact",
            "MATCH (cr:Creature) WHERE cr.name CONTAINS 'peut-être' "
            "DETACH DELETE cr RETURN count(cr) as removed",
        )

        # Generic descriptions with articles
        total += await run_cleanup(
            s,
            "Creature",
            "generic descriptions",
            "MATCH (cr:Creature) "
            "WHERE cr.name STARTS WITH 'créatures ' "
            "   OR cr.name STARTS WITH 'cr' "
            "   OR cr.name STARTS WITH 'gros ' "
            "   OR cr.name STARTS WITH 'moustiques ' "
            "   OR cr.name STARTS WITH 'tiques ' "
            "   OR cr.name STARTS WITH 'araignées ' "
            "DETACH DELETE cr RETURN count(cr) as removed",
        )

        # Duplicate plurals: keep singular, remove plurals
        plural_creatures = ["belettes", "furets", "blaireaux", "guerriers"]
        total += await run_cleanup(
            s,
            "Creature",
            "plural duplicates",
            "MATCH (cr:Creature) WHERE cr.name IN $names "
            "DETACH DELETE cr RETURN count(cr) as removed",
            {"names": plural_creatures},
        )

        # ══════════════════════════════════════════════════════════
        # CLASSES
        # ══════════════════════════════════════════════════════════
        print("\n=== Classes ===")

        bad_classes = [
            "null",
            "Humain",
            "Humain (G)",
            "évolution de classe",
            "évolution professionnelle",
            "intermédiaire",
            "intermédiaires",
        ]
        total += await run_cleanup(
            s,
            "Class",
            "garbage/generic classes",
            "MATCH (cls:Class) WHERE cls.name IN $names "
            "DETACH DELETE cls RETURN count(cls) as removed",
            {"names": bad_classes},
        )

        # Plural class names (keep singular)
        plural_classes = [
            "guerriers",
            "guerriers intermédiaires",
            "guerriers légers",
            "archers",
            "ensorceleurs",
        ]
        total += await run_cleanup(
            s,
            "Class",
            "plural class names",
            "MATCH (cls:Class) WHERE cls.name IN $names "
            "DETACH DELETE cls RETURN count(cls) as removed",
            {"names": plural_classes},
        )

        # Lowercase duplicates (keep capitalized version)
        total += await run_cleanup(
            s,
            "Class",
            "lowercase duplicates",
            "MATCH (cls:Class) WHERE cls.name IN "
            "['archer', 'ensorceleur', 'ensorceleuse', "
            "'guerrier', 'variant lourd', 'soigneuse'] "
            "DETACH DELETE cls RETURN count(cls) as removed",
        )

        # ══════════════════════════════════════════════════════════
        # FINAL REPORT
        # ══════════════════════════════════════════════════════════
        print(f"\n{'=' * 50}")
        print(f"Total entities removed: {total}")
        print(f"{'=' * 50}")

        # Final counts
        r = await s.run(
            "MATCH (n) WHERE NOT n:Book AND NOT n:Chapter AND NOT n:Chunk "
            "RETURN labels(n)[0] as label, count(n) as cnt "
            "ORDER BY cnt DESC"
        )
        records = await r.data()
        print("\nFinal KG Entity Counts (excluding Book/Chapter/Chunk):")
        grand_total = 0
        for rec in records:
            print(f"  {rec['label']:15s}: {rec['cnt']}")
            grand_total += rec["cnt"]
        print(f"  {'TOTAL':15s}: {grand_total}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
