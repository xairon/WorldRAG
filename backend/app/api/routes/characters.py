"""Character State API routes.

Provides endpoints for reconstructing character state at any chapter,
viewing progression timelines, comparing states across chapters,
and fetching lightweight character summaries.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.api.auth import require_auth
from app.api.dependencies import get_neo4j
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.repositories.character_state_repo import CharacterStateRepository
from app.schemas.character_state import (
    CategoryDiff,
    CharacterComparison,
    CharacterStateSnapshot,
    CharacterSummary,
    ClassSnapshot,
    ItemSnapshot,
    LevelSnapshot,
    ProgressionMilestone,
    ProgressionTimeline,
    SkillSnapshot,
    StatDiff,
    StateChangeRecord,
    StatEntry,
    TitleSnapshot,
)

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)
router = APIRouter(prefix="/characters", tags=["characters"])


# -- GET /{name}/at/{chapter} -- Full character sheet snapshot ----------------


@router.get(
    "/{name}/at/{chapter}",
    response_model=CharacterStateSnapshot,
    dependencies=[Depends(require_auth)],
)
async def get_character_state_at_chapter(
    name: str,
    chapter: int,
    book_id: str = Query(..., description="Book ID to scope the query"),
    driver: AsyncDriver = Depends(get_neo4j),
) -> CharacterStateSnapshot:
    """Reconstruct the full character sheet at a specific chapter.

    Aggregates stats, skills, classes, titles, items, and level from
    the immutable StateChange ledger and temporal relationships.
    """
    repo = CharacterStateRepository(driver)

    # Verify character exists
    char_info = await repo.get_character_info(name)
    if char_info is None:
        raise NotFoundError(f"Character '{name}' not found")

    # Run all aggregation queries in parallel
    (
        stats_raw,
        level_raw,
        skills_raw,
        classes_raw,
        titles_raw,
        items_raw,
        chapter_changes_raw,
        total_chapters,
    ) = await asyncio.gather(
        repo.get_stats_at_chapter(name, book_id, chapter),
        repo.get_level_at_chapter(name, book_id, chapter),
        repo.get_skills_at_chapter(name, book_id, chapter),
        repo.get_classes_at_chapter(name, book_id, chapter),
        repo.get_titles_at_chapter(name, book_id, chapter),
        repo.get_items_at_chapter(name, book_id, chapter),
        repo.get_chapter_changes(name, book_id, chapter),
        repo.get_total_chapters(book_id),
    )

    # Count total changes to date (sum of all changes up to this chapter)
    # We use the progression milestones count for this
    _, total_changes = await repo.get_progression_milestones(name, book_id, limit=0, offset=0)

    # Assemble response
    stats = [
        StatEntry(
            name=s["stat_name"],
            value=s["value"],
            last_changed_chapter=s["last_changed_chapter"],
        )
        for s in stats_raw
    ]

    level = LevelSnapshot(
        level=level_raw.get("level"),
        realm=level_raw.get("realm") or "",
        since_chapter=level_raw.get("since_chapter"),
    )

    skills = [
        SkillSnapshot(
            name=s["name"],
            rank=s.get("rank") or "",
            skill_type=s.get("skill_type") or "",
            description=s.get("description") or "",
            acquired_chapter=s.get("acquired_chapter"),
        )
        for s in skills_raw
    ]

    classes = [
        ClassSnapshot(
            name=c["name"],
            tier=c.get("tier"),
            description=c.get("description") or "",
            acquired_chapter=c.get("acquired_chapter"),
        )
        for c in classes_raw
    ]

    titles = [
        TitleSnapshot(
            name=t["name"],
            description=t.get("description") or "",
            effects=t.get("effects") or [],
            acquired_chapter=t.get("acquired_chapter"),
        )
        for t in titles_raw
    ]

    items = [
        ItemSnapshot(
            name=i["name"],
            item_type=i.get("item_type") or "",
            rarity=i.get("rarity") or "",
            description=i.get("description") or "",
            acquired_chapter=i.get("acquired_chapter"),
            grants=i.get("grants") or [],
        )
        for i in items_raw
    ]

    chapter_changes = [
        StateChangeRecord(
            chapter=ch["chapter"],
            category=ch["category"],
            name=ch["name"],
            action=ch["action"],
            value_delta=ch.get("value_delta"),
            value_after=ch.get("value_after"),
            detail=ch.get("detail") or "",
        )
        for ch in chapter_changes_raw
    ]

    aliases = char_info.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]

    return CharacterStateSnapshot(
        character_name=char_info.get("name") or name,
        canonical_name=char_info.get("canonical_name") or name,
        book_id=book_id,
        as_of_chapter=chapter,
        total_chapters_in_book=total_chapters,
        role=char_info.get("role") or "",
        species=char_info.get("species") or "",
        description=char_info.get("description") or "",
        aliases=aliases,
        level=level,
        stats=stats,
        skills=skills,
        classes=classes,
        titles=titles,
        items=items,
        chapter_changes=chapter_changes,
        total_changes_to_date=total_changes,
    )


# -- GET /{name}/progression -- Paginated progression timeline ----------------


@router.get(
    "/{name}/progression",
    response_model=ProgressionTimeline,
    dependencies=[Depends(require_auth)],
)
async def get_character_progression(
    name: str,
    book_id: str = Query(..., description="Book ID to scope the query"),
    category: str | None = Query(
        None, description="Filter by category: stat, skill, class, title, item, level"
    ),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    driver: AsyncDriver = Depends(get_neo4j),
) -> ProgressionTimeline:
    """Get paginated progression timeline of all state changes for a character."""
    repo = CharacterStateRepository(driver)

    milestones_raw, total = await repo.get_progression_milestones(
        name, book_id, category=category, offset=offset, limit=limit
    )

    milestones = [
        ProgressionMilestone(
            chapter=m["chapter"],
            category=m["category"],
            name=m["name"],
            action=m["action"],
            value_delta=m.get("value_delta"),
            value_after=m.get("value_after"),
            detail=m.get("detail") or "",
        )
        for m in milestones_raw
    ]

    return ProgressionTimeline(
        character_name=name,
        book_id=book_id,
        milestones=milestones,
        total=total,
        offset=offset,
        limit=limit,
    )


# -- GET /{name}/compare -- Compare state at two chapters --------------------


@router.get(
    "/{name}/compare",
    response_model=CharacterComparison,
    dependencies=[Depends(require_auth)],
)
async def compare_character_state(
    name: str,
    book_id: str = Query(..., description="Book ID to scope the query"),
    from_chapter: int = Query(..., alias="from", description="Starting chapter"),
    to_chapter: int = Query(..., alias="to", description="Ending chapter"),
    driver: AsyncDriver = Depends(get_neo4j),
) -> CharacterComparison:
    """Compare character state between two chapters.

    Shows stat diffs, gained/lost skills/classes/titles/items, and level changes.
    """
    repo = CharacterStateRepository(driver)

    # Get stats and levels at both chapters in parallel
    (
        stats_from_raw,
        stats_to_raw,
        level_from_raw,
        level_to_raw,
        changes_raw,
    ) = await asyncio.gather(
        repo.get_stats_at_chapter(name, book_id, from_chapter),
        repo.get_stats_at_chapter(name, book_id, to_chapter),
        repo.get_level_at_chapter(name, book_id, from_chapter),
        repo.get_level_at_chapter(name, book_id, to_chapter),
        repo.get_changes_between_chapters(name, book_id, from_chapter, to_chapter),
    )

    # Compute stat diffs
    stats_from_map = {s["stat_name"]: s["value"] for s in stats_from_raw}
    stats_to_map = {s["stat_name"]: s["value"] for s in stats_to_raw}
    all_stat_names = sorted(set(stats_from_map) | set(stats_to_map))

    stat_diffs = []
    for stat_name in all_stat_names:
        val_from = stats_from_map.get(stat_name, 0)
        val_to = stats_to_map.get(stat_name, 0)
        if val_from != val_to:
            stat_diffs.append(
                StatDiff(
                    name=stat_name,
                    value_at_from=val_from,
                    value_at_to=val_to,
                    delta=val_to - val_from,
                )
            )

    # Build category diffs from changes between chapters
    category_diffs: dict[str, CategoryDiff] = {
        "skill": CategoryDiff(),
        "class": CategoryDiff(),
        "title": CategoryDiff(),
        "item": CategoryDiff(),
    }

    for change in changes_raw:
        cat = change.get("category", "")
        action = change.get("action", "")
        change_name = change.get("name", "")

        if cat in category_diffs:
            if action in ("gain", "acquire", "upgrade", "evolve"):
                category_diffs[cat].gained.append(change_name)
            elif action in ("lose", "drop"):
                category_diffs[cat].lost.append(change_name)

    return CharacterComparison(
        character_name=name,
        book_id=book_id,
        from_chapter=from_chapter,
        to_chapter=to_chapter,
        level_from=level_from_raw.get("level"),
        level_to=level_to_raw.get("level"),
        stat_diffs=stat_diffs,
        skills=category_diffs["skill"],
        classes=category_diffs["class"],
        titles=category_diffs["title"],
        items=category_diffs["item"],
        total_changes=len(changes_raw),
    )


# -- GET /{name}/summary -- Lightweight character summary ---------------------


@router.get(
    "/{name}/summary",
    response_model=CharacterSummary,
    dependencies=[Depends(require_auth)],
)
async def get_character_summary(
    name: str,
    book_id: str | None = Query(None, description="Book ID (optional)"),
    chapter: int | None = Query(None, description="Chapter for level/skills snapshot"),
    driver: AsyncDriver = Depends(get_neo4j),
) -> CharacterSummary:
    """Get a lightweight character summary for hover tooltips.

    Returns basic character info. If chapter and book_id are provided,
    also includes level, active class, and top skills at that chapter.
    """
    repo = CharacterStateRepository(driver)

    char_info = await repo.get_character_info(name)
    if char_info is None:
        raise NotFoundError(f"Character '{name}' not found")

    level_val: int | None = None
    realm = ""
    active_class: str | None = None
    top_skills: list[str] = []

    # If chapter and book_id are provided, fetch temporal data
    if chapter is not None and book_id is not None:
        level_raw, skills_raw, classes_raw = await asyncio.gather(
            repo.get_level_at_chapter(name, book_id, chapter),
            repo.get_skills_at_chapter(name, book_id, chapter),
            repo.get_classes_at_chapter(name, book_id, chapter),
        )
        level_val = level_raw.get("level")
        realm = level_raw.get("realm") or ""
        top_skills = [s["name"] for s in skills_raw[:5]]
        if classes_raw:
            active_class = classes_raw[-1]["name"]

    return CharacterSummary(
        name=char_info.get("name") or name,
        canonical_name=char_info.get("canonical_name") or name,
        role=char_info.get("role") or "",
        species=char_info.get("species") or "",
        level=level_val,
        realm=realm,
        active_class=active_class,
        top_skills=top_skills,
        description=char_info.get("description") or "",
    )
