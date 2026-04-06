#!/usr/bin/env python3
"""CLI for running MINE benchmark on a WorldRAG book's Knowledge Graph.

Usage:
    uv run python scripts/evaluate_kg.py <book_id> [--chapters N] [--facts K]

Example:
    uv run python scripts/evaluate_kg.py ff54a9fc --chapters 10 --facts 10
"""

import argparse
import asyncio
import json
import sys

sys.path.insert(0, "backend")


async def main() -> None:
    parser = argparse.ArgumentParser(description="MINE benchmark for WorldRAG KG")
    parser.add_argument("book_id", help="Book ID to evaluate")
    parser.add_argument("--chapters", type=int, default=10, help="Number of chapters to sample")
    parser.add_argument("--facts", type=int, default=10, help="Facts per chapter")
    args = parser.parse_args()

    from app.core.logging import setup_logging

    setup_logging()

    from app.core.neo4j import get_driver

    driver = get_driver()

    from app.services.evaluation.mine_benchmark import evaluate_mine

    print(f"Running MINE benchmark on book {args.book_id}...")
    print(f"  Chapters: {args.chapters}, Facts per chapter: {args.facts}")
    print()

    result = await evaluate_mine(
        driver,
        args.book_id,
        n_chapters=args.chapters,
        k_facts=args.facts,
    )

    print(f"\n{'=' * 50}")
    print(f"MINE Score: {result['score']:.1%}")
    print(f"Chapters evaluated: {result['chapters_evaluated']}")
    print(f"Total facts: {result['total_facts']}")
    print(f"Inferable: {result['total_inferable']}")
    print(f"{'=' * 50}")

    if result.get("per_chapter"):
        print("\nPer-chapter breakdown:")
        for ch in result["per_chapter"]:
            bar = "█" * int(ch["score"] * 20)
            print(f"  Ch.{ch['chapter']:3d}: {ch['score']:.0%} ({ch['inferable']}/{ch['facts']}) {bar}")

    # Save full results to JSON
    out_path = f"mine_results_{args.book_id}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFull results saved to {out_path}")

    await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
