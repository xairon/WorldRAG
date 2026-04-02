// fix_duplicate_relations.cypher
// Finds all duplicate relationships (same source node, target node, and type)
// created by the old MERGE pattern that included valid_from_chapter in the key.
//
// For each group of duplicates:
//   - Keeps the relationship with the lowest valid_from_chapter (earliest occurrence)
//   - Transfers the max last_seen_chapter across duplicates to the kept relationship
//   - Sums the occurrences counters (treating NULL as 1)
//   - Deletes the duplicate relationships
//
// Run this once in Neo4j Browser after deploying the fix to entity_repo.py.
// Safe to run multiple times (idempotent — no duplicates remain after first run).

// Step 1: Identify duplicate groups and consolidate onto the earliest relationship.
MATCH (a)-[r]->(b)
WHERE NOT type(r) IN ['CONTAINS', 'HAS_CHUNK', 'HAS_PARAGRAPH', 'NEXT', 'IN_BOOK']
WITH a, b, type(r) AS rel_type, collect(r) AS rels
WHERE size(rels) > 1
WITH a, b, rel_type, rels,
     // Find the relationship with the lowest valid_from_chapter to keep
     reduce(
         keeper = rels[0],
         r IN rels |
         CASE
             WHEN r.valid_from_chapter IS NOT NULL
                  AND (keeper.valid_from_chapter IS NULL OR r.valid_from_chapter < keeper.valid_from_chapter)
             THEN r
             ELSE keeper
         END
     ) AS kept,
     // Compute aggregates across all duplicates
     reduce(max_seen = 0, r IN rels |
         CASE WHEN r.last_seen_chapter IS NOT NULL AND r.last_seen_chapter > max_seen
              THEN r.last_seen_chapter ELSE max_seen END
     ) AS max_last_seen,
     reduce(total = 0, r IN rels |
         total + coalesce(r.occurrences, 1)
     ) AS total_occurrences

// Step 2: Update the kept relationship with consolidated values.
SET kept.last_seen_chapter = CASE WHEN max_last_seen > 0 THEN max_last_seen ELSE kept.last_seen_chapter END,
    kept.occurrences = total_occurrences

// Step 3: Delete all duplicates except the kept one.
WITH a, b, rel_type, rels, kept
UNWIND rels AS r
WITH r, kept
WHERE r <> kept
DELETE r

RETURN count(*) AS duplicates_deleted;
