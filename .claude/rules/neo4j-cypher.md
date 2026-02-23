---
paths:
  - "**/*.cypher"
  - "scripts/**"
---

# Neo4j Cypher Rules

## Queries
- Always use parameterized queries: `WHERE n.name = $name` (never string interpolation)
- Use MERGE (not CREATE) for entities to respect uniqueness constraints
- Set `batch_id` on all writes for rollback capability

## Temporal Pattern
- All temporal relations use `valid_from_chapter` / `valid_to_chapter` (integers, not datetime)
- `valid_to_chapter` is NULL for currently valid relations
- Point-in-time query: `WHERE r.valid_from_chapter <= $ch AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter >= $ch)`

## Indexes & Constraints
- Uniqueness constraints on all entity canonical identifiers
- Composite indexes on temporal fields for range queries
- Fulltext indexes for text search
- Vector indexes for embedding similarity

## Naming Conventions
- Node labels: PascalCase (`:Character`, `:Skill`, `:Event`)
- Relationship types: UPPER_SNAKE_CASE (`:HAS_SKILL`, `:LOCATED_AT`)
- Properties: snake_case (`valid_from_chapter`, `canonical_name`)
