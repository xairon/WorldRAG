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

# ── Genre sub_type → Neo4j label mapping ────────────────────────────────
# V4 GenreEntity entities arrive with sub_type (e.g. "bloodline", "floor").
# Core genre types (skill, class, title, system, race) and layer-3 types
# (bloodline, profession, church) have dedicated upsert methods.
# This mapping covers ALL sub_types for the fallback generic upsert.
_GENRE_SUBTYPE_LABEL_MAP: dict[str, str] = {
    "skill": "Skill",
    "class": "Class",
    "title": "Title",
    "system": "System",
    "race": "Race",
    "bloodline": "Bloodline",
    "profession": "Profession",
    "church": "PrimordialChurch",
    "alchemy_recipe": "AlchemyRecipe",
    "floor": "Floor",
    "quest": "QuestObjective",
    "achievement": "Achievement",
    "realm": "Realm",
}

# Types that already have dedicated upsert methods in Phase 2
_HANDLED_ENTITY_TYPES: set[str] = {
    "character",
    "skill",
    "class",
    "title",
    "event",
    "location",
    "item",
    "creature",
    "faction",
    "concept",
    "level_change",
    "stat_change",
    "bloodline",
    "profession",
    "church",
    "arc",
    "prophecy",
}


class EntityRepository(Neo4jRepository):
    """Repository for KG entity CRUD operations."""

    # ── Characters ──────────────────────────────────────────────────────

    async def upsert_characters(
        self,
        book_id: str,
        chapter_number: int,
        characters: list[ExtractedCharacter],
        batch_id: str = "",
        ontology_version: str = "",
    ) -> int:
        """Upsert character nodes. MERGE on canonical_name."""
        if not characters:
            return 0

        data = [
            {
                "name": c.name,
                "canonical_name": (c.canonical_name or c.name).lower().strip(),
                "aliases": c.aliases,
                "description": c.description,
                "role": c.role,
                "species": c.species,
                "first_chapter": c.first_appearance_chapter or chapter_number,
                "confidence": getattr(c, "confidence", 1.0),
            }
            for c in characters
        ]

        version_clause = ""
        if ontology_version:
            version_clause = ", ch.ontology_version = $ontology_version"

        await self.execute_write(
            f"""
            UNWIND $chars AS c
            MERGE (ch:Character {{canonical_name: c.canonical_name, book_id: $book_id}})
            ON CREATE SET
                ch.name = c.name,
                ch.aliases = c.aliases,
                ch.description = c.description,
                ch.role = c.role,
                ch.species = c.species,
                ch.first_appearance_chapter = c.first_chapter,
                ch.confidence = c.confidence,
                ch.batch_id = $batch_id,
                ch.created_at = timestamp()
                {version_clause}
            ON MATCH SET
                ch.description = CASE
                    WHEN size(c.description) > size(coalesce(ch.description, ''))
                    THEN c.description ELSE ch.description END,
                ch.aliases = ch.aliases + [a IN c.aliases WHERE NOT a IN ch.aliases],
                ch.confidence = CASE
                    WHEN c.confidence > coalesce(ch.confidence, 0.0)
                    THEN c.confidence ELSE ch.confidence END,
                ch.batch_id = $batch_id
                {version_clause}
            WITH ch, c
            MATCH (chap:Chapter {{book_id: $book_id, number: $chapter}})
            MERGE (ch)-[:MENTIONED_IN]->(chap)
            """,
            {
                "chars": data,
                "book_id": book_id,
                "chapter": chapter_number,
                "batch_id": batch_id,
                "ontology_version": ontology_version,
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
                "temporal_order": getattr(r, "temporal_order", None),
                "confidence": getattr(r, "confidence", 1.0),
            }
            for r in relationships
            if r.source and r.target
        ]

        if not data:
            return 0

        # Process relations one by one to avoid cartesian products from label-free MATCH.
        # Uses f-string for dynamic relationship type (safe: sanitized from controlled LLM output).
        total_created = 0
        for rel in data:
            rel_type = rel["rel_type"].upper().replace(" ", "_").replace("-", "_")
            rel_type = "".join(c for c in rel_type if c.isalnum() or c == "_")
            if not rel_type:
                rel_type = "RELATES_TO"
            _, summary = await self.execute_write_with_summary(
                f"""
                WITH $rel AS r
                MATCH (a {{book_id: $book_id}})
                WHERE (a.canonical_name = toLower(r.source) OR toLower(a.name) = toLower(r.source))
                  AND NOT a:Book AND NOT a:Chapter AND NOT a:Chunk AND NOT a:Paragraph
                WITH a, r LIMIT 1
                MATCH (b {{book_id: $book_id}})
                WHERE (b.canonical_name = toLower(r.target) OR toLower(b.name) = toLower(r.target))
                  AND NOT b:Book AND NOT b:Chapter AND NOT b:Chunk AND NOT b:Paragraph
                WITH a, b, r LIMIT 1
                MERGE (a)-[rel:{rel_type} {{valid_from_chapter: r.since_chapter}}]->(b)
                ON CREATE SET
                    rel.subtype = r.subtype,
                    rel.context = r.context,
                    rel.book_id = $book_id,
                    rel.batch_id = $batch_id,
                    rel.type = r.rel_type,
                    rel.temporal_order = r.temporal_order,
                    rel.confidence = r.confidence
                RETURN rel
                """,
                {"rel": rel, "book_id": book_id, "batch_id": batch_id},
            )
            total_created += summary.counters.relationships_created
        created = total_created
        if created == 0 and len(data) > 0:
            logger.warning(
                "v4_relations_zero_created",
                book_id=book_id,
                chapter=chapter_number,
                attempted=len(data),
                hint="source/target canonical_name may not match any existing entity",
            )

        logger.info(
            "relationships_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(data),
            created=created,
        )
        return len(data)

    # ── Skills ──────────────────────────────────────────────────────────

    async def upsert_skills(
        self,
        book_id: str,
        chapter_number: int,
        skills: list[ExtractedSkill],
        batch_id: str = "",
        ontology_version: str = "",
    ) -> int:
        """Upsert skill nodes and link to owner characters."""
        if not skills:
            return 0

        data = [
            {
                "name": s.name.lower().strip(),
                "description": s.description,
                "skill_type": s.skill_type,
                "rank": s.rank,
                "owner": s.owner,
                "chapter": s.acquired_chapter or chapter_number,
                "confidence": getattr(s, "confidence", 1.0),
            }
            for s in skills
        ]

        version_clause = ""
        if ontology_version:
            version_clause = ", sk.ontology_version = $ontology_version"

        await self.execute_write(
            f"""
            UNWIND $skills AS s
            MERGE (sk:Skill {{name: s.name, book_id: $book_id}})
            ON CREATE SET
                sk.description = s.description,
                sk.skill_type = s.skill_type,
                sk.rank = s.rank,
                sk.confidence = s.confidence,
                sk.batch_id = $batch_id,
                sk.created_at = timestamp()
                {version_clause}
            ON MATCH SET
                sk.description = CASE
                    WHEN size(s.description) > size(coalesce(sk.description, ''))
                    THEN s.description ELSE sk.description END,
                sk.rank = CASE
                    WHEN s.rank <> '' THEN s.rank ELSE sk.rank END,
                sk.batch_id = $batch_id
                {version_clause}
            WITH sk, s
            WHERE s.owner <> ''
            MATCH (ch:Character {{canonical_name: s.owner, book_id: $book_id}})
            MERGE (ch)-[r:HAS_SKILL]->(sk)
            ON CREATE SET r.valid_from_chapter = s.chapter
            """,
            {
                "skills": data,
                "book_id": book_id,
                "batch_id": batch_id,
                "ontology_version": ontology_version,
            },
        )

        # G4: Close open HAS_SKILL when a skill evolves (rank changes)
        # If the same owner gains the same skill again with a new rank,
        # the MERGE above updates the Skill node's rank. We close any
        # open HAS_SKILL edges where the stored rank differs from the new rank,
        # then a fresh edge is created by re-running MERGE on next encounter.
        skills_with_rank = [s for s in data if s["owner"] and s["rank"]]
        if skills_with_rank:
            await self.execute_write(
                """
                UNWIND $skills AS s
                MATCH (ch:Character {canonical_name: s.owner, book_id: $book_id})
                      -[r:HAS_SKILL]->(sk:Skill {name: s.name, book_id: $book_id})
                WHERE r.valid_to_chapter IS NULL
                  AND r.valid_from_chapter < s.chapter
                SET r.valid_to_chapter = s.chapter - 1
                WITH ch, s
                MATCH (sk:Skill {name: s.name, book_id: $book_id})
                MERGE (ch)-[r2:HAS_SKILL {valid_from_chapter: s.chapter}]->(sk)
                ON CREATE SET r2.rank = s.rank, r2.batch_id = $batch_id
                """,
                {
                    "skills": skills_with_rank,
                    "book_id": book_id,
                    "batch_id": batch_id,
                },
            )

        # V3: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": s["owner"],
                "category": "skill",
                "name": s["name"],
                "action": "acquire",
            }
            for s in data
            if s["owner"]
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

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
                "name": c.name.lower().strip(),
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
            MERGE (cls:Class {name: c.name, book_id: $book_id})
            ON CREATE SET
                cls.description = c.description,
                cls.tier = c.tier,
                cls.batch_id = $batch_id,
                cls.created_at = timestamp()
            WITH cls, c
            WHERE c.owner <> ''
            MATCH (ch:Character {canonical_name: c.owner, book_id: $book_id})
            MERGE (ch)-[r:HAS_CLASS]->(cls)
            ON CREATE SET r.valid_from_chapter = c.chapter
            """,
            {"classes": data, "book_id": book_id, "batch_id": batch_id},
        )

        # G4: Close open HAS_CLASS when a character gets a new/evolved class
        # When a new class is acquired in a chapter, close any previous open
        # HAS_CLASS edges for that character (class evolution replaces old class)
        classes_with_owner = [c for c in data if c["owner"]]
        if classes_with_owner:
            await self.execute_write(
                """
                UNWIND $classes AS c
                MATCH (ch:Character {canonical_name: c.owner, book_id: $book_id})
                      -[r:HAS_CLASS]->(cls:Class {book_id: $book_id})
                WHERE r.valid_to_chapter IS NULL
                  AND cls.name <> c.name
                  AND r.valid_from_chapter < c.chapter
                SET r.valid_to_chapter = c.chapter - 1
                """,
                {
                    "classes": classes_with_owner,
                    "book_id": book_id,
                },
            )

        # V3: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": c["owner"],
                "category": "class",
                "name": c["name"],
                "action": "acquire",
            }
            for c in data
            if c["owner"]
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

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
                "name": t.name.lower().strip(),
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
            MERGE (ti:Title {name: t.name, book_id: $book_id})
            ON CREATE SET
                ti.description = t.description,
                ti.effects = t.effects,
                ti.batch_id = $batch_id,
                ti.created_at = timestamp()
            WITH ti, t
            WHERE t.owner <> ''
            MATCH (ch:Character {canonical_name: t.owner, book_id: $book_id})
            MERGE (ch)-[r:HAS_TITLE]->(ti)
            ON CREATE SET r.acquired_chapter = t.chapter
            """,
            {"titles": data, "book_id": book_id, "batch_id": batch_id},
        )

        # V3: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": t["owner"],
                "category": "title",
                "name": t["name"],
                "action": "acquire",
            }
            for t in data
            if t["owner"]
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

        return len(titles)

    # ── Events ──────────────────────────────────────────────────────────

    async def upsert_events(
        self,
        book_id: str,
        chapter_number: int,
        events: list[ExtractedEvent],
        batch_id: str = "",
        ontology_version: str = "",
    ) -> int:
        """Upsert event nodes and link to participants/locations."""
        if not events:
            return 0

        data = [
            {
                "name": e.name.lower().strip(),
                "description": e.description,
                "event_type": e.event_type,
                "significance": e.significance,
                "participants": e.participants,
                "location": e.location,
                "chapter": e.chapter or chapter_number,
                "is_flashback": e.is_flashback,
                "confidence": getattr(e, "confidence", 1.0),
            }
            for e in events
        ]

        version_clause = ""
        if ontology_version:
            version_clause = ", ev.ontology_version = $ontology_version"

        # Create events and link to chapter
        await self.execute_write(
            f"""
            UNWIND $events AS e
            MERGE (ev:Event {{name: e.name, chapter_start: e.chapter, book_id: $book_id}})
            ON CREATE SET
                ev.description = e.description,
                ev.event_type = e.event_type,
                ev.significance = e.significance,
                ev.is_flashback = e.is_flashback,
                ev.confidence = e.confidence,
                ev.batch_id = $batch_id,
                ev.created_at = timestamp()
                {version_clause}
            ON MATCH SET
                ev.batch_id = $batch_id
                {version_clause}
            WITH ev, e
            MATCH (chap:Chapter {{book_id: $book_id, number: e.chapter}})
            MERGE (ev)-[:FIRST_MENTIONED_IN]->(chap)
            """,
            {
                "events": data,
                "book_id": book_id,
                "batch_id": batch_id,
                "ontology_version": ontology_version,
            },
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
                MATCH (ev:Event {name: l.event_name, chapter_start: l.chapter, book_id: $book_id})
                MATCH (ch:Character {canonical_name: l.participant, book_id: $book_id})
                MERGE (ch)-[:PARTICIPATES_IN]->(ev)
                """,
                {"links": participant_data, "book_id": book_id},
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
                MATCH (ev:Event {name: l.event_name, chapter_start: l.chapter, book_id: $book_id})
                MATCH (loc:Location {name: l.location, book_id: $book_id})
                MERGE (ev)-[:OCCURS_AT]->(loc)
                """,
                {"links": location_data, "book_id": book_id},
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
                "name": loc.name.lower().strip(),
                "canonical_name": (loc.canonical_name or loc.name).lower().strip(),
                "description": loc.description,
                "location_type": loc.location_type,
                "parent": loc.parent_location,
                "confidence": getattr(loc, "confidence", 1.0),
            }
            for loc in locations
        ]

        await self.execute_write(
            """
            UNWIND $locs AS l
            MERGE (loc:Location {name: l.name, book_id: $book_id})
            ON CREATE SET
                loc.canonical_name = l.canonical_name,
                loc.description = l.description,
                loc.location_type = l.location_type,
                loc.confidence = l.confidence,
                loc.batch_id = $batch_id,
                loc.created_at = timestamp()
            ON MATCH SET
                loc.canonical_name = l.canonical_name,
                loc.description = CASE
                    WHEN size(l.description) > size(coalesce(loc.description, ''))
                    THEN l.description ELSE loc.description END,
                loc.confidence = CASE
                    WHEN l.confidence > coalesce(loc.confidence, 0.0)
                    THEN l.confidence ELSE loc.confidence END,
                loc.batch_id = $batch_id
            WITH loc, l
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (loc)-[:MENTIONED_IN]->(chap)
            """,
            {"locs": data, "book_id": book_id, "batch_id": batch_id, "chapter": chapter_number},
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
                MATCH (child:Location {name: l.name, book_id: $book_id})
                MERGE (parent:Location {name: l.parent, book_id: $book_id})
                MERGE (child)-[:LOCATION_PART_OF]->(parent)
                """,
                {"links": parent_data, "book_id": book_id},
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
                "name": i.name.lower().strip(),
                "canonical_name": (getattr(i, "canonical_name", "") or i.name).lower().strip(),
                "description": getattr(i, "description", ""),
                "item_type": i.item_type,
                "rarity": i.rarity,
                "owner": i.owner,
                "confidence": getattr(i, "confidence", 1.0),
            }
            for i in items
        ]

        await self.execute_write(
            """
            UNWIND $items AS i
            MERGE (it:Item {name: i.name, book_id: $book_id})
            ON CREATE SET
                it.canonical_name = i.canonical_name,
                it.description = i.description,
                it.item_type = i.item_type,
                it.rarity = i.rarity,
                it.confidence = i.confidence,
                it.batch_id = $batch_id,
                it.created_at = timestamp()
            WITH it, i
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (it)-[:MENTIONED_IN]->(chap)
            WITH it, i
            WHERE i.owner <> ''
            MATCH (ch:Character {canonical_name: i.owner, book_id: $book_id})
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

        # V3: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": i["owner"],
                "category": "item",
                "name": i["name"],
                "action": "acquire",
            }
            for i in data
            if i["owner"]
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

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
                "name": c.name.lower().strip(),
                "canonical_name": (getattr(c, "canonical_name", "") or c.name).lower().strip(),
                "description": c.description,
                "species": c.species,
                "threat_level": c.threat_level,
                "habitat": c.habitat,
                "confidence": getattr(c, "confidence", 1.0),
            }
            for c in creatures
        ]

        await self.execute_write(
            """
            UNWIND $creatures AS c
            MERGE (cr:Creature {name: c.name, book_id: $book_id})
            ON CREATE SET
                cr.canonical_name = c.canonical_name,
                cr.description = c.description,
                cr.species = c.species,
                cr.threat_level = c.threat_level,
                cr.habitat = c.habitat,
                cr.confidence = c.confidence,
                cr.batch_id = $batch_id,
                cr.created_at = timestamp()
            WITH cr, c
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (cr)-[:MENTIONED_IN]->(chap)
            """,
            {
                "creatures": data,
                "book_id": book_id,
                "batch_id": batch_id,
                "chapter": chapter_number,
            },
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
                "name": f.name.lower().strip(),
                "canonical_name": (getattr(f, "canonical_name", "") or f.name).lower().strip(),
                "description": f.description,
                "faction_type": f.faction_type,
                "alignment": f.alignment,
                "confidence": getattr(f, "confidence", 1.0),
            }
            for f in factions
        ]

        await self.execute_write(
            """
            UNWIND $factions AS f
            MERGE (fa:Faction {name: f.name, book_id: $book_id})
            ON CREATE SET
                fa.canonical_name = f.canonical_name,
                fa.description = f.description,
                fa.type = f.faction_type,
                fa.alignment = f.alignment,
                fa.confidence = f.confidence,
                fa.batch_id = $batch_id,
                fa.created_at = timestamp()
            WITH fa, f
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (fa)-[:MENTIONED_IN]->(chap)
            """,
            {"factions": data, "book_id": book_id, "batch_id": batch_id, "chapter": chapter_number},
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
                "name": c.name.lower().strip(),
                "canonical_name": (getattr(c, "canonical_name", "") or c.name).lower().strip(),
                "description": c.description,
                "domain": c.domain,
                "confidence": getattr(c, "confidence", 1.0),
            }
            for c in concepts
        ]

        await self.execute_write(
            """
            UNWIND $concepts AS c
            MERGE (co:Concept {name: c.name, book_id: $book_id})
            ON CREATE SET
                co.canonical_name = c.canonical_name,
                co.description = c.description,
                co.domain = c.domain,
                co.confidence = c.confidence,
                co.batch_id = $batch_id,
                co.created_at = timestamp()
            ON MATCH SET
                co.description = CASE
                    WHEN size(c.description) > size(coalesce(co.description, ''))
                    THEN c.description ELSE co.description END,
                co.confidence = CASE
                    WHEN c.confidence > coalesce(co.confidence, 0.0)
                    THEN c.confidence ELSE co.confidence END,
                co.batch_id = $batch_id
            WITH co, c
            MATCH (chap:Chapter {book_id: $book_id, number: $chapter})
            MERGE (co)-[:MENTIONED_IN]->(chap)
            """,
            {"concepts": data, "book_id": book_id, "batch_id": batch_id, "chapter": chapter_number},
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
            MATCH (ch:Character {canonical_name: lc.character, book_id: $book_id})
            MERGE (ev:Event {
                name: ch.canonical_name + ' levels to ' + coalesce(toString(lc.new_level), '?'),
                chapter_start: lc.chapter,
                book_id: $book_id
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

        # G4: Create temporal AT_LEVEL edges — close previous open level, then create new
        await self.execute_write(
            """
            UNWIND $changes AS lc
            MATCH (ch:Character {canonical_name: lc.character, book_id: $book_id})
            MATCH (b:Book {id: $book_id})
            WHERE lc.new_level IS NOT NULL
            // Close any open AT_LEVEL relationships with a lower level
            OPTIONAL MATCH (ch)-[old:AT_LEVEL]->(b)
            WHERE old.valid_to_chapter IS NULL AND old.level < lc.new_level
            SET old.valid_to_chapter = lc.chapter - 1
            WITH ch, lc, b
            WHERE lc.new_level IS NOT NULL
            MERGE (ch)-[r:AT_LEVEL {level: lc.new_level, valid_from_chapter: lc.chapter}]->(b)
            ON CREATE SET
                r.realm = lc.realm,
                r.batch_id = $batch_id
            """,
            {"changes": data, "book_id": book_id, "batch_id": batch_id},
        )

        # V3: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": lc["character"],
                "category": "level",
                "name": "level",
                "action": "gain",
                "value_delta": (lc["new_level"] - lc["old_level"])
                if lc["old_level"] and lc["new_level"]
                else None,
                "value_after": lc["new_level"],
                "detail": lc.get("realm", ""),
            }
            for lc in data
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

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
            MATCH (ch:Character {canonical_name: sc.character, book_id: $book_id})
            MERGE (stat:Concept {name: sc.stat_name, book_id: $book_id})
            ON CREATE SET
                stat.canonical_name = toLower(sc.stat_name),
                stat.domain = 'stat',
                stat.description = sc.stat_name + ' stat',
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

        # V3: Create immutable StateChange ledger nodes
        state_change_data = [
            {
                "character_name": sc["character"],
                "category": "stat",
                "name": sc["stat_name"],
                "action": "gain" if sc["value"] > 0 else "lose",
                "value_delta": sc["value"],
            }
            for sc in data
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

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
                    "mention_type": g.attributes.get("mention_type", "langextract")
                    if g.attributes
                    else "langextract",
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
                MATCH (entity:{label} {{{prop_name}: e.entity_name, book_id: $book_id}})
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
                "mention_type": g.attributes.get("mention_type", "langextract")
                if g.attributes
                else "langextract",
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

    # ── Blue Boxes ───────────────────────────────────────────────────────

    async def upsert_blue_boxes(
        self,
        book_id: str,
        chapter_number: int,
        boxes: list,  # list[BlueBoxGroup] from bluebox.py
        batch_id: str = "",
    ) -> int:
        """Persist BlueBox grouping nodes to Neo4j."""
        if not boxes:
            return 0

        data = [
            {
                "index": idx,
                "raw_text": box.raw_text,
                "box_type": box.box_type,
                "paragraph_start": box.paragraph_start,
                "paragraph_end": box.paragraph_end,
            }
            for idx, box in enumerate(boxes)
        ]

        await self.execute_write(
            """
            UNWIND $boxes AS bb
            MERGE (b:BlueBox {book_id: $book_id, chapter: $chapter, index: bb.index})
            ON CREATE SET
                b.raw_text = bb.raw_text,
                b.box_type = bb.box_type,
                b.paragraph_start = bb.paragraph_start,
                b.paragraph_end = bb.paragraph_end,
                b.batch_id = $batch_id,
                b.created_at = timestamp()
            ON MATCH SET
                b.raw_text = bb.raw_text,
                b.box_type = bb.box_type,
                b.batch_id = $batch_id
            """,
            {
                "boxes": data,
                "book_id": book_id,
                "chapter": chapter_number,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "blue_boxes_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(boxes),
        )
        return len(boxes)

    # ── V3: StatBlocks ────────────────────────────────────────────────────

    async def upsert_stat_blocks(
        self,
        book_id: str,
        chapter_number: int,
        stat_blocks: list,  # list[ExtractedStatBlock]
        batch_id: str = "",
    ) -> int:
        """Upsert StatBlock nodes — snapshots of character stats at a chapter.

        MERGE on (character_name, chapter) to allow one snapshot per chapter.
        """
        if not stat_blocks:
            return 0

        data = [
            {
                "character_name": sb.character_name,
                "stats": sb.stats,
                "total": sb.total,
                "source": sb.source,
                "chapter": sb.chapter_number,
            }
            for sb in stat_blocks
        ]

        await self.execute_write(
            """
            UNWIND $blocks AS sb
            MERGE (s:StatBlock {character_name: sb.character_name, chapter: sb.chapter})
            ON CREATE SET
                s.stats = apoc.convert.toJson(sb.stats),
                s.total = sb.total,
                s.source = sb.source,
                s.book_id = $book_id,
                s.batch_id = $batch_id,
                s.created_at = timestamp()
            ON MATCH SET
                s.stats = apoc.convert.toJson(sb.stats),
                s.total = sb.total,
                s.source = sb.source,
                s.batch_id = $batch_id
            WITH s, sb
            MATCH (ch:Character {canonical_name: sb.character_name, book_id: $book_id})
            MERGE (ch)-[:HAS_STAT_BLOCK]->(s)
            """,
            {
                "blocks": data,
                "book_id": book_id,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "stat_blocks_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(stat_blocks),
        )
        return len(stat_blocks)

    # ── V3: QuestObjectives ──────────────────────────────────────────────

    async def upsert_quest_objectives(
        self,
        book_id: str,
        chapter_number: int,
        quests: list[dict[str, Any]],
        batch_id: str = "",
    ) -> int:
        """Upsert QuestObjective nodes.

        MERGE on name to allow quest progress updates across chapters.
        Each quest dict should have: name, description, status, giver, chapter.
        """
        if not quests:
            return 0

        await self.execute_write(
            """
            UNWIND $quests AS q
            MERGE (qo:QuestObjective {name: q.name, book_id: $book_id})
            ON CREATE SET
                qo.description = q.description,
                qo.status = q.status,
                qo.giver = q.giver,
                qo.chapter_started = q.chapter,
                qo.batch_id = $batch_id,
                qo.created_at = timestamp()
            ON MATCH SET
                qo.status = q.status,
                qo.batch_id = $batch_id
            WITH qo, q
            WHERE q.giver IS NOT NULL AND q.giver <> ''
            MATCH (ch:Character {canonical_name: q.giver, book_id: $book_id})
            MERGE (ch)-[:GIVES_QUEST]->(qo)
            """,
            {
                "quests": quests,
                "book_id": book_id,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "quest_objectives_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(quests),
        )
        return len(quests)

    # ── V3: Achievements ─────────────────────────────────────────────────

    async def upsert_achievements(
        self,
        book_id: str,
        chapter_number: int,
        achievements: list[dict[str, Any]],
        batch_id: str = "",
    ) -> int:
        """Upsert Achievement nodes and link to earner characters.

        MERGE on name to avoid duplicates.
        Each achievement dict should have: name, description, rarity, earner, chapter.
        """
        if not achievements:
            return 0

        await self.execute_write(
            """
            UNWIND $achievements AS a
            MERGE (ach:Achievement {name: a.name, book_id: $book_id})
            ON CREATE SET
                ach.description = a.description,
                ach.rarity = a.rarity,
                ach.batch_id = $batch_id,
                ach.created_at = timestamp()
            ON MATCH SET
                ach.description = CASE
                    WHEN size(a.description) > size(coalesce(ach.description, ''))
                    THEN a.description ELSE ach.description END,
                ach.batch_id = $batch_id
            WITH ach, a
            WHERE a.earner IS NOT NULL AND a.earner <> ''
            MATCH (ch:Character {canonical_name: a.earner, book_id: $book_id})
            MERGE (ch)-[r:EARNED]->(ach)
            ON CREATE SET r.chapter = a.chapter
            """,
            {
                "achievements": achievements,
                "book_id": book_id,
                "batch_id": batch_id,
            },
        )

        # V3: StateChange ledger for achievements
        state_change_data = [
            {
                "character_name": a["earner"],
                "category": "achievement",
                "name": a["name"],
                "action": "earn",
            }
            for a in achievements
            if a.get("earner")
        ]
        if state_change_data:
            await self._create_state_changes(
                book_id,
                chapter_number,
                state_change_data,
                batch_id,
            )

        logger.info(
            "achievements_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(achievements),
        )
        return len(achievements)

    # ── GRANTS relations ─────────────────────────────────────────────────

    async def upsert_grants_relations(
        self,
        provenances: list,  # list[SkillProvenance]
        batch_id: str = "",
        book_id: str = "",
    ) -> int:
        """Create GRANTS_SKILL relationships from provenance data.

        Only creates relations for high-confidence (>= 0.7) provenances
        with known source types (item, class, bloodline).
        """
        valid = [
            p
            for p in provenances
            if p.confidence >= 0.7
            and p.source_type in ("item", "class", "bloodline")
            and p.source_name
        ]
        if not valid:
            return 0

        label_map = {"item": "Item", "class": "Class", "bloodline": "Bloodline"}

        created = 0
        for source_type, label in label_map.items():
            type_provenances = [p for p in valid if p.source_type == source_type]
            if not type_provenances:
                continue

            data = [
                {"source_name": p.source_name, "skill_name": p.skill_name} for p in type_provenances
            ]

            await self.execute_write(
                f"""
                UNWIND $data AS d
                MATCH (src:{label} {{name: d.source_name, book_id: $book_id}})
                MATCH (sk:Skill {{name: d.skill_name, book_id: $book_id}})
                MERGE (src)-[r:GRANTS_SKILL]->(sk)
                ON CREATE SET r.batch_id = $batch_id, r.created_at = timestamp()
                """,
                {"data": data, "batch_id": batch_id, "book_id": book_id},
            )
            created += len(type_provenances)

        logger.info("grants_relations_upserted", count=created)
        return created

    # ── Layer 3: Bloodlines ──────────────────────────────────────────────

    async def upsert_bloodlines(
        self,
        book_id: str,
        chapter_number: int,
        bloodlines: list,  # list[ExtractedBloodline]
        batch_id: str = "",
    ) -> int:
        """Upsert Bloodline nodes and link to owner characters."""
        if not bloodlines:
            return 0

        data = [
            {
                "name": b.name,
                "canonical_name": b.name.lower().strip(),
                "description": b.description,
                "effects": b.effects,
                "origin": b.origin,
                "owner": b.owner,
                "awakened_chapter": b.awakened_chapter or chapter_number,
            }
            for b in bloodlines
        ]

        await self.execute_write(
            """
            UNWIND $bloodlines AS b
            MERGE (bl:Bloodline {canonical_name: b.canonical_name, book_id: $book_id})
            ON CREATE SET
                bl.name = b.name,
                bl.description = b.description,
                bl.effects = b.effects,
                bl.origin = b.origin,
                bl.batch_id = $batch_id,
                bl.created_at = timestamp()
            ON MATCH SET
                bl.description = CASE
                    WHEN size(b.description) > size(coalesce(bl.description, ''))
                    THEN b.description ELSE bl.description END,
                bl.batch_id = $batch_id
            WITH bl, b
            WHERE b.owner <> ''
            MATCH (ch:Character {canonical_name: b.owner, book_id: $book_id})
            MERGE (ch)-[r:HAS_BLOODLINE]->(bl)
            ON CREATE SET r.awakened_chapter = b.awakened_chapter
            """,
            {"bloodlines": data, "book_id": book_id, "batch_id": batch_id},
        )

        # V3: StateChange for bloodline awakening
        state_change_data = [
            {
                "character_name": b["owner"],
                "category": "bloodline",
                "name": b["name"],
                "action": "awaken",
            }
            for b in data
            if b["owner"]
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

        logger.info(
            "bloodlines_upserted", book_id=book_id, chapter=chapter_number, count=len(bloodlines)
        )
        return len(bloodlines)

    # ── Layer 3: Professions ─────────────────────────────────────────────

    async def upsert_professions(
        self,
        book_id: str,
        chapter_number: int,
        professions: list,  # list[ExtractedProfession]
        batch_id: str = "",
    ) -> int:
        """Upsert Profession nodes and link to owner characters."""
        if not professions:
            return 0

        data = [
            {
                "name": p.name,
                "canonical_name": p.name.lower().strip(),
                "tier": p.tier,
                "profession_type": p.profession_type,
                "owner": p.owner,
                "chapter": p.acquired_chapter or chapter_number,
            }
            for p in professions
        ]

        await self.execute_write(
            """
            UNWIND $professions AS p
            MERGE (pr:Profession {canonical_name: p.canonical_name, book_id: $book_id})
            ON CREATE SET
                pr.name = p.name,
                pr.tier = p.tier,
                pr.profession_type = p.profession_type,
                pr.batch_id = $batch_id,
                pr.created_at = timestamp()
            WITH pr, p
            WHERE p.owner <> ''
            MATCH (ch:Character {canonical_name: p.owner, book_id: $book_id})
            MERGE (ch)-[r:HAS_PROFESSION]->(pr)
            ON CREATE SET r.valid_from_chapter = p.chapter
            """,
            {"professions": data, "book_id": book_id, "batch_id": batch_id},
        )

        state_change_data = [
            {
                "character_name": p["owner"],
                "category": "profession",
                "name": p["name"],
                "action": "acquire",
            }
            for p in data
            if p["owner"]
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

        logger.info(
            "professions_upserted", book_id=book_id, chapter=chapter_number, count=len(professions)
        )
        return len(professions)

    # ── Layer 3: Primordial Churches ─────────────────────────────────────

    async def upsert_churches(
        self,
        book_id: str,
        chapter_number: int,
        churches: list,  # list[ExtractedChurch]
        batch_id: str = "",
    ) -> int:
        """Upsert PrimordialChurch nodes and link worshippers."""
        if not churches:
            return 0

        data = [
            {
                "deity_name": c.deity_name,
                "canonical_name": c.deity_name.lower().strip(),
                "domain": c.domain,
                "blessing": c.blessing,
                "worshipper": c.worshipper,
                "chapter": c.valid_from_chapter or chapter_number,
            }
            for c in churches
        ]

        await self.execute_write(
            """
            UNWIND $churches AS c
            MERGE (pc:PrimordialChurch {canonical_name: c.canonical_name, book_id: $book_id})
            ON CREATE SET
                pc.deity_name = c.deity_name,
                pc.name = c.deity_name,
                pc.domain = c.domain,
                pc.batch_id = $batch_id,
                pc.created_at = timestamp()
            WITH pc, c
            WHERE c.worshipper <> ''
            MATCH (ch:Character {canonical_name: c.worshipper, book_id: $book_id})
            MERGE (ch)-[r:WORSHIPS]->(pc)
            ON CREATE SET r.blessing = c.blessing, r.valid_from_chapter = c.chapter
            """,
            {"churches": data, "book_id": book_id, "batch_id": batch_id},
        )

        # V3 dual-write: StateChange ledger
        state_change_data = [
            {
                "character_name": c.worshipper,
                "category": "church",
                "name": c.deity_name,
                "action": "worship",
                "detail": c.blessing or "",
            }
            for c in churches
            if c.worshipper
        ]
        if state_change_data:
            await self._create_state_changes(book_id, chapter_number, state_change_data, batch_id)

        logger.info(
            "churches_upserted", book_id=book_id, chapter=chapter_number, count=len(churches)
        )
        return len(churches)

    # ── Arcs ─────────────────────────────────────────────────────────────

    async def upsert_arcs(
        self,
        book_id: str,
        chapter_number: int,
        arcs: list,
        batch_id: str = "",
    ) -> int:
        """Upsert Arc nodes and create MENTIONED_IN edge to the chapter."""
        if not arcs:
            return 0

        data = [
            {
                "name": a.name,
                "canonical_name": (
                    getattr(a, "canonical_name", None) or a.name
                ).lower().strip(),
                "description": getattr(a, "description", ""),
                "arc_type": getattr(a, "arc_type", ""),
                "related_events": [
                    e.lower().strip() for e in getattr(a, "related_events", []) or []
                ],
            }
            for a in arcs
        ]

        await self.execute_write(
            """
            UNWIND $arcs AS a
            MERGE (n:Arc {canonical_name: a.canonical_name, book_id: $book_id})
            ON CREATE SET
                n.name = a.name,
                n.description = a.description,
                n.arc_type = a.arc_type,
                n.batch_id = $batch_id,
                n.valid_from_chapter = $chapter,
                n.created_at = timestamp()
            ON MATCH SET
                n.description = CASE
                    WHEN size(a.description) > size(coalesce(n.description, ''))
                    THEN a.description ELSE n.description END,
                n.batch_id = $batch_id
            WITH n
            MATCH (ch:Chapter {book_id: $book_id, number: $chapter})
            MERGE (n)-[:MENTIONED_IN]->(ch)
            """,
            {
                "arcs": data,
                "book_id": book_id,
                "batch_id": batch_id,
                "chapter": chapter_number,
            },
        )

        # Link arcs to their related events via PART_OF_ARC edges
        for arc_data in data:
            if arc_data["related_events"]:
                await self.execute_write(
                    """
                    UNWIND $event_names AS event_name
                    MATCH (e:Event {book_id: $book_id})
                    WHERE toLower(e.name) = event_name
                       OR e.canonical_name = event_name
                    WITH e, event_name
                    LIMIT 1
                    MATCH (arc:Arc {canonical_name: $arc_name, book_id: $book_id})
                    MERGE (e)-[:PART_OF_ARC]->(arc)
                    """,
                    {
                        "event_names": arc_data["related_events"],
                        "arc_name": arc_data["canonical_name"],
                        "book_id": book_id,
                    },
                )

        # Add PRECEDES edges between consecutive events within each arc (by chapter order)
        for arc_data in data:
            if len(arc_data["related_events"]) >= 2:
                await self.execute_write(
                    """
                    MATCH (arc:Arc {canonical_name: $arc_name, book_id: $book_id})
                    MATCH (e:Event)-[:PART_OF_ARC]->(arc)
                    WITH e ORDER BY e.valid_from_chapter ASC, e.name ASC
                    WITH collect(e) AS events
                    UNWIND range(0, size(events) - 2) AS i
                    WITH events[i] AS prev, events[i + 1] AS next
                    MERGE (prev)-[:PRECEDES {arc_derived: true}]->(next)
                    """,
                    {
                        "arc_name": arc_data["canonical_name"],
                        "book_id": book_id,
                    },
                )

        logger.info(
            "arcs_upserted", book_id=book_id, chapter=chapter_number, count=len(arcs)
        )
        return len(arcs)

    # ── Prophecies ───────────────────────────────────────────────────────

    async def upsert_prophecies(
        self,
        book_id: str,
        chapter_number: int,
        prophecies: list,
        batch_id: str = "",
    ) -> int:
        """Upsert Prophecy nodes and create MENTIONED_IN edge to the chapter."""
        if not prophecies:
            return 0

        data = [
            {
                "name": p.name,
                "canonical_name": (
                    getattr(p, "canonical_name", None) or p.name
                ).lower().strip(),
                "description": getattr(p, "description", ""),
                "status": getattr(p, "status", ""),
            }
            for p in prophecies
        ]

        await self.execute_write(
            """
            UNWIND $prophecies AS p
            MERGE (n:Prophecy {canonical_name: p.canonical_name, book_id: $book_id})
            ON CREATE SET
                n.name = p.name,
                n.description = p.description,
                n.status = p.status,
                n.batch_id = $batch_id,
                n.valid_from_chapter = $chapter,
                n.created_at = timestamp()
            ON MATCH SET
                n.description = CASE
                    WHEN size(p.description) > size(coalesce(n.description, ''))
                    THEN p.description ELSE n.description END,
                n.batch_id = $batch_id
            WITH n
            MATCH (ch:Chapter {book_id: $book_id, number: $chapter})
            MERGE (n)-[:MENTIONED_IN]->(ch)
            """,
            {
                "prophecies": data,
                "book_id": book_id,
                "batch_id": batch_id,
                "chapter": chapter_number,
            },
        )

        logger.info(
            "prophecies_upserted",
            book_id=book_id,
            chapter=chapter_number,
            count=len(prophecies),
        )
        return len(prophecies)

    # ── Generic genre entity upsert (fallback for unmapped sub_types) ───

    async def upsert_genre_entities(
        self,
        book_id: str,
        chapter_number: int,
        entity_type: str,
        entities: list,
        batch_id: str = "",
    ) -> int:
        """Upsert genre entities with proper Neo4j labels based on sub_type.

        Uses _GENRE_SUBTYPE_LABEL_MAP to resolve the Neo4j label.
        Falls back to 'GenreEntity' if the sub_type is unknown.
        Since labels come from a controlled mapping (not user input),
        f-string interpolation is safe — same pattern as apply_relation_end.
        """
        if not entities:
            return 0

        label = _GENRE_SUBTYPE_LABEL_MAP.get(entity_type, "GenreEntity")

        data = [
            {
                "name": (
                    getattr(e, "name", e.get("name", "")) if isinstance(e, dict) else e.name
                ).lower().strip(),
                "canonical_name": (
                    getattr(e, "name", e.get("name", "")) if isinstance(e, dict) else e.name
                ).lower().strip(),
                "description": (
                    getattr(e, "description", e.get("description", ""))
                    if isinstance(e, dict)
                    else getattr(e, "description", "")
                ),
                "sub_type": entity_type,
            }
            for e in entities
        ]

        await self.execute_write(
            f"""
            UNWIND $entities AS e
            MERGE (n:{label} {{canonical_name: e.canonical_name, book_id: $book_id}})
            ON CREATE SET
                n.name = e.name,
                n.description = e.description,
                n.sub_type = e.sub_type,
                n.batch_id = $batch_id,
                n.valid_from_chapter = $chapter,
                n.created_at = timestamp()
            ON MATCH SET
                n.description = CASE
                    WHEN size(e.description) > size(coalesce(n.description, ''))
                    THEN e.description ELSE n.description END,
                n.batch_id = $batch_id
            WITH n, e
            MATCH (chap:Chapter {{book_id: $book_id, number: $chapter}})
            MERGE (n)-[:MENTIONED_IN]->(chap)
            """,
            {
                "entities": data,
                "book_id": book_id,
                "batch_id": batch_id,
                "chapter": chapter_number,
            },
        )

        logger.info(
            "genre_entities_upserted",
            book_id=book_id,
            chapter=chapter_number,
            entity_type=entity_type,
            label=label,
            count=len(entities),
        )
        return len(entities)

    # ── StateChange ledger (V3 dual-write) ──────────────────────────────

    async def _create_state_changes(
        self,
        book_id: str,
        chapter: int,
        changes: list[dict[str, Any]],
        batch_id: str,
    ) -> int:
        """Create immutable StateChange ledger nodes.

        Each change dict must have: character_name, category, name, action.
        Optional: value_delta, value_after, detail.
        """
        if not changes:
            return 0

        for sc in changes:
            sc.setdefault("value_delta", None)
            sc.setdefault("value_after", None)
            sc.setdefault("detail", "")

        await self.execute_write(
            """
            UNWIND $changes AS sc
            MATCH (ch:Character {canonical_name: sc.character_name, book_id: $book_id})
            MERGE (s:StateChange {
                character_name: sc.character_name,
                book_id: $book_id,
                chapter: $chapter,
                category: sc.category,
                name: sc.name,
                action: sc.action
            })
            ON CREATE SET
                s.value_delta = sc.value_delta,
                s.value_after = sc.value_after,
                s.detail = sc.detail,
                s.batch_id = $batch_id,
                s.created_at = timestamp()
            ON MATCH SET
                s.value_delta = sc.value_delta,
                s.value_after = sc.value_after,
                s.detail = sc.detail,
                s.batch_id = $batch_id
            MERGE (ch)-[:STATE_CHANGED]->(s)
            """,
            {
                "changes": changes,
                "book_id": book_id,
                "chapter": chapter,
                "batch_id": batch_id,
            },
        )

        logger.info(
            "state_changes_created",
            book_id=book_id,
            chapter=chapter,
            count=len(changes),
        )
        return len(changes)

    # ── V4: Relation end ────────────────────────────────────────────────

    async def apply_relation_end(
        self,
        source: str,
        target: str,
        relation_type: str,
        ended_at_chapter: int,
        reason: str = "",
        book_id: str = "",
    ) -> None:
        """Set valid_to_chapter on an active relation.

        Uses dynamic relationship type (controlled Literal enum — safe).
        Neo4j doesn't support parameterized relationship types in MATCH.
        Since relation_type comes from a controlled Literal enum (16 values),
        the f-string interpolation is safe — not user input.
        """
        book_filter_a = "AND a.book_id = $book_id" if book_id else ""
        book_filter_b = "AND b.book_id = $book_id" if book_id else ""
        rel_book_filter = "AND r.book_id = $book_id" if book_id else ""
        query = f"""
            MATCH (a)-[r:{relation_type}]->(b)
            WHERE (a.canonical_name = $source OR a.name = $source)
            AND NOT a:Book AND NOT a:Chapter
            {book_filter_a}
            AND (b.canonical_name = $target OR b.name = $target)
            AND NOT b:Book AND NOT b:Chapter
            {book_filter_b}
            AND r.valid_to_chapter IS NULL
            {rel_book_filter}
            SET r.valid_to_chapter = $ended_at_chapter,
                r.end_reason = $reason
        """
        await self.execute_write(
            query,
            {
                "source": source,
                "target": target,
                "ended_at_chapter": ended_at_chapter,
                "reason": reason,
                "book_id": book_id,
            },
        )
        logger.info(
            "relation_end_applied",
            source=source,
            target=target,
            relation_type=relation_type,
            ended_at_chapter=ended_at_chapter,
        )

    # ── V4: Flat entity dispatch ─────────────────────────────────────────

    async def upsert_v4_entities(
        self,
        entities: list[dict],
        relations: list[dict],
        ended_relations: list[dict],
        book_id: str,
        chapter_number: int,
        batch_id: str,
    ) -> dict[str, int]:
        """Dispatch v4 flat entities to existing upsert methods by entity_type.

        Converts v4 flat dicts to the simple-namespace objects (SimpleNamespace)
        expected by the existing upsert_* methods (which access fields as attributes).
        """
        from types import SimpleNamespace

        counts: dict[str, int] = {}

        # ── Normalize names to lowercase to prevent case-sensitive MERGE duplicates ──
        for e in entities:
            if "canonical_name" in e and isinstance(e["canonical_name"], str):
                e["canonical_name"] = e["canonical_name"].lower().strip()
            if "name" in e and isinstance(e["name"], str):
                e["name"] = e["name"].lower().strip()
        for r in relations:
            if "source" in r and isinstance(r["source"], str):
                r["source"] = r["source"].lower().strip()
            if "target" in r and isinstance(r["target"], str):
                r["target"] = r["target"].lower().strip()
        for er in ended_relations:
            if "source" in er and isinstance(er["source"], str):
                er["source"] = er["source"].lower().strip()
            if "target" in er and isinstance(er["target"], str):
                er["target"] = er["target"].lower().strip()

        # Remap genre_entity → sub_type for dispatch (V4 GenreEntity catch-all)
        # e.g. {entity_type: "genre_entity", sub_type: "skill"} → dispatch as "skill"
        # Shallow copy to avoid mutating caller's data (EntityRegistry stores genre_entity)
        entities = [dict(e) for e in entities]
        for e in entities:
            if e.get("entity_type") == "genre_entity":
                e["entity_type"] = e.get("sub_type", "concept")

        # Group entities by entity_type
        by_type: dict[str, list[dict]] = {}
        for e in entities:
            et = e.get("entity_type", "")
            if et not in by_type:
                by_type[et] = []
            by_type[et].append(e)

        def _ns(d: dict) -> SimpleNamespace:
            """Convert a dict to a SimpleNamespace for attribute access."""
            return SimpleNamespace(**d)

        # ── Phase 1: Prepare all entity SimpleNamespace objects ─────────

        # Characters
        chars = []
        if "character" in by_type:
            chars = [_ns(e) for e in by_type["character"]]
            for c in chars:
                if not hasattr(c, "aliases"):
                    c.aliases = []
                if not hasattr(c, "canonical_name") or not c.canonical_name:
                    c.canonical_name = c.name
                if not hasattr(c, "description"):
                    c.description = ""
                if not hasattr(c, "role"):
                    c.role = ""
                if not hasattr(c, "species"):
                    c.species = ""
                if not hasattr(c, "first_appearance_chapter"):
                    c.first_appearance_chapter = chapter_number

        # Skills
        skills = []
        if "skill" in by_type:
            skills = [_ns(e) for e in by_type["skill"]]
            for s in skills:
                if not hasattr(s, "description"):
                    s.description = ""
                if not hasattr(s, "skill_type"):
                    s.skill_type = "active"
                if not hasattr(s, "rank"):
                    s.rank = ""
                if not hasattr(s, "owner"):
                    s.owner = ""
                if not hasattr(s, "acquired_chapter"):
                    s.acquired_chapter = chapter_number

        # Classes
        classes = []
        if "class" in by_type:
            classes = [_ns(e) for e in by_type["class"]]
            for c in classes:
                if not hasattr(c, "description"):
                    c.description = ""
                if not hasattr(c, "tier"):
                    c.tier = None
                if not hasattr(c, "owner"):
                    c.owner = ""
                if not hasattr(c, "acquired_chapter"):
                    c.acquired_chapter = chapter_number

        # Titles
        titles = []
        if "title" in by_type:
            titles = [_ns(e) for e in by_type["title"]]
            for t in titles:
                if not hasattr(t, "description"):
                    t.description = ""
                if not hasattr(t, "effects"):
                    t.effects = []
                if not hasattr(t, "owner"):
                    t.owner = ""
                if not hasattr(t, "acquired_chapter"):
                    t.acquired_chapter = chapter_number

        # Events
        events = []
        if "event" in by_type:
            events = [_ns(e) for e in by_type["event"]]
            for ev in events:
                if not hasattr(ev, "description"):
                    ev.description = ""
                if not hasattr(ev, "event_type"):
                    ev.event_type = "action"
                if not hasattr(ev, "significance"):
                    ev.significance = "moderate"
                if not hasattr(ev, "participants"):
                    ev.participants = []
                if not hasattr(ev, "location"):
                    ev.location = ""
                if not hasattr(ev, "chapter"):
                    ev.chapter = chapter_number
                if not hasattr(ev, "is_flashback"):
                    ev.is_flashback = False

        # Locations
        locations = []
        if "location" in by_type:
            locations = [_ns(e) for e in by_type["location"]]
            for loc in locations:
                if not hasattr(loc, "description"):
                    loc.description = ""
                if not hasattr(loc, "location_type"):
                    loc.location_type = ""
                if not hasattr(loc, "parent_location"):
                    loc.parent_location = ""

        # Items
        items = []
        if "item" in by_type:
            items = [_ns(e) for e in by_type["item"]]
            for it in items:
                if not hasattr(it, "description"):
                    it.description = ""
                if not hasattr(it, "item_type"):
                    it.item_type = ""
                if not hasattr(it, "rarity"):
                    it.rarity = ""
                if not hasattr(it, "owner"):
                    it.owner = ""

        # Creatures
        creatures = []
        if "creature" in by_type:
            creatures = [_ns(e) for e in by_type["creature"]]
            for cr in creatures:
                if not hasattr(cr, "description"):
                    cr.description = ""
                if not hasattr(cr, "species"):
                    cr.species = ""
                if not hasattr(cr, "threat_level"):
                    cr.threat_level = ""
                if not hasattr(cr, "habitat"):
                    cr.habitat = ""

        # Factions
        factions = []
        if "faction" in by_type:
            factions = [_ns(e) for e in by_type["faction"]]
            for fa in factions:
                if not hasattr(fa, "description"):
                    fa.description = ""
                if not hasattr(fa, "faction_type"):
                    fa.faction_type = ""
                if not hasattr(fa, "alignment"):
                    fa.alignment = ""

        # Concepts
        concepts = []
        if "concept" in by_type:
            concepts = [_ns(e) for e in by_type["concept"]]
            for co in concepts:
                if not hasattr(co, "description"):
                    co.description = ""
                if not hasattr(co, "domain"):
                    co.domain = ""

        # LevelChanges
        level_changes = []
        if "level_change" in by_type:
            level_changes = [_ns(e) for e in by_type["level_change"]]
            for lc in level_changes:
                if not hasattr(lc, "old_level"):
                    lc.old_level = None
                if not hasattr(lc, "new_level"):
                    lc.new_level = None
                if not hasattr(lc, "realm"):
                    lc.realm = ""
                if not hasattr(lc, "chapter"):
                    lc.chapter = chapter_number

        # StatChanges
        stat_changes = []
        if "stat_change" in by_type:
            stat_changes = [_ns(e) for e in by_type["stat_change"]]
            for sc in stat_changes:
                if not hasattr(sc, "value"):
                    sc.value = 0

        # Bloodlines (Layer 3)
        bloodlines = []
        if "bloodline" in by_type:
            bloodlines = [_ns(e) for e in by_type["bloodline"]]
            for bl in bloodlines:
                if not hasattr(bl, "description"):
                    bl.description = ""
                if not hasattr(bl, "effects"):
                    bl.effects = []
                if not hasattr(bl, "origin"):
                    bl.origin = ""
                if not hasattr(bl, "owner"):
                    bl.owner = ""
                if not hasattr(bl, "awakened_chapter"):
                    bl.awakened_chapter = chapter_number

        # Professions (Layer 3)
        professions = []
        if "profession" in by_type:
            professions = [_ns(e) for e in by_type["profession"]]
            for pr in professions:
                if not hasattr(pr, "tier"):
                    pr.tier = None
                if not hasattr(pr, "profession_type"):
                    pr.profession_type = ""
                if not hasattr(pr, "owner"):
                    pr.owner = ""
                if not hasattr(pr, "acquired_chapter"):
                    pr.acquired_chapter = chapter_number

        # Churches (Layer 3)
        churches = []
        if "church" in by_type:
            churches = [_ns(e) for e in by_type["church"]]
            for ch in churches:
                # V4 GenreEntity uses "name"; upsert_churches expects "deity_name"
                if not hasattr(ch, "deity_name"):
                    ch.deity_name = getattr(ch, "name", "")
                if not hasattr(ch, "domain"):
                    ch.domain = ""
                if not hasattr(ch, "blessing"):
                    ch.blessing = ""
                if not hasattr(ch, "worshipper"):
                    ch.worshipper = ""
                if not hasattr(ch, "valid_from_chapter"):
                    ch.valid_from_chapter = chapter_number

        # Arcs
        arcs = []
        if "arc" in by_type:
            arcs = [_ns(e) for e in by_type["arc"]]
            for a in arcs:
                if not hasattr(a, "description"):
                    a.description = ""
                if not hasattr(a, "arc_type"):
                    a.arc_type = ""
                if not hasattr(a, "canonical_name") or not a.canonical_name:
                    a.canonical_name = a.name
                if not hasattr(a, "related_events"):
                    a.related_events = []

        # Prophecies
        prophecies = []
        if "prophecy" in by_type:
            prophecies = [_ns(e) for e in by_type["prophecy"]]
            for p in prophecies:
                if not hasattr(p, "description"):
                    p.description = ""
                if not hasattr(p, "status"):
                    p.status = ""
                if not hasattr(p, "canonical_name") or not p.canonical_name:
                    p.canonical_name = p.name

        # Relations
        rel_ns = []
        if relations:
            rel_ns = [_ns(r) for r in relations]
            for r in rel_ns:
                if not hasattr(r, "rel_type"):
                    r.rel_type = getattr(r, "relation_type", "RELATES_TO")
                if not hasattr(r, "subtype"):
                    r.subtype = ""
                if not hasattr(r, "context"):
                    r.context = ""
                if not hasattr(r, "since_chapter"):
                    r.since_chapter = getattr(r, "valid_from_chapter", None) or chapter_number
                if not hasattr(r, "temporal_order"):
                    r.temporal_order = None

        # ── Phase 2: Entity node upserts in parallel ─────────────────
        # All entity types are independent — safe to run concurrently.
        entity_coros: list[tuple[str, Any]] = []
        if chars:
            entity_coros.append(
                ("characters", self.upsert_characters(book_id, chapter_number, chars, batch_id))
            )
        if skills:
            entity_coros.append(
                ("skills", self.upsert_skills(book_id, chapter_number, skills, batch_id))
            )
        if classes:
            entity_coros.append(
                ("classes", self.upsert_classes(book_id, chapter_number, classes, batch_id))
            )
        if titles:
            entity_coros.append(
                ("titles", self.upsert_titles(book_id, chapter_number, titles, batch_id))
            )
        if events:
            entity_coros.append(
                ("events", self.upsert_events(book_id, chapter_number, events, batch_id))
            )
        if locations:
            entity_coros.append(
                ("locations", self.upsert_locations(book_id, chapter_number, locations, batch_id))
            )
        if items:
            entity_coros.append(
                ("items", self.upsert_items(book_id, chapter_number, items, batch_id))
            )
        if creatures:
            entity_coros.append(
                ("creatures", self.upsert_creatures(book_id, chapter_number, creatures, batch_id))
            )
        if factions:
            entity_coros.append(
                ("factions", self.upsert_factions(book_id, chapter_number, factions, batch_id))
            )
        if concepts:
            entity_coros.append(
                ("concepts", self.upsert_concepts(book_id, chapter_number, concepts, batch_id))
            )
        if level_changes:
            entity_coros.append(
                (
                    "level_changes",
                    self.upsert_level_changes(book_id, chapter_number, level_changes, batch_id),
                )
            )
        if stat_changes:
            entity_coros.append(
                (
                    "stat_changes",
                    self.upsert_stat_changes(book_id, chapter_number, stat_changes, batch_id),
                )
            )
        if bloodlines:
            entity_coros.append(
                (
                    "bloodlines",
                    self.upsert_bloodlines(book_id, chapter_number, bloodlines, batch_id),
                )
            )
        if professions:
            entity_coros.append(
                (
                    "professions",
                    self.upsert_professions(book_id, chapter_number, professions, batch_id),
                )
            )
        if churches:
            entity_coros.append(
                ("churches", self.upsert_churches(book_id, chapter_number, churches, batch_id))
            )
        if arcs:
            entity_coros.append(
                ("arcs", self.upsert_arcs(book_id, chapter_number, arcs, batch_id))
            )
        if prophecies:
            entity_coros.append(
                (
                    "prophecies",
                    self.upsert_prophecies(book_id, chapter_number, prophecies, batch_id),
                )
            )

        # ── Fallback: unmapped genre sub_types (floor, alchemy_recipe, etc.)
        for etype, etype_entities in by_type.items():
            if etype not in _HANDLED_ENTITY_TYPES:
                ns_list = [_ns(e) for e in etype_entities]
                entity_coros.append(
                    (
                        etype,
                        self.upsert_genre_entities(
                            book_id, chapter_number, etype, ns_list, batch_id
                        ),
                    )
                )

        if entity_coros:
            entity_keys = [key for key, _ in entity_coros]
            entity_results = await asyncio.gather(*(coro for _, coro in entity_coros))
            for key, result_count in zip(entity_keys, entity_results):
                counts[key] = result_count

        # ── Phase 3: Relations (depend on entity nodes existing) ─────
        if rel_ns:
            counts["relations"] = await self.upsert_relationships(
                book_id, chapter_number, rel_ns, batch_id
            )

        # ── Phase 4: Ended relations in parallel ─────────────────────
        if ended_relations:
            ended_coros = [
                self.apply_relation_end(
                    source=er.get("source", ""),
                    target=er.get("target", ""),
                    relation_type=er.get("relation_type", "RELATES_TO"),
                    ended_at_chapter=er.get("ended_at_chapter", chapter_number),
                    reason=er.get("reason", ""),
                    book_id=book_id,
                )
                for er in ended_relations
            ]
            await asyncio.gather(*ended_coros)
            counts["ended_relations"] = len(ended_relations)

        logger.info(
            "v4_entities_upserted",
            book_id=book_id,
            chapter=chapter_number,
            batch_id=batch_id,
            entity_types=list(by_type.keys()),
            counts=counts,
        )
        return counts

    # ── V4: Entity summaries ─────────────────────────────────────────────

    async def upsert_entity_summary(
        self,
        entity_name: str,
        summary: str,
        key_facts: list[str],
        mention_count: int,
        batch_id: str,
        book_id: str = "",
    ) -> None:
        """Store entity summary on the node. Uses MERGE pattern."""
        await self.execute_write(
            """
            MATCH (e {canonical_name: $name})
            WHERE e.book_id = $book_id OR $book_id = ''
            SET e.summary = $summary,
                e.key_facts = $key_facts,
                e.mention_count = $mention_count,
                e.summary_batch_id = $batch_id
            """,
            {
                "name": entity_name,
                "book_id": book_id,
                "summary": summary,
                "key_facts": key_facts,
                "mention_count": mention_count,
                "batch_id": batch_id,
            },
        )
        logger.info(
            "entity_summary_upserted",
            entity_name=entity_name,
            book_id=book_id,
            mention_count=mention_count,
        )

    # ── V4: Communities ──────────────────────────────────────────────────

    async def upsert_community(
        self,
        community_id: str,
        book_id: str,
        summary: str,
        member_names: list[str],
        batch_id: str,
        level: int = 0,
        resolution: float = 1.0,
        key_themes: list[str] | None = None,
    ) -> None:
        """Create/update community node + member edges. Uses MERGE."""
        await self.execute_write(
            """
            MERGE (comm:Community {id: $community_id})
            ON CREATE SET
                comm.book_id = $book_id,
                comm.summary = $summary,
                comm.member_count = size($member_names),
                comm.batch_id = $batch_id,
                comm.level = $level,
                comm.resolution = $resolution,
                comm.key_themes = $key_themes,
                comm.created_at = datetime()
            ON MATCH SET
                comm.summary = $summary,
                comm.member_count = size($member_names),
                comm.batch_id = $batch_id,
                comm.level = $level,
                comm.resolution = $resolution,
                comm.key_themes = $key_themes
            WITH comm
            UNWIND $member_names AS member_name
            MATCH (e {canonical_name: member_name, book_id: $book_id})
            MERGE (e)-[:BELONGS_TO_COMMUNITY]->(comm)
            """,
            {
                "community_id": community_id,
                "book_id": book_id,
                "summary": summary,
                "member_names": member_names,
                "batch_id": batch_id,
                "level": level,
                "resolution": resolution,
                "key_themes": key_themes or [],
            },
        )
        logger.info(
            "community_upserted",
            community_id=community_id,
            book_id=book_id,
            level=level,
            member_count=len(member_names),
        )

    async def link_parent_community(
        self,
        child_id: str,
        parent_id: str,
        book_id: str,
    ) -> None:
        """Create PARENT_COMMUNITY edge between child and parent community."""
        await self.execute_write(
            """
            MATCH (child:Community {id: $child_id, book_id: $book_id})
            MATCH (parent:Community {id: $parent_id, book_id: $book_id})
            MERGE (child)-[:PARENT_COMMUNITY]->(parent)
            """,
            {
                "child_id": child_id,
                "parent_id": parent_id,
                "book_id": book_id,
            },
        )

    async def delete_communities_for_book(self, book_id: str) -> None:
        """Remove all existing communities for a book before re-clustering."""
        await self.execute_write(
            """
            MATCH (comm:Community {book_id: $book_id})
            DETACH DELETE comm
            """,
            {"book_id": book_id},
        )

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
