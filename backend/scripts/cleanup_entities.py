"""Clean up low-quality entities from Neo4j.

Removes generic descriptors, LLM artifacts, and noise entities
that passed through the initial extraction but shouldn't be in
a wiki-quality Knowledge Graph.

Usage: uv run python scripts/cleanup_entities.py
"""

from __future__ import annotations

import asyncio

from neo4j import AsyncGraphDatabase

from app.config import settings


async def main() -> None:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    total_removed = 0

    async with driver.session() as s:
        # ── Characters ────────────────────────────────────────────
        print("=== Cleaning Characters ===")

        # Remove characters by exact name list
        bad_char_names = [
            "la chose",
            "la chose humanoïde",
            "Le manieur de hache",
            "Nan",
        ]
        r = await s.run(
            "MATCH (c:Character) WHERE c.canonical_name IN $names "
            "DETACH DELETE c RETURN count(c) as removed",
            {"names": bad_char_names},
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} by exact name match")
            total_removed += cnt

        # Remove characters with names containing apostrophe + common relation
        r = await s.run(
            "MATCH (c:Character) "
            'WHERE c.canonical_name CONTAINS "\'s " '
            "DETACH DELETE c RETURN count(c) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} relational descriptors (X's Y)")
            total_removed += cnt

        # Remove characters with names starting with "l'" or "l\u2019"
        r = await s.run(
            "MATCH (c:Character) "
            'WHERE c.canonical_name STARTS WITH "l\'" '
            '   OR c.canonical_name STARTS WITH "l\\u2019" '
            "DETACH DELETE c RETURN count(c) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} French article characters (l'...)")
            total_removed += cnt

        # ── Locations ─────────────────────────────────────────────
        print("\n=== Cleaning Locations ===")

        bad_loc_names = [
            "une clairière",
            "petite clairière",
            "une petite colline",
            "Clairière",
        ]
        r = await s.run(
            "MATCH (l:Location) WHERE l.name IN $names DETACH DELETE l RETURN count(l) as removed",
            {"names": bad_loc_names},
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} generic location names")
            total_removed += cnt

        # Remove locations starting with "l'" or "l\u2019"
        r = await s.run(
            "MATCH (l:Location) "
            'WHERE l.name STARTS WITH "l\'" '
            '   OR l.name STARTS WITH "l\\u2019" '
            "DETACH DELETE l RETURN count(l) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} French article locations (l'...)")
            total_removed += cnt

        # Remove locations starting with "Le " or "La " (generic articles)
        r = await s.run(
            "MATCH (l:Location) "
            "WHERE l.name STARTS WITH 'Le ' "
            "   OR l.name STARTS WITH 'La ' "
            "DETACH DELETE l RETURN count(l) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} French article locations (Le/La...)")
            total_removed += cnt

        # ── Skills ────────────────────────────────────────────────
        print("\n=== Cleaning Skills ===")

        # Remove generic skill descriptions by pattern
        r = await s.run(
            "MATCH (sk:Skill) "
            "WHERE sk.name STARTS WITH 'compétence' "
            "   OR sk.name STARTS WITH 'compétences' "
            "   OR sk.name STARTS WITH 'maniement' "
            "   OR sk.name STARTS WITH 'double maniement' "
            "   OR sk.name STARTS WITH 'les armes' "
            "   OR sk.name STARTS WITH 'nouveau sixième' "
            "DETACH DELETE sk RETURN count(sk) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} generic skill descriptions")
            total_removed += cnt

        # Remove skills starting with "l'" (generic French descriptions)
        r = await s.run(
            "MATCH (sk:Skill) "
            'WHERE sk.name STARTS WITH "l\'" '
            '   OR sk.name STARTS WITH "l\\u2019" '
            "DETACH DELETE sk RETURN count(sk) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} French article skills (l'...)")
            total_removed += cnt

        # ── Concepts ──────────────────────────────────────────────
        print("\n=== Cleaning Concepts ===")

        # Remove orphan concepts (no relationships except FIRST_MENTIONED_IN)
        r = await s.run(
            "MATCH (co:Concept) "
            "WHERE NOT exists { (co)-[:GROUNDED_IN]->() } "
            "DETACH DELETE co RETURN count(co) as removed",
        )
        data = await r.data()
        cnt = data[0]["removed"]
        if cnt:
            print(f"  Removed {cnt} ungrounded concepts")
            total_removed += cnt

        # ── Final counts ──────────────────────────────────────────
        print(f"\n=== Total removed: {total_removed} ===")

        # Show final entity counts
        r = await s.run("MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt ORDER BY cnt DESC")
        records = await r.data()
        print("\n=== Final Entity Counts ===")
        for rec in records:
            print(f"  {rec['label']:15s}: {rec['cnt']}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
