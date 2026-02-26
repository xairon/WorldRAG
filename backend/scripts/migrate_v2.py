"""V2 migration: clean up legacy GROUNDED_IN relationships and Paragraph nodes.

WorldRAG V2 replaces GROUNDED_IN with MENTIONED_IN for entity-to-chapter
grounding. This script removes the old data so books can be re-extracted
with the new pipeline.

Usage:
    # Minimal cleanup (GROUNDED_IN rels + Paragraph nodes only)
    cd backend
    uv run python scripts/migrate_v2.py

    # Or via module
    uv run python -m backend.scripts.migrate_v2

    # Full cleanup (also removes all entities and relationships for re-extraction)
    uv run python scripts/migrate_v2.py --full

    # Dry run (show what would be deleted without actually deleting)
    uv run python scripts/migrate_v2.py --dry-run
    uv run python scripts/migrate_v2.py --full --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from neo4j import AsyncGraphDatabase

from app.config import settings

# All entity labels created by the extraction pipeline
ENTITY_LABELS = [
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
]

# All relationship types created by the extraction pipeline (excluding structural ones)
ENTITY_RELATIONSHIP_TYPES = [
    "RELATES_TO",
    "HAS_SKILL",
    "HAS_CLASS",
    "HAS_TITLE",
    "PARTICIPATES_IN",
    "OCCURS_AT",
    "LOCATION_PART_OF",
    "POSSESSES",
    "HAS_STAT",
    "FIRST_MENTIONED_IN",
    "MENTIONED_IN",
]


async def count_items(session, query: str) -> int:
    """Run a count query and return the integer result."""
    result = await session.run(query)
    data = await result.data()
    return data[0]["cnt"] if data else 0


async def delete_and_count(session, query: str) -> int:
    """Run a delete query that returns a 'removed' count."""
    result = await session.run(query)
    data = await result.data()
    return data[0]["removed"] if data else 0


async def run_audit(session) -> None:
    """Print current state of the knowledge graph."""
    result = await session.run(
        "MATCH (n) "
        "RETURN labels(n)[0] AS label, count(n) AS cnt "
        "ORDER BY cnt DESC"
    )
    records = await result.data()

    print("\n=== Current KG Node Counts ===")
    total = 0
    for rec in records:
        print(f"  {rec['label']:15s}: {rec['cnt']}")
        total += rec["cnt"]
    print(f"  {'TOTAL':15s}: {total}")

    # Relationship counts
    result = await session.run(
        "MATCH ()-[r]->() "
        "RETURN type(r) AS rel_type, count(r) AS cnt "
        "ORDER BY cnt DESC"
    )
    records = await result.data()

    print("\n=== Current KG Relationship Counts ===")
    total = 0
    for rec in records:
        print(f"  {rec['rel_type']:25s}: {rec['cnt']}")
        total += rec["cnt"]
    print(f"  {'TOTAL':25s}: {total}")


async def migrate_minimal(session, *, dry_run: bool = False) -> dict[str, int]:
    """Remove legacy GROUNDED_IN relationships and Paragraph nodes.

    Returns dict of item type -> count removed.
    """
    counts: dict[str, int] = {}

    # 1. Count and delete GROUNDED_IN relationships
    grounded_count = await count_items(
        session,
        "MATCH ()-[r:GROUNDED_IN]->() RETURN count(r) AS cnt",
    )
    print(f"\n  GROUNDED_IN relationships found: {grounded_count}")

    if grounded_count > 0 and not dry_run:
        # Delete in batches to avoid memory issues on large graphs
        removed = 0
        while True:
            batch_removed = await delete_and_count(
                session,
                "MATCH ()-[r:GROUNDED_IN]->() "
                "WITH r LIMIT 10000 "
                "DELETE r "
                "RETURN count(r) AS removed",
            )
            removed += batch_removed
            if batch_removed == 0:
                break
            print(f"    Deleted batch: {batch_removed} (total: {removed})")
        counts["GROUNDED_IN relationships"] = removed
        print(f"  Deleted {removed} GROUNDED_IN relationships")
    elif dry_run and grounded_count > 0:
        counts["GROUNDED_IN relationships"] = grounded_count
        print(f"  [DRY RUN] Would delete {grounded_count} GROUNDED_IN relationships")

    # 2. Count and delete Paragraph nodes (they'll be recreated on re-upload)
    paragraph_count = await count_items(
        session,
        "MATCH (p:Paragraph) RETURN count(p) AS cnt",
    )
    print(f"\n  Paragraph nodes found: {paragraph_count}")

    if paragraph_count > 0 and not dry_run:
        removed = 0
        while True:
            batch_removed = await delete_and_count(
                session,
                "MATCH (p:Paragraph) "
                "WITH p LIMIT 5000 "
                "DETACH DELETE p "
                "RETURN count(p) AS removed",
            )
            removed += batch_removed
            if batch_removed == 0:
                break
            print(f"    Deleted batch: {batch_removed} (total: {removed})")
        counts["Paragraph nodes"] = removed
        print(f"  Deleted {removed} Paragraph nodes")
    elif dry_run and paragraph_count > 0:
        counts["Paragraph nodes"] = paragraph_count
        print(f"  [DRY RUN] Would delete {paragraph_count} Paragraph nodes")

    return counts


async def migrate_full(session, *, dry_run: bool = False) -> dict[str, int]:
    """Remove all extraction entities and relationships for full re-extraction.

    This deletes all entity nodes and their relationships so books can be
    re-extracted from scratch. Book, Chapter, Chunk, and Series nodes are
    preserved.

    Returns dict of item type -> count removed.
    """
    counts: dict[str, int] = {}

    # Delete entity relationship types first (before deleting nodes)
    for rel_type in ENTITY_RELATIONSHIP_TYPES:
        rel_count = await count_items(
            session,
            f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt",
        )
        if rel_count == 0:
            continue

        print(f"\n  {rel_type} relationships found: {rel_count}")

        if not dry_run:
            removed = 0
            while True:
                batch_removed = await delete_and_count(
                    session,
                    f"MATCH ()-[r:{rel_type}]->() "
                    f"WITH r LIMIT 10000 "
                    f"DELETE r "
                    f"RETURN count(r) AS removed",
                )
                removed += batch_removed
                if batch_removed == 0:
                    break
            counts[f"{rel_type} relationships"] = removed
            print(f"  Deleted {removed} {rel_type} relationships")
        else:
            counts[f"{rel_type} relationships"] = rel_count
            print(f"  [DRY RUN] Would delete {rel_count} {rel_type} relationships")

    # Delete entity nodes
    for label in ENTITY_LABELS:
        node_count = await count_items(
            session,
            f"MATCH (n:{label}) RETURN count(n) AS cnt",
        )
        if node_count == 0:
            continue

        print(f"\n  {label} nodes found: {node_count}")

        if not dry_run:
            removed = 0
            while True:
                batch_removed = await delete_and_count(
                    session,
                    f"MATCH (n:{label}) "
                    f"WITH n LIMIT 5000 "
                    f"DETACH DELETE n "
                    f"RETURN count(n) AS removed",
                )
                removed += batch_removed
                if batch_removed == 0:
                    break
            counts[f"{label} nodes"] = removed
            print(f"  Deleted {removed} {label} nodes")
        else:
            counts[f"{label} nodes"] = node_count
            print(f"  [DRY RUN] Would delete {node_count} {label} nodes")

    # Reset book statuses from 'extracted'/'embedded' back to 'completed'
    # so they can be re-extracted
    status_count = await count_items(
        session,
        "MATCH (b:Book) WHERE b.status IN ['extracted', 'embedded'] "
        "RETURN count(b) AS cnt",
    )
    if status_count > 0:
        print(f"\n  Books to reset status: {status_count}")
        if not dry_run:
            result = await session.run(
                "MATCH (b:Book) WHERE b.status IN ['extracted', 'embedded'] "
                "SET b.status = 'completed' "
                "RETURN count(b) AS removed"
            )
            data = await result.data()
            reset = data[0]["removed"] if data else 0
            counts["Book statuses reset"] = reset
            print(f"  Reset {reset} book statuses to 'completed'")
        else:
            counts["Book statuses reset"] = status_count
            print(f"  [DRY RUN] Would reset {status_count} book statuses to 'completed'")

    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="WorldRAG V2 migration: clean up legacy GROUNDED_IN data",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also delete all entities and relationships for full re-extraction",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    args = parser.parse_args()

    mode = "FULL" if args.full else "MINIMAL"
    dry_label = " (DRY RUN)" if args.dry_run else ""

    print(f"{'='*60}")
    print(f"WorldRAG V2 Migration — {mode}{dry_label}")
    print(f"{'='*60}")
    print(f"Neo4j: {settings.neo4j_uri}")

    if args.full and not args.dry_run:
        print(
            "\nWARNING: --full mode will delete ALL extraction entities and "
            "relationships."
        )
        print("Books, chapters, and chunks will be preserved.")
        print("You will need to re-extract all books after this migration.\n")
        confirm = input("Type 'yes' to proceed: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    try:
        async with driver.session() as session:
            # Pre-migration audit
            print("\n--- Pre-migration state ---")
            await run_audit(session)

            # Step 1: Minimal cleanup (always runs)
            print(f"\n{'='*60}")
            print("Step 1: Remove legacy GROUNDED_IN + Paragraph nodes")
            print(f"{'='*60}")
            minimal_counts = await migrate_minimal(session, dry_run=args.dry_run)

            # Step 2: Full cleanup (only with --full)
            full_counts: dict[str, int] = {}
            if args.full:
                print(f"\n{'='*60}")
                print("Step 2: Remove all extraction entities and relationships")
                print(f"{'='*60}")
                full_counts = await migrate_full(session, dry_run=args.dry_run)

            # Post-migration audit
            if not args.dry_run:
                print("\n--- Post-migration state ---")
                await run_audit(session)

            # Summary
            all_counts = {**minimal_counts, **full_counts}
            print(f"\n{'='*60}")
            print(f"Migration Summary{dry_label}")
            print(f"{'='*60}")
            if all_counts:
                for item, count in all_counts.items():
                    action = "Would delete" if args.dry_run else "Deleted"
                    if "reset" in item.lower():
                        action = "Would reset" if args.dry_run else "Reset"
                    print(f"  {action} {count} {item}")
            else:
                print("  Nothing to clean up — database is already migrated.")

            print(f"\n{'='*60}")
            if not args.full:
                print("Next steps:")
                print("  1. Re-extract books: POST /api/books/{id}/extract")
                print("  2. Or run: uv run python scripts/run_full_pipeline.py <book_id>")
                print(
                    "\nTip: Use --full to also delete entities for a clean re-extraction."
                )
            else:
                print("Next steps:")
                print("  1. Re-extract all books: POST /api/books/{id}/extract")
                print("  2. Or run: uv run python scripts/run_full_pipeline.py <book_id>")
            print(f"{'='*60}")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
