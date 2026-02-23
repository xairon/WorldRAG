"""Neo4j repository for KG entities (characters, skills, events, etc.).

Handles MERGE operations for all ontology entity types with temporal
properties and grounding links. Uses UNWIND for batch efficiency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
        ExtractedLocation,
        ExtractedRelationship,
        ExtractedSkill,
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
                ch.created_at = timestamp()
            ON MATCH SET
                ch.description = CASE
                    WHEN size(c.description) > size(coalesce(ch.description, ''))
                    THEN c.description ELSE ch.description END,
                ch.aliases = ch.aliases + [a IN c.aliases WHERE NOT a IN ch.aliases]
            WITH ch, c
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (ch)-[:MENTIONED_IN]->(chap)
            """,
            {
                "chars": data,
                "book_id": book_id,
                "chapter": chapter_number,
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
                rel.book_id = $book_id
            """,
            {"rels": data, "book_id": book_id},
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
                sk.created_at = timestamp()
            ON MATCH SET
                sk.description = CASE
                    WHEN size(s.description) > size(coalesce(sk.description, ''))
                    THEN s.description ELSE sk.description END,
                sk.rank = CASE
                    WHEN s.rank <> '' THEN s.rank ELSE sk.rank END
            WITH sk, s
            WHERE s.owner <> ''
            MATCH (ch:Character {canonical_name: s.owner})
            MERGE (ch)-[r:HAS_SKILL]->(sk)
            ON CREATE SET r.valid_from_chapter = s.chapter
            """,
            {"skills": data, "book_id": book_id},
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
                cls.created_at = timestamp()
            WITH cls, c
            WHERE c.owner <> ''
            MATCH (ch:Character {canonical_name: c.owner})
            MERGE (ch)-[r:HAS_CLASS]->(cls)
            ON CREATE SET r.valid_from_chapter = c.chapter
            """,
            {"classes": data, "book_id": book_id},
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
                ti.created_at = timestamp()
            WITH ti, t
            WHERE t.owner <> ''
            MATCH (ch:Character {canonical_name: t.owner})
            MERGE (ch)-[r:HAS_TITLE]->(ti)
            ON CREATE SET r.acquired_chapter = t.chapter
            """,
            {"titles": data, "book_id": book_id},
        )

        return len(titles)

    # ── Events ──────────────────────────────────────────────────────────

    async def upsert_events(
        self,
        book_id: str,
        chapter_number: int,
        events: list[ExtractedEvent],
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
                ev.created_at = timestamp()
            WITH ev, e
            MATCH (chap:Chapter {book_id: $book_id, number: e.chapter})
            MERGE (ev)-[:FIRST_MENTIONED_IN]->(chap)
            """,
            {"events": data, "book_id": book_id},
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
                loc.created_at = timestamp()
            ON MATCH SET
                loc.description = CASE
                    WHEN size(l.description) > size(coalesce(loc.description, ''))
                    THEN l.description ELSE loc.description END
            """,
            {"locs": data, "book_id": book_id},
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
                it.created_at = timestamp()
            WITH it, i
            WHERE i.owner <> ''
            MATCH (ch:Character {canonical_name: i.owner})
            MERGE (ch)-[r:POSSESSES]->(it)
            ON CREATE SET r.valid_from_chapter = $chapter
            """,
            {"items": data, "book_id": book_id, "chapter": chapter_number},
        )

        return len(items)

    # ── Creatures ───────────────────────────────────────────────────────

    async def upsert_creatures(
        self,
        book_id: str,
        chapter_number: int,
        creatures: list[ExtractedCreature],
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
                cr.created_at = timestamp()
            """,
            {"creatures": data, "book_id": book_id},
        )

        return len(creatures)

    # ── Factions ────────────────────────────────────────────────────────

    async def upsert_factions(
        self,
        book_id: str,
        chapter_number: int,
        factions: list[ExtractedFaction],
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
                fa.created_at = timestamp()
            """,
            {"factions": data, "book_id": book_id},
        )

        return len(factions)

    # ── Concepts ────────────────────────────────────────────────────────

    async def upsert_concepts(
        self,
        book_id: str,
        chapter_number: int,
        concepts: list[ExtractedConcept],
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
                co.created_at = timestamp()
            ON MATCH SET
                co.description = CASE
                    WHEN size(c.description) > size(coalesce(co.description, ''))
                    THEN c.description ELSE co.description END
            """,
            {"concepts": data, "book_id": book_id},
        )

        return len(concepts)

    # ── Grounding links ────────────────────────────────────────────────

    async def store_grounding(
        self,
        book_id: str,
        chapter_number: int,
        grounded: list[GroundedEntity],
    ) -> int:
        """Store grounding links between entities and chunks.

        Creates GROUNDED_IN relationships with character offsets
        from the source text for highlighting in the reader.
        """
        if not grounded:
            return 0

        data = [
            {
                "entity_type": g.entity_type,
                "entity_name": g.entity_name,
                "char_start": g.char_offset_start,
                "char_end": g.char_offset_end,
                "pass_name": g.pass_name,
            }
            for g in grounded
        ]

        # Store grounding data on the chapter node as JSON
        # (actual chunk-level grounding requires chunk offset mapping)
        import json

        grounding_json = json.dumps(data, default=str)

        await self.execute_write(
            """
            MATCH (c:Chapter {book_id: $book_id, number: $chapter})
            SET c.grounding_data = $grounding_json,
                c.grounding_count = $count
            """,
            {
                "book_id": book_id,
                "chapter": chapter_number,
                "grounding_json": grounding_json,
                "count": len(grounded),
            },
        )

        logger.info(
            "grounding_stored",
            book_id=book_id,
            chapter=chapter_number,
            count=len(grounded),
        )
        return len(grounded)

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
        counts: dict[str, int] = {}

        # Characters
        counts["characters"] = await self.upsert_characters(
            book_id, chapter, result.characters.characters,
        )
        counts["relationships"] = await self.upsert_relationships(
            book_id, chapter, result.characters.relationships,
        )

        # Systems
        counts["skills"] = await self.upsert_skills(
            book_id, chapter, result.systems.skills,
        )
        counts["classes"] = await self.upsert_classes(
            book_id, chapter, result.systems.classes,
        )
        counts["titles"] = await self.upsert_titles(
            book_id, chapter, result.systems.titles,
        )

        # Events
        counts["events"] = await self.upsert_events(
            book_id, chapter, result.events.events,
        )

        # Lore
        counts["locations"] = await self.upsert_locations(
            book_id, chapter, result.lore.locations,
        )
        counts["items"] = await self.upsert_items(
            book_id, chapter, result.lore.items,
        )
        counts["creatures"] = await self.upsert_creatures(
            book_id, chapter, result.lore.creatures,
        )
        counts["factions"] = await self.upsert_factions(
            book_id, chapter, result.lore.factions,
        )
        counts["concepts"] = await self.upsert_concepts(
            book_id, chapter, result.lore.concepts,
        )

        # Grounding
        counts["grounding"] = await self.store_grounding(
            book_id, chapter, result.grounded_entities,
        )

        total = sum(counts.values())
        logger.info(
            "extraction_result_upserted",
            book_id=book_id,
            chapter=chapter,
            total_upserted=total,
            counts=counts,
        )

        return counts
