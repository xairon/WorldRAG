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
        ontology_version: str = "",
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

        version_clause = ""
        if ontology_version:
            version_clause = ", ch.ontology_version = $ontology_version"

        await self.execute_write(
            f"""
            UNWIND $chars AS c
            MERGE (ch:Character {{canonical_name: c.canonical_name}})
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
                {version_clause}
            ON MATCH SET
                ch.description = CASE
                    WHEN size(c.description) > size(coalesce(ch.description, ''))
                    THEN c.description ELSE ch.description END,
                ch.aliases = ch.aliases + [a IN c.aliases WHERE NOT a IN ch.aliases],
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
        ontology_version: str = "",
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

        version_clause = ""
        if ontology_version:
            version_clause = ", sk.ontology_version = $ontology_version"

        await self.execute_write(
            f"""
            UNWIND $skills AS s
            MERGE (sk:Skill {{name: s.name}})
            ON CREATE SET
                sk.description = s.description,
                sk.skill_type = s.skill_type,
                sk.rank = s.rank,
                sk.book_id = $book_id,
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
            MATCH (ch:Character {{canonical_name: s.owner}})
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

        version_clause = ""
        if ontology_version:
            version_clause = ", ev.ontology_version = $ontology_version"

        # Create events and link to chapter
        await self.execute_write(
            f"""
            UNWIND $events AS e
            MERGE (ev:Event {{name: e.name, chapter_start: e.chapter}})
            ON CREATE SET
                ev.description = e.description,
                ev.event_type = e.event_type,
                ev.significance = e.significance,
                ev.is_flashback = e.is_flashback,
                ev.book_id = $book_id,
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
            MATCH (ch:Character {canonical_name: sb.character_name})
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
            MERGE (qo:QuestObjective {name: q.name})
            ON CREATE SET
                qo.description = q.description,
                qo.status = q.status,
                qo.giver = q.giver,
                qo.chapter_started = q.chapter,
                qo.book_id = $book_id,
                qo.batch_id = $batch_id,
                qo.created_at = timestamp()
            ON MATCH SET
                qo.status = q.status,
                qo.batch_id = $batch_id
            WITH qo, q
            WHERE q.giver IS NOT NULL AND q.giver <> ''
            MATCH (ch:Character {canonical_name: q.giver})
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
            MERGE (ach:Achievement {name: a.name})
            ON CREATE SET
                ach.description = a.description,
                ach.rarity = a.rarity,
                ach.book_id = $book_id,
                ach.batch_id = $batch_id,
                ach.created_at = timestamp()
            ON MATCH SET
                ach.description = CASE
                    WHEN size(a.description) > size(coalesce(ach.description, ''))
                    THEN a.description ELSE ach.description END,
                ach.batch_id = $batch_id
            WITH ach, a
            WHERE a.earner IS NOT NULL AND a.earner <> ''
            MATCH (ch:Character {canonical_name: a.earner})
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
                MATCH (src:{label} {{name: d.source_name}})
                MATCH (sk:Skill {{name: d.skill_name}})
                MERGE (src)-[r:GRANTS_SKILL]->(sk)
                ON CREATE SET r.batch_id = $batch_id, r.created_at = timestamp()
                """,
                {"data": data, "batch_id": batch_id},
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
            MERGE (bl:Bloodline {name: b.name})
            ON CREATE SET
                bl.description = b.description,
                bl.effects = b.effects,
                bl.origin = b.origin,
                bl.book_id = $book_id,
                bl.batch_id = $batch_id,
                bl.created_at = timestamp()
            ON MATCH SET
                bl.description = CASE
                    WHEN size(b.description) > size(coalesce(bl.description, ''))
                    THEN b.description ELSE bl.description END,
                bl.batch_id = $batch_id
            WITH bl, b
            WHERE b.owner <> ''
            MATCH (ch:Character {canonical_name: b.owner})
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
            MERGE (pr:Profession {name: p.name, book_id: $book_id})
            ON CREATE SET
                pr.tier = p.tier,
                pr.profession_type = p.profession_type,
                pr.batch_id = $batch_id,
                pr.created_at = timestamp()
            WITH pr, p
            WHERE p.owner <> ''
            MATCH (ch:Character {canonical_name: p.owner})
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
            MERGE (pc:PrimordialChurch {deity_name: c.deity_name})
            ON CREATE SET
                pc.domain = c.domain,
                pc.batch_id = $batch_id,
                pc.created_at = timestamp()
            WITH pc, c
            WHERE c.worshipper <> ''
            MATCH (ch:Character {canonical_name: c.worshipper})
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
            MATCH (ch:Character {canonical_name: sc.character_name})
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
