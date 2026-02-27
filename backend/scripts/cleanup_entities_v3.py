"""Final cleanup pass — factions and concepts."""

from __future__ import annotations

import asyncio

from neo4j import AsyncGraphDatabase

from app.config import settings


async def main() -> None:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    total = 0

    async with driver.session() as s:
        # Factions
        print("=== Factions ===")

        # Remove generic departments/companies
        bad_factions = [
            "ensorceleurs",
            "service financier",
        ]
        r = await s.run(
            "MATCH (f:Faction) WHERE f.name IN $names DETACH DELETE f RETURN count(f) as removed",
            {"names": bad_factions},
        )
        d = await r.data()
        cnt = d[0]["removed"]
        total += cnt
        if cnt:
            print(f"  Removed {cnt}: exact match")

        # Factions containing "service" or "société"
        r = await s.run(
            "MATCH (f:Faction) "
            "WHERE f.name CONTAINS 'service' "
            "   OR f.name CONTAINS 'société' "
            "   OR f.name CONTAINS 'entreprise' "
            "DETACH DELETE f RETURN count(f) as removed"
        )
        d = await r.data()
        cnt = d[0]["removed"]
        total += cnt
        if cnt:
            print(f"  Removed {cnt}: generic organizations")

        # Concepts
        print("\n=== Concepts ===")

        bad_concepts = [
            "Fire",
            "Flammes",
            "Classes",
            "Professions",
            "Race",
            "Title",
            "Spells",
            "Gods",
            "Urban Traffic",
            "Identification",
            "Ensorceleurs",
            "Compound Bows",
            "Medieval Aesthetic",
            "Multiverse",
            "Tutorial",
            "New World",
            "New Reality",
            "Mana Bolts",
            "Mana Injection",
        ]
        r = await s.run(
            "MATCH (co:Concept) WHERE co.name IN $names "
            "DETACH DELETE co RETURN count(co) as removed",
            {"names": bad_concepts},
        )
        d = await r.data()
        cnt = d[0]["removed"]
        total += cnt
        if cnt:
            print(f"  Removed {cnt}: generic/duplicates")

        # Concepts that are Nouvelle Réalité (keep only Multivers)
        r = await s.run(
            "MATCH (co:Concept) "
            "WHERE co.name CONTAINS 'Nouvelle' "
            "   OR co.name CONTAINS 'Forbidden' "
            "   OR co.name CONTAINS 'Required Threshold' "
            "DETACH DELETE co RETURN count(co) as removed"
        )
        d = await r.data()
        cnt = d[0]["removed"]
        total += cnt
        if cnt:
            print(f"  Removed {cnt}: verbose descriptions")

        # Single all-lowercase concepts
        r = await s.run(
            "MATCH (co:Concept) "
            "WHERE co.name = toLower(co.name) "
            "AND NOT co.name CONTAINS ' ' "
            "AND size(co.name) < 10 "
            "DETACH DELETE co RETURN count(co) as removed"
        )
        d = await r.data()
        cnt = d[0]["removed"]
        total += cnt
        if cnt:
            print(f"  Removed {cnt}: single lowercase words")

        print(f"\nTotal removed: {total}")

        # Final audit
        r = await s.run(
            "MATCH (n) WHERE NOT n:Book AND NOT n:Chapter AND NOT n:Chunk "
            "RETURN labels(n)[0] as label, count(n) as cnt "
            "ORDER BY cnt DESC"
        )
        records = await r.data()
        print("\n=== FINAL KG ENTITY COUNTS ===")
        gt = 0
        for rec in records:
            print(f"  {rec['label']:15s}: {rec['cnt']}")
            gt += rec["cnt"]
        print(f"  {'TOTAL':15s}: {gt}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
