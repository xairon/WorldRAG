"""Neo4j repository for KG entities (characters, skills, events, etc.).

Handles MERGE operations for all ontology entity types with temporal
properties and grounding links. Uses UNWIND for batch efficiency.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

if TYPE_CHECKING:
    from app.schemas.extraction import (
        ChapterExtractionResult,
        ExtractedCharacter,
        ExtractedClass,
        ExtractedConcept,
        ExtractedCreature,
        ExtractedEvent,
        ExtractedFaction,
        ExtractedItem,
        ExtractedLevelChange,
        ExtractedLocation,
        ExtractedRelationship,
        ExtractedSkill,
        ExtractedStatChange,
        ExtractedTitle,
        GroundedEntity,
    )

logger = get_logger(__name__)


class EntityRepository(Neo4jRepository):
    """Repository for KG entity CRUD operations."""

    # ── Characters ──────────────────────────────────────────────────────

    async def upsert_characters(
        self,
        book_id: str,
        chapter_number: int,
        characters: list[ExtractedCharacter],
        batch_id: str = "",
    ) -> int:
        """Upsert character nodes. MERGE on canonical_name."""
        if not characters:
            return 0

        data = [
            {
                "name": c.name,
                "canonical_name": c.canonical_name or c.name,
                "aliases": c.aliases,
                "description": c.description,
                "role": c.role,
                "species": c.species,
                "first_chapter": c.first_appearance_chapter or chapter_number,
            }
            for c in characters
        ]

        await self.execute_write(
            """
            UNWIND $chars AS c
            MERGE (ch:Character {canonical_name: c.canonical_name})
            ON CREATE SET
                ch.name = c.name,
                ch.aliases = c.aliases,
                ch.description = c.description,
                ch.role = c.role,
                ch.species = c.species,
                ch.first_appearance_chapter = c.first_chapter,
                ch.book_id = $book_id,
                ch.batch_id = $batch_id,
                ch.created_at = timestamp()
            ON MATCH SET
                ch.description = CASE
                    WHEN size(c.description) > size(coalesce(ch.description, ''))
                    THEN c.description ELSE ch.description END,
                ch.aliases = ch.aliases + [a IN c.aliases WHERE NOT a IN ch.aliases],
                ch.batch_id = $batch_id
            WITH ch, c
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (ch)-[:MENTIONED_IN]->(chap)
            """,
            {
                "chars": data,
                "book_id": book_id,
                "chapter": chapter_number,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "characters_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(characters),
        )
        return len(characters)

    # ── Relationships ───────────────────────────────────────────────────

    async def upsert_relationships(
        self,
        book_id: str,
        chapter_number: int,
        relationships: list[ExtractedRelationship],
        batch_id: str = "",
    ) -> int:
        """Upsert character relationships with temporal properties."""
        if not relationships:
            return 0

        data = [
            {
                "source": r.source,
                "target": r.target,
                "rel_type": r.rel_type,
                "subtype": r.subtype,
                "context": r.context,
                "since_chapter": r.since_chapter or chapter_number,
            }
            for r in relationships
            if r.source and r.target
        ]

        if not data:
            return 0

        await self.execute_write(
            """
            UNWIND $rels AS r
            MATCH (a:Character {canonical_name: r.source})
            MATCH (b:Character {canonical_name: r.target})
            MERGE (a)-[rel:RELATES_TO {
                type: r.rel_type,
                valid_from_chapter: r.since_chapter
            }]->(b)
            ON CREATE SET
                rel.subtype = r.subtype,
                rel.context = r.context,
                rel.book_id = $book_id,
                rel.batch_id = $batch_id
            """,
            {"rels": data, "book_id": book_id, "batch_id": batch_id},
        )

        logger.info(
            "relationships_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(data),
        )
        return len(data)

    # ── Skills ──────────────────────────────────────────────────────────

    async def upsert_skills(
        self,
        book_id: str,
        chapter_number: int,
        skills: list[ExtractedSkill],
        batch_id: str = "",
    ) -> int:
        """Upsert skill nodes and link to owner characters."""
        if not skills:
            return 0

        data = [
            {
                "name": s.name,
                "description": s.description,
                "skill_type": s.skill_type,
                "rank": s.rank,
                "owner": s.owner,
                "chapter": s.acquired_chapter or chapter_number,
            }
            for s in skills
        ]

        await self.execute_write(
            """
            UNWIND $skills AS s
            MERGE (sk:Skill {name: s.name})
            ON CREATE SET
                sk.description = s.description,
                sk.skill_type = s.skill_type,
                sk.rank = s.rank,
                sk.book_id = $book_id,
                sk.batch_id = $batch_id,
                sk.created_at = timestamp()
            ON MATCH SET
                sk.description = CASE
                    WHEN size(s.description) > size(coalesce(sk.description, ''))
                    THEN s.description ELSE sk.description END,
                sk.rank = CASE
                    WHEN s.rank <> '' THEN s.rank ELSE sk.rank END,
                sk.batch_id = $batch_id
            WITH sk, s
            WHERE s.owner <> ''
            MATCH (ch:Character {canonical_name: s.owner})
            MERGE (ch)-[r:HAS_SKILL]->(sk)
            ON CREATE SET r.valid_from_chapter = s.chapter
            """,
            {"skills": data, "book_id": book_id, "batch_id": batch_id},
        )

        logger.info(
            "skills_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(skills),
        )
        return len(skills)

    # ── Classes ─────────────────────────────────────────────────────────

    async def upsert_classes(
        self,
        book_id: str,
        chapter_number: int,
        classes: list[ExtractedClass],
        batch_id: str = "",
    ) -> int:
        """Upsert class nodes and link to owner characters."""
        if not classes:
            return 0

        data = [
            {
                "name": c.name,
                "description": c.description,
                "tier": c.tier,
                "owner": c.owner,
                "chapter": c.acquired_chapter or chapter_number,
            }
            for c in classes
        ]

        await self.execute_write(
            """
            UNWIND $classes AS c
            MERGE (cls:Class {name: c.name})
            ON CREATE SET
                cls.description = c.description,
                cls.tier = c.tier,
                cls.book_id = $book_id,
                cls.batch_id = $batch_id,
                cls.created_at = timestamp()
            WITH cls, c
            WHERE c.owner <> ''
            MATCH (ch:Character {canonical_name: c.owner})
            MERGE (ch)-[r:HAS_CLASS]->(cls)
            ON CREATE SET r.valid_from_chapter = c.chapter
            """,
            {"classes": data, "book_id": book_id, "batch_id": batch_id},
        )

        logger.info(
            "classes_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(classes),
        )
        return len(classes)

    # ── Titles ──────────────────────────────────────────────────────────

    async def upsert_titles(
        self,
        book_id: str,
        chapter_number: int,
        titles: list[ExtractedTitle],
        batch_id: str = "",
    ) -> int:
        """Upsert title nodes and link to owner characters."""
        if not titles:
            return 0

        data = [
            {
                "name": t.name,
                "description": t.description,
                "effects": t.effects,
                "owner": t.owner,
                "chapter": t.acquired_chapter or chapter_number,
            }
            for t in titles
        ]

        await self.execute_write(
            """
            UNWIND $titles AS t
            MERGE (ti:Title {name: t.name})
            ON CREATE SET
                ti.description = t.description,
                ti.effects = t.effects,
                ti.book_id = $book_id,
                ti.batch_id = $batch_id,
                ti.created_at = timestamp()
            WITH ti, t
            WHERE t.owner <> ''
            MATCH (ch:Character {canonical_name: t.owner})
            MERGE (ch)-[r:HAS_TITLE]->(ti)
            ON CREATE SET r.acquired_chapter = t.chapter
            """,
            {"titles": data, "book_id": book_id, "batch_id": batch_id},
        )

        return len(titles)

    # ── Events ──────────────────────────────────────────────────────────

    async def upsert_events(
        self,
        book_id: str,
        chapter_number: int,
        events: list[ExtractedEvent],
        batch_id: str = "",
    ) -> int:
        """Upsert event nodes and link to participants/locations."""
        if not events:
            return 0

        data = [
            {
                "name": e.name,
                "description": e.description,
                "event_type": e.event_type,
                "significance": e.significance,
                "participants": e.participants,
                "location": e.location,
                "chapter": e.chapter or chapter_number,
                "is_flashback": e.is_flashback,
            }
            for e in events
        ]

        # Create events and link to chapter
        await self.execute_write(
            """
            UNWIND $events AS e
            MERGE (ev:Event {name: e.name, chapter_start: e.chapter})
            ON CREATE SET
                ev.description = e.description,
                ev.event_type = e.event_type,
                ev.significance = e.significance,
                ev.is_flashback = e.is_flashback,
                ev.book_id = $book_id,
                ev.batch_id = $batch_id,
                ev.created_at = timestamp()
            ON MATCH SET
                ev.batch_id = $batch_id
            WITH ev, e
            MATCH (chap:Chapter {book_id: $book_id, number: e.chapter})
            MERGE (ev)-[:FIRST_MENTIONED_IN]->(chap)
            """,
            {"events": data, "book_id": book_id, "batch_id": batch_id},
        )

        # Link participants
        participant_data = [
            {"event_name": e.name, "chapter": e.chapter or chapter_number, "participant": p}
            for e in events
            for p in e.participants
            if p
        ]

        if participant_data:
            await self.execute_write(
                """
                UNWIND $links AS l
                MATCH (ev:Event {name: l.event_name, chapter_start: l.chapter})
                MATCH (ch:Character {canonical_name: l.participant})
                MERGE (ch)-[:PARTICIPATES_IN]->(ev)
                """,
                {"links": participant_data},
            )

        # Link locations
        location_data = [
            {"event_name": e.name, "chapter": e.chapter or chapter_number, "location": e.location}
            for e in events
            if e.location
        ]

        if location_data:
            await self.execute_write(
                """
                UNWIND $links AS l
                MATCH (ev:Event {name: l.event_name, chapter_start: l.chapter})
                MATCH (loc:Location {name: l.location})
                MERGE (ev)-[:OCCURS_AT]->(loc)
                """,
                {"links": location_data},
            )

        logger.info(
            "events_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(events),
        )
        return len(events)

    # ── Locations ───────────────────────────────────────────────────────

    async def upsert_locations(
        self,
        book_id: str,
        chapter_number: int,
        locations: list[ExtractedLocation],
        batch_id: str = "",
    ) -> int:
        """Upsert location nodes with parent hierarchy."""
        if not locations:
            return 0

        data = [
            {
                "name": loc.name,
                "description": loc.description,
                "location_type": loc.location_type,
                "parent": loc.parent_location,
            }
            for loc in locations
        ]

        await self.execute_write(
            """
            UNWIND $locs AS l
            MERGE (loc:Location {name: l.name})
            ON CREATE SET
                loc.description = l.description,
                loc.location_type = l.location_type,
                loc.book_id = $book_id,
                loc.batch_id = $batch_id,
                loc.created_at = timestamp()
            ON MATCH SET
                loc.description = CASE
                    WHEN size(l.description) > size(coalesce(loc.description, ''))
                    THEN l.description ELSE loc.description END,
                loc.batch_id = $batch_id
            """,
            {"locs": data, "book_id": book_id, "batch_id": batch_id},
        )

        # Link parent locations
        parent_data = [
            {"name": loc.name, "parent": loc.parent_location}
            for loc in locations
            if loc.parent_location
        ]

        if parent_data:
            await self.execute_write(
                """
                UNWIND $links AS l
                MATCH (child:Location {name: l.name})
                MERGE (parent:Location {name: l.parent})
                MERGE (child)-[:LOCATION_PART_OF]->(parent)
                """,
                {"links": parent_data},
            )

        return len(locations)

    # ── Items ───────────────────────────────────────────────────────────

    async def upsert_items(
        self,
        book_id: str,
        chapter_number: int,
        items: list[ExtractedItem],
        batch_id: str = "",
    ) -> int:
        """Upsert item nodes and link to owners."""
        if not items:
            return 0

        data = [
            {
                "name": i.name,
                "description": i.description,
                "item_type": i.item_type,
                "rarity": i.rarity,
                "owner": i.owner,
            }
            for i in items
        ]

        await self.execute_write(
            """
            UNWIND $items AS i
            MERGE (it:Item {name: i.name})
            ON CREATE SET
                it.description = i.description,
                it.item_type = i.item_type,
                it.rarity = i.rarity,
                it.book_id = $book_id,
                it.batch_id = $batch_id,
                it.created_at = timestamp()
            WITH it, i
            WHERE i.owner <> ''
            MATCH (ch:Character {canonical_name: i.owner})
            MERGE (ch)-[r:POSSESSES]->(it)
            ON CREATE SET r.valid_from_chapter = $chapter
            """,
            {
                "items": data,
                "book_id": book_id,
                "chapter": chapter_number,
                "batch_id": batch_id,
            },
        )

        return len(items)

    # ── Creatures ───────────────────────────────────────────────────────

    async def upsert_creatures(
        self,
        book_id: str,
        chapter_number: int,
        creatures: list[ExtractedCreature],
        batch_id: str = "",
    ) -> int:
        """Upsert creature nodes."""
        if not creatures:
            return 0

        data = [
            {
                "name": c.name,
                "description": c.description,
                "species": c.species,
                "threat_level": c.threat_level,
                "habitat": c.habitat,
            }
            for c in creatures
        ]

        await self.execute_write(
            """
            UNWIND $creatures AS c
            MERGE (cr:Creature {name: c.name})
            ON CREATE SET
                cr.description = c.description,
                cr.species = c.species,
                cr.threat_level = c.threat_level,
                cr.habitat = c.habitat,
                cr.book_id = $book_id,
                cr.batch_id = $batch_id,
                cr.created_at = timestamp()
            """,
            {"creatures": data, "book_id": book_id, "batch_id": batch_id},
        )

        return len(creatures)

    # ── Factions ────────────────────────────────────────────────────────

    async def upsert_factions(
        self,
        book_id: str,
        chapter_number: int,
        factions: list[ExtractedFaction],
        batch_id: str = "",
    ) -> int:
        """Upsert faction nodes."""
        if not factions:
            return 0

        data = [
            {
                "name": f.name,
                "description": f.description,
                "faction_type": f.faction_type,
                "alignment": f.alignment,
            }
            for f in factions
        ]

        await self.execute_write(
            """
            UNWIND $factions AS f
            MERGE (fa:Faction {name: f.name})
            ON CREATE SET
                fa.description = f.description,
                fa.type = f.faction_type,
                fa.alignment = f.alignment,
                fa.book_id = $book_id,
                fa.batch_id = $batch_id,
                fa.created_at = timestamp()
            """,
            {"factions": data, "book_id": book_id, "batch_id": batch_id},
        )

        return len(factions)

    # ── Concepts ────────────────────────────────────────────────────────

    async def upsert_concepts(
        self,
        book_id: str,
        chapter_number: int,
        concepts: list[ExtractedConcept],
        batch_id: str = "",
    ) -> int:
        """Upsert concept nodes."""
        if not concepts:
            return 0

        data = [
            {
                "name": c.name,
                "description": c.description,
                "domain": c.domain,
            }
            for c in concepts
        ]

        await self.execute_write(
            """
            UNWIND $concepts AS c
            MERGE (co:Concept {name: c.name})
            ON CREATE SET
                co.description = c.description,
                co.domain = c.domain,
                co.book_id = $book_id,
                co.batch_id = $batch_id,
                co.created_at = timestamp()
            ON MATCH SET
                co.description = CASE
                    WHEN size(c.description) > size(coalesce(co.description, ''))
                    THEN c.description ELSE co.description END,
                co.batch_id = $batch_id
            """,
            {"concepts": data, "book_id": book_id, "batch_id": batch_id},
        )

        return len(concepts)

    # ── Level Changes ────────────────────────────────────────────────

    async def upsert_level_changes(
        self,
        book_id: str,
        chapter_number: int,
        level_changes: list[ExtractedLevelChange],
        batch_id: str = "",
    ) -> int:
        """Upsert level change events linked to characters."""
        if not level_changes:
            return 0

        data = [
            {
                "character": lc.character,
                "old_level": lc.old_level,
                "new_level": lc.new_level,
                "realm": lc.realm,
                "chapter": lc.chapter or chapter_number,
            }
            for lc in level_changes
            if lc.character
        ]

        if not data:
            return 0

        await self.execute_write(
            """
            UNWIND $changes AS lc
            MATCH (ch:Character {canonical_name: lc.character})
            MERGE (ev:Event {
                name: ch.canonical_name + ' levels to ' + coalesce(toString(lc.new_level), '?'),
                chapter_start: lc.chapter
            })
            ON CREATE SET
                ev.event_type = 'level_change',
                ev.significance = 'moderate',
                ev.description = ch.canonical_name + ' leveled from ' +
                    coalesce(toString(lc.old_level), '?') + ' to ' +
                    coalesce(toString(lc.new_level), '?'),
                ev.old_level = lc.old_level,
                ev.new_level = lc.new_level,
                ev.realm = lc.realm,
                ev.book_id = $book_id,
                ev.batch_id = $batch_id,
                ev.created_at = timestamp()
            MERGE (ch)-[:PARTICIPATES_IN]->(ev)
            WITH ch, lc
            SET ch.level = CASE
                WHEN lc.new_level IS NOT NULL AND (ch.level IS NULL OR lc.new_level > ch.level)
                THEN lc.new_level ELSE ch.level END
            """,
            {"changes": data, "book_id": book_id, "batch_id": batch_id},
        )

        logger.info(
            "level_changes_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(data),
        )
        return len(data)

    # ── Stat Changes ─────────────────────────────────────────────────

    async def upsert_stat_changes(
        self,
        book_id: str,
        chapter_number: int,
        stat_changes: list[ExtractedStatChange],
        batch_id: str = "",
    ) -> int:
        """Upsert stat changes linked to characters."""
        if not stat_changes:
            return 0

        data = [
            {
                "character": sc.character,
                "stat_name": sc.stat_name,
                "value": sc.value,
            }
            for sc in stat_changes
            if sc.character and sc.stat_name
        ]

        if not data:
            return 0

        await self.execute_write(
            """
            UNWIND $changes AS sc
            MATCH (ch:Character {canonical_name: sc.character})
            MERGE (stat:Concept {name: sc.stat_name, domain: 'stat'})
            ON CREATE SET
                stat.description = sc.stat_name + ' stat',
                stat.book_id = $book_id,
                stat.batch_id = $batch_id,
                stat.created_at = timestamp()
            MERGE (ch)-[r:HAS_STAT]->(stat)
            ON CREATE SET r.value = sc.value, r.valid_from_chapter = $chapter
            ON MATCH SET r.value = r.value + sc.value
            """,
            {
                "changes": data,
                "book_id": book_id,
                "chapter": chapter_number,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "stat_changes_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(data),
        )
        return len(data)

    # ── Grounding links ────────────────────────────────────────────────

    # Mapping from LangExtract extraction_class to Neo4j label + match property
    _GROUNDING_LABEL_MAP: dict[str, tuple[str, str]] = {
        "character": ("Character", "canonical_name"),
        "skill": ("Skill", "name"),
        "class": ("Class", "name"),
        "title": ("Title", "name"),
        "event": ("Event", "name"),
        "location": ("Location", "name"),
        "item": ("Item", "name"),
        "creature": ("Creature", "name"),
        "faction": ("Faction", "name"),
        "concept": ("Concept", "name"),
    }

    async def store_mentions(
        self,
        book_id: str,
        chapter_number: int,
        grounded: list[GroundedEntity],
    ) -> int:
        """Store MENTIONED_IN relationships between entities and chapter.

        Creates one relationship PER MENTION (no merging/expanding).
        Uses CREATE instead of MERGE — each mention is independent.
        This fixes the span expansion bug where MERGE ON MATCH expanded
        char offsets to min/max, causing entire text blocks to be
        annotated as a single entity.

        Uses a label-aware UNWIND strategy: groups entities by Neo4j label,
        then runs one CREATE per label group (Neo4j doesn't allow variable labels).
        Also stores a JSON summary on the Chapter node for quick access.
        """
        if not grounded:
            return 0

        linked = 0

        # Group by entity type for label-aware Cypher
        by_label: dict[str, list[dict]] = {}
        for g in grounded:
            label_info = self._GROUNDING_LABEL_MAP.get(g.entity_type)
            if label_info is None:
                continue
            label, prop = label_info
            if label not in by_label:
                by_label[label] = []
            by_label[label].append(
                {
                    "entity_name": g.entity_name,
                    "match_prop": prop,
                    "char_start": g.char_offset_start,
                    "char_end": g.char_offset_end,
                    "mention_text": g.extraction_text[:200],
                    "mention_type": g.attributes.get("mention_type", "langextract") if g.attributes else "langextract",
                    "confidence": g.confidence,
                    "alignment_status": g.alignment_status,
                    "pass_name": g.pass_name,
                }
            )

        # Create MENTIONED_IN relationships per label group
        for label, entries in by_label.items():
            prop_name = entries[0]["match_prop"]
            query = f"""
                UNWIND $entries AS e
                MATCH (chapter:Chapter {{book_id: $book_id, number: $chapter_num}})
                MATCH (entity:{label} {{{prop_name}: e.entity_name}})
                CREATE (entity)-[:MENTIONED_IN {{
                    char_start: e.char_start,
                    char_end: e.char_end,
                    mention_text: e.mention_text,
                    mention_type: e.mention_type,
                    confidence: e.confidence,
                    alignment_status: e.alignment_status,
                    pass_name: e.pass_name
                }}]->(chapter)
            """
            await self.execute_write(
                query,
                {
                    "book_id": book_id,
                    "chapter_num": chapter_number,
                    "entries": entries,
                },
            )
            linked += len(entries)

        # Store summary JSON on Chapter for quick access
        import json

        summary = [
            {
                "entity_type": g.entity_type,
                "entity_name": g.entity_name,
                "char_start": g.char_offset_start,
                "char_end": g.char_offset_end,
                "mention_type": g.attributes.get("mention_type", "langextract") if g.attributes else "langextract",
                "pass_name": g.pass_name,
            }
            for g in grounded
        ]
        await self.execute_write(
            """
            MATCH (c:Chapter {book_id: $book_id, number: $chapter})
            SET c.mention_data = $mention_json,
                c.mention_count = $count
            """,
            {
                "book_id": book_id,
                "chapter": chapter_number,
                "mention_json": json.dumps(summary, default=str),
                "count": len(grounded),
            },
        )

        logger.info(
            "mentions_stored",
            book_id=book_id,
            chapter=chapter_number,
            total=len(grounded),
            linked=linked,
            labels=list(by_label.keys()),
        )
        return linked

    # ── Cross-book entity queries ────────────────────────────────────────

    async def get_series_entities(
        self,
        series_name: str,
        exclude_book_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all entities from books in a series (for cross-book dedup).

        Returns entity names, types, and aliases for reconciliation context.
        Used when processing Book N to load known entities from Books 1..N-1.

        Args:
            series_name: Name of the series to query.
            exclude_book_id: Optional book ID to exclude (current book).

        Returns:
            List of dicts with name, canonical_name, entity_types, aliases,
            and description for each entity in the series.
        """
        query = """
        MATCH (s:Series {name: $series_name})-[:CONTAINS_WORK]->(b:Book)
        WHERE ($exclude_book_id IS NULL OR b.id <> $exclude_book_id)
        WITH b
        MATCH (entity)-[:MENTIONED_IN|GROUNDED_IN]->(c:Chapter {book_id: b.id})
        WITH DISTINCT entity, labels(entity) AS labels
        RETURN entity.name AS name,
               entity.canonical_name AS canonical_name,
               [l IN labels WHERE l IN [
                   'Character','Skill','Class','Title','Event',
                   'Location','Item','Creature','Faction','Concept'
               ]] AS entity_types,
               entity.aliases AS aliases,
               entity.description AS description
        ORDER BY entity.name
        """
        results = await self.execute_read(
            query,
            {"series_name": series_name, "exclude_book_id": exclude_book_id},
        )

        logger.info(
            "series_entities_loaded",
            series_name=series_name,
            exclude_book_id=exclude_book_id,
            entity_count=len(results),
        )
        return results

    # ── Bulk upsert from extraction result ─────────────────────────────

    async def upsert_extraction_result(
        self,
        result: ChapterExtractionResult,
    ) -> dict[str, int]:
        """Upsert all entities from a complete extraction result.

        Args:
            result: ChapterExtractionResult with all passes.

        Returns:
            Dict of entity_type -> count upserted.
        """
        book_id = result.book_id
        chapter = result.chapter_number
        batch_id = str(uuid.uuid4())
        counts: dict[str, int] = {}

        # Phase 1: Characters + relationships (sequential — relationships reference characters)
        counts["characters"] = await self.upsert_characters(
            book_id,
            chapter,
            result.characters.characters,
            batch_id,
        )
        counts["relationships"] = await self.upsert_relationships(
            book_id,
            chapter,
            result.characters.relationships,
            batch_id,
        )

        # Phase 2: All independent entity types in parallel
        (
            counts["skills"],
            counts["classes"],
            counts["titles"],
            counts["level_changes"],
            counts["stat_changes"],
            counts["events"],
            counts["locations"],
            counts["items"],
            counts["creatures"],
            counts["factions"],
            counts["concepts"],
        ) = await asyncio.gather(
            self.upsert_skills(book_id, chapter, result.systems.skills, batch_id),
            self.upsert_classes(book_id, chapter, result.systems.classes, batch_id),
            self.upsert_titles(book_id, chapter, result.systems.titles, batch_id),
            self.upsert_level_changes(book_id, chapter, result.systems.level_changes, batch_id),
            self.upsert_stat_changes(book_id, chapter, result.systems.stat_changes, batch_id),
            self.upsert_events(book_id, chapter, result.events.events, batch_id),
            self.upsert_locations(book_id, chapter, result.lore.locations, batch_id),
            self.upsert_items(book_id, chapter, result.lore.items, batch_id),
            self.upsert_creatures(book_id, chapter, result.lore.creatures, batch_id),
            self.upsert_factions(book_id, chapter, result.lore.factions, batch_id),
            self.upsert_concepts(book_id, chapter, result.lore.concepts, batch_id),
        )

        # Phase 3: Mentions (depends on entities existing)
        counts["mentions"] = await self.store_mentions(
            book_id,
            chapter,
            result.grounded_entities,
        )

        total = sum(counts.values())
        logger.info(
            "extraction_result_upserted",
            book_id=book_id,
            chapter=chapter,
            batch_id=batch_id,
            total_upserted=total,
            counts=counts,
        )

        return counts
