"""V3 Migration Script — Clean V2 data and prepare for V3 re-extraction.

Usage:
    python scripts/migrate_v3.py --dry-run          # Show counts only
    python scripts/migrate_v3.py                     # Execute cleanup
    python scripts/migrate_v3.py --re-extract        # Cleanup + trigger re-extraction

Requires:
    NEO4J_URI (default: bolt://localhost:7687)
    NEO4J_USER (default: neo4j)
    NEO4J_PASSWORD (default: worldrag)
"""

import argparse
import asyncio
import os
import sys

from neo4j import AsyncGraphDatabase


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "worldrag")


CLEANUP_QUERIES = [
    ("StateChange nodes", "MATCH (n:StateChange) RETURN count(n) AS cnt", "MATCH (n:StateChange) DETACH DELETE n"),
    ("BlueBox nodes", "MATCH (n:BlueBox) RETURN count(n) AS cnt", "MATCH (n:BlueBox) DETACH DELETE n"),
    ("GRANTS_SKILL relationships", "MATCH ()-[r:GRANTS_SKILL]->() RETURN count(r) AS cnt", "MATCH ()-[r:GRANTS_SKILL]->() DELETE r"),
    ("Bloodline nodes", "MATCH (n:Bloodline) RETURN count(n) AS cnt", "MATCH (n:Bloodline) DETACH DELETE n"),
    ("Profession nodes", "MATCH (n:Profession) RETURN count(n) AS cnt", "MATCH (n:Profession) DETACH DELETE n"),
    ("PrimordialChurch nodes", "MATCH (n:PrimordialChurch) RETURN count(n) AS cnt", "MATCH (n:PrimordialChurch) DETACH DELETE n"),
]


async def run_migration(dry_run: bool = True, re_extract: bool = False) -> None:
    driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        async with driver.session() as session:
            print(f"\n{'=' * 60}")
            print(f"V3 Migration — {'DRY RUN' if dry_run else 'EXECUTING'}")
            print(f"{'=' * 60}")
            print(f"Neo4j: {NEO4J_URI}\n")

            for label, count_query, delete_query in CLEANUP_QUERIES:
                result = await session.run(count_query)
                record = await result.single()
                count = record["cnt"] if record else 0

                if dry_run:
                    print(f"  [DRY RUN] {label}: {count} would be deleted")
                else:
                    if count > 0:
                        await session.run(delete_query)
                        print(f"  [DELETED] {label}: {count} removed")
                    else:
                        print(f"  [SKIP]    {label}: none found")

            print(f"\n{'=' * 60}")

            if not dry_run:
                print("Cleanup complete.")

                if re_extract:
                    print("\nTriggering re-extraction for all books...")
                    # Fetch all book IDs
                    result = await session.run(
                        "MATCH (b:Book) RETURN b.book_id AS book_id"
                    )
                    records = await result.data()
                    book_ids = [r["book_id"] for r in records]

                    if book_ids:
                        print(f"Found {len(book_ids)} books: {', '.join(book_ids)}")
                        print("NOTE: Re-extraction must be triggered via the API:")
                        for bid in book_ids:
                            print(f"  curl -X POST http://localhost:8000/api/books/{bid}/extract")
                    else:
                        print("No books found in the graph.")
            else:
                print("No changes made. Run without --dry-run to execute.")

    finally:
        await driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="V3 Migration: clean V2 data for re-extraction")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Show counts without deleting")
    parser.add_argument("--re-extract", action="store_true", default=False, help="Print re-extraction commands after cleanup")
    args = parser.parse_args()

    asyncio.run(run_migration(dry_run=args.dry_run, re_extract=args.re_extract))


if __name__ == "__main__":
    main()
