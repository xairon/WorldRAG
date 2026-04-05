// ============================================================================
// GOLEM v1.1 Migration — Phase C: Neo4j data migration
// ============================================================================
// Run AFTER deploying Phase A+B code (v4.0.0 ontology).
// Run BEFORE creating new constraints/indexes (init_neo4j.cypher).
//
// Prerequisites:
//   - Backup your Neo4j database before running
//   - Run statements one at a time (not all at once) in Neo4j Browser
//   - Verify counts after each step
// ============================================================================

// ── 1. Item → Object (label rename) ────────────────────────────────────
// Adds :Object label, removes :Item label
MATCH (n:Item)
SET n:Object
REMOVE n:Item;

// Rename item_type → object_type property
MATCH (n:Object)
WHERE n.item_type IS NOT NULL
SET n.object_type = n.item_type
REMOVE n.item_type;

// ── 2. Arc → NarrativeSequence (label + property rename) ───────────────
MATCH (n:Arc)
SET n:NarrativeSequence
REMOVE n:Arc;

// Rename arc_type → sequence_type
MATCH (n:NarrativeSequence)
WHERE n.arc_type IS NOT NULL
SET n.sequence_type = n.arc_type
REMOVE n.arc_type;

// Rename PART_OF_ARC → SEQUENCED_IN edges
MATCH (e:Event)-[r:PART_OF_ARC]->(a:NarrativeSequence)
CREATE (e)-[:SEQUENCED_IN]->(a)
DELETE r;

// ── 3. event_type → event_category (property rename on Event) ──────────
MATCH (ev:Event)
WHERE ev.event_type IS NOT NULL
SET ev.event_category = ev.event_type
REMOVE ev.event_type;

// ── 4. OCCURS_BEFORE → PRECEDES (relationship rename) ──────────────────
MATCH (a:Event)-[r:OCCURS_BEFORE]->(b:Event)
CREATE (a)-[:PRECEDES]->(b)
DELETE r;

// ── 5. Character.role → removed (moved to NarrativeRole nodes) ─────────
// Copy role to agency if not already set, then remove role
MATCH (c:Character)
WHERE c.role IS NOT NULL AND c.agency IS NULL
SET c.agency = CASE
    WHEN c.role IN ['protagonist', 'antagonist', 'mentor'] THEN 'active'
    WHEN c.role IN ['minor', 'neutral'] THEN 'passive'
    ELSE 'ambiguous'
END;

MATCH (c:Character)
WHERE c.role IS NOT NULL
REMOVE c.role;

// ── 6. RELATES_TO → SocialRelationship + INVOLVED_IN (reification) ─────
// Each RELATES_TO edge becomes:
//   - 1 SocialRelationship node
//   - 2 INVOLVED_IN edges (one per participant)
//   - Original edge deleted
//
// NOTE: Run this in batches if you have >10K RELATES_TO edges

MATCH (a:Character)-[r:RELATES_TO]->(b:Character)
WITH a, b, r,
     a.canonical_name + ' — ' + b.canonical_name AS sr_name,
     CASE
         WHEN r.type IS NOT NULL THEN r.type
         WHEN r.subtype IS NOT NULL THEN r.subtype
         ELSE 'professional'
     END AS rel_type,
     coalesce(r.valid_from_chapter, 1) AS vfc
CREATE (sr:SocialRelationship {
    name: sr_name,
    relationship_type: rel_type,
    book_id: coalesce(a.book_id, 'unknown'),
    valid_from_chapter: vfc,
    valid_to_chapter: r.valid_to_chapter,
    description: coalesce(r.context, ''),
    batch_id: 'golem_migration_v4',
    created_at: timestamp()
})
CREATE (a)-[:INVOLVED_IN {
    role: 'participant',
    valid_from_chapter: vfc,
    batch_id: 'golem_migration_v4'
}]->(sr)
CREATE (b)-[:INVOLVED_IN {
    role: 'participant',
    valid_from_chapter: vfc,
    batch_id: 'golem_migration_v4'
}]->(sr)
DELETE r;

// ── 7. Drop old constraints (run before creating new ones) ─────────────
DROP CONSTRAINT constraint_item_name IF EXISTS;
DROP CONSTRAINT constraint_arc_name IF EXISTS;

// ── 8. Drop old fulltext index (recreated by init_neo4j.cypher) ────────
DROP INDEX entity_fulltext IF EXISTS;

// ── Verification queries ───────────────────────────────────────────────
// Run these after migration to verify:
//
// MATCH (n:Item) RETURN count(n);           // Should be 0
// MATCH (n:Arc) RETURN count(n);            // Should be 0
// MATCH ()-[r:RELATES_TO]->() RETURN count(r);  // Should be 0
// MATCH ()-[r:OCCURS_BEFORE]->() RETURN count(r);  // Should be 0
// MATCH (n:Object) RETURN count(n);         // Should match old Item count
// MATCH (n:NarrativeSequence) RETURN count(n);  // Should match old Arc count
// MATCH (n:SocialRelationship) RETURN count(n); // Should match old RELATES_TO count
// MATCH (n:Event) WHERE n.event_type IS NOT NULL RETURN count(n);  // Should be 0
// MATCH (n:Character) WHERE n.role IS NOT NULL RETURN count(n);    // Should be 0
