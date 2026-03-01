---
name: neo4j-inspect
description: Query and inspect the Neo4j knowledge graph — entity counts, relationships, dedup quality, temporal consistency
disable-model-invocation: true
---

# Neo4j Knowledge Graph Inspector

Run diagnostic Cypher queries to inspect the WorldRAG knowledge graph.

## Connection

```bash
# Interactive Cypher shell
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p worldrag

# Single query
docker exec rag-neo4j-1 cypher-shell -u neo4j -p worldrag "YOUR QUERY HERE"
```

- **Bolt**: bolt://127.0.0.1:7687
- **Browser**: http://localhost:7474
- **Credentials**: neo4j / worldrag

## Diagnostic Queries

### Overview — Entity counts by label

```cypher
CALL db.labels() YIELD label
CALL db.stats.retrieve('GRAPH COUNTS') YIELD data
WITH label
MATCH (n) WHERE label IN labels(n)
WITH label, count(n) AS cnt
WHERE cnt > 0
RETURN label, cnt ORDER BY cnt DESC
```

Simpler version:
```cypher
MATCH (n)
WITH labels(n) AS lbls, count(*) AS cnt
UNWIND lbls AS label
WITH label, sum(cnt) AS total
WHERE NOT label IN ['Book', 'Chapter', 'Chunk', 'Series', 'Paragraph']
RETURN label, total ORDER BY total DESC
```

### Book-scoped entity counts

```cypher
MATCH (n {book_id: $book_id})
WHERE NOT n:Book AND NOT n:Chapter AND NOT n:Chunk AND NOT n:Paragraph
WITH labels(n)[0] AS label, count(*) AS cnt
RETURN label, cnt ORDER BY cnt DESC
```

### Characters with relationship counts

```cypher
MATCH (c:Character {book_id: $book_id})
OPTIONAL MATCH (c)-[r]-()
WITH c, count(r) AS rels
RETURN c.canonical_name AS name, c.role AS role, c.status AS status, rels
ORDER BY rels DESC LIMIT 20
```

### Duplicate detection — potential missed dedup

```cypher
// Characters with similar names (edit distance)
MATCH (a:Character), (b:Character)
WHERE a.book_id = $book_id AND b.book_id = $book_id
  AND id(a) < id(b)
  AND (a.canonical_name CONTAINS b.canonical_name
       OR b.canonical_name CONTAINS a.canonical_name)
RETURN a.canonical_name, b.canonical_name, a.aliases, b.aliases
```

### Orphaned nodes — entities with no relationships

```cypher
MATCH (n {book_id: $book_id})
WHERE NOT n:Book AND NOT n:Chapter AND NOT n:Chunk AND NOT n:Paragraph
  AND NOT (n)-[]-()
WITH labels(n)[0] AS label, n.name AS name
RETURN label, name ORDER BY label, name
```

### Temporal consistency — relationships with valid_from_chapter

```cypher
MATCH (c:Character)-[r:HAS_SKILL]->(s:Skill)
WHERE c.book_id = $book_id
RETURN c.canonical_name AS character, s.name AS skill,
       r.valid_from_chapter AS acquired_chapter
ORDER BY r.valid_from_chapter
```

### GROUNDED_IN relationships — source traceability

```cypher
MATCH (n {book_id: $book_id})-[g:GROUNDED_IN]->(chunk:Chunk)
WHERE NOT n:Chapter AND NOT n:Book
WITH labels(n)[0] AS label, count(g) AS groundings
RETURN label, groundings ORDER BY groundings DESC
```

### Batch audit — entities by batch_id

```cypher
MATCH (n {book_id: $book_id})
WHERE n.batch_id IS NOT NULL AND NOT n:Book AND NOT n:Chapter AND NOT n:Chunk
WITH n.batch_id AS batch, count(*) AS cnt
RETURN batch, cnt ORDER BY cnt DESC LIMIT 10
```

### Fulltext search test

```cypher
CALL db.index.fulltext.queryNodes('entity_fulltext', 'search term here')
YIELD node, score
RETURN labels(node) AS labels, node.name AS name, score
ORDER BY score DESC LIMIT 10
```

### Vector index status

```cypher
SHOW INDEXES YIELD name, type, state, populationPercent
WHERE type = 'VECTOR' OR type = 'FULLTEXT'
RETURN name, type, state, populationPercent
```

### Chunks with/without embeddings

```cypher
MATCH (c:Chunk {book_id: $book_id})
WITH count(c) AS total,
     count(CASE WHEN c.embedding IS NOT NULL THEN 1 END) AS embedded
RETURN total, embedded, total - embedded AS missing
```

### Schema — constraints and indexes

```cypher
SHOW CONSTRAINTS
```

```cypher
SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state
RETURN name, type, labelsOrTypes, properties, state
ORDER BY type, name
```

## Key Files Reference

| Component | Path |
|-----------|------|
| Entity schemas | `backend/app/schemas/extraction.py` |
| Entity persistence | `backend/app/repositories/entity_repo.py` |
| Book queries | `backend/app/repositories/book_repo.py` |
| Graph search API | `backend/app/api/routes/graph.py` |
| Schema init | `scripts/init_neo4j.cypher` |
| Ontology definitions | `ontology/*.yaml` |

## Entity Types (19 labels)

**Narrative Core**: Book, Chapter, Chunk, Series, Paragraph
**Extraction (11 types)**: Character, Skill, Class, Title, Event, Location, Item, Creature, Faction, Concept, StateChange
**Special**: BlueBox, Bloodline, Profession, PrimordialChurch (Layer 3)

All extracted entities carry: `book_id`, `batch_id`, `created_at`
Characters use `canonical_name` as unique key; others use `name`.
Events use composite key: `(name, chapter_start)`.
