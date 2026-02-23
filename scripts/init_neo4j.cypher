// ============================================================
// WorldRAG — Neo4j Schema Initialization
// ============================================================
// Run once on fresh database: cat scripts/init_neo4j.cypher | cypher-shell -u neo4j -p worldrag
// Or via Neo4j Browser at http://localhost:7474
//
// Ontology: Layer 1 (Core Narrative) + Layer 2 (LitRPG)
// Temporal model: chapter-based integers (valid_from_chapter / valid_to_chapter)
// ============================================================

// === UNIQUENESS CONSTRAINTS ===
// Prevent duplicate entities during concurrent extraction

CREATE CONSTRAINT series_unique IF NOT EXISTS
FOR (s:Series) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT book_unique IF NOT EXISTS
FOR (b:Book) REQUIRE b.title IS UNIQUE;

CREATE CONSTRAINT chapter_unique IF NOT EXISTS
FOR (c:Chapter) REQUIRE (c.book_id, c.number) IS UNIQUE;

CREATE CONSTRAINT character_unique IF NOT EXISTS
FOR (c:Character) REQUIRE c.canonical_name IS UNIQUE;

CREATE CONSTRAINT faction_unique IF NOT EXISTS
FOR (f:Faction) REQUIRE f.name IS UNIQUE;

CREATE CONSTRAINT location_unique IF NOT EXISTS
FOR (l:Location) REQUIRE l.name IS UNIQUE;

CREATE CONSTRAINT concept_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT title_unique IF NOT EXISTS
FOR (t:Title) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT system_unique IF NOT EXISTS
FOR (s:System) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT race_unique IF NOT EXISTS
FOR (r:Race) REQUIRE r.name IS UNIQUE;

// Composite uniqueness for skills and classes (name + system)
CREATE CONSTRAINT skill_unique IF NOT EXISTS
FOR (s:Skill) REQUIRE (s.name, s.system_name) IS UNIQUE;

CREATE CONSTRAINT class_unique IF NOT EXISTS
FOR (c:Class) REQUIRE (c.name, c.system_name) IS UNIQUE;

// === NODE PROPERTY INDEXES ===

CREATE INDEX character_name IF NOT EXISTS
FOR (c:Character) ON (c.name);

CREATE INDEX character_first_appearance IF NOT EXISTS
FOR (c:Character) ON (c.first_appearance_chapter);

CREATE INDEX event_chapter IF NOT EXISTS
FOR (e:Event) ON (e.chapter_start);

CREATE INDEX event_significance IF NOT EXISTS
FOR (e:Event) ON (e.significance);

CREATE INDEX event_type IF NOT EXISTS
FOR (e:Event) ON (e.event_type);

CREATE INDEX arc_status IF NOT EXISTS
FOR (a:Arc) ON (a.status);

CREATE INDEX chunk_chapter IF NOT EXISTS
FOR (c:Chunk) ON (c.chapter_id);

CREATE INDEX chunk_position IF NOT EXISTS
FOR (c:Chunk) ON (c.position);

CREATE INDEX skill_name IF NOT EXISTS
FOR (s:Skill) ON (s.name);

CREATE INDEX class_name IF NOT EXISTS
FOR (c:Class) ON (c.name);

CREATE INDEX item_name IF NOT EXISTS
FOR (i:Item) ON (i.name);

// Batch ID index for rollback operations
CREATE INDEX character_batch IF NOT EXISTS
FOR (c:Character) ON (c.batch_id);

CREATE INDEX event_batch IF NOT EXISTS
FOR (e:Event) ON (e.batch_id);

CREATE INDEX skill_batch IF NOT EXISTS
FOR (s:Skill) ON (s.batch_id);

// === FULLTEXT INDEXES ===
// For keyword search in hybrid retrieval pipeline

CREATE FULLTEXT INDEX character_fulltext IF NOT EXISTS
FOR (c:Character) ON EACH [c.name, c.canonical_name, c.description];

CREATE FULLTEXT INDEX event_fulltext IF NOT EXISTS
FOR (e:Event) ON EACH [e.name, e.description];

CREATE FULLTEXT INDEX location_fulltext IF NOT EXISTS
FOR (l:Location) ON EACH [l.name, l.description];

CREATE FULLTEXT INDEX skill_fulltext IF NOT EXISTS
FOR (s:Skill) ON EACH [s.name, s.description];

CREATE FULLTEXT INDEX class_fulltext IF NOT EXISTS
FOR (c:Class) ON EACH [c.name, c.description];

CREATE FULLTEXT INDEX item_fulltext IF NOT EXISTS
FOR (i:Item) ON EACH [i.name, i.description];

CREATE FULLTEXT INDEX concept_fulltext IF NOT EXISTS
FOR (c:Concept) ON EACH [c.name, c.description];

CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS
FOR (c:Chunk) ON EACH [c.text];

// === VECTOR INDEX ===
// For semantic search with Voyage AI embeddings (1024 dimensions)
// Adjust dimensions if using different model variant

CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1024,
    `vector.similarity_function`: 'cosine'
  }
};

// === RELATIONSHIP INDEXES ===
// For temporal queries on relationships

// Note: Neo4j 5.x supports relationship property indexes
CREATE INDEX rel_has_class_temporal IF NOT EXISTS
FOR ()-[r:HAS_CLASS]-() ON (r.valid_from_chapter);

CREATE INDEX rel_has_skill_temporal IF NOT EXISTS
FOR ()-[r:HAS_SKILL]-() ON (r.valid_from_chapter);

CREATE INDEX rel_at_level_temporal IF NOT EXISTS
FOR ()-[r:AT_LEVEL]-() ON (r.valid_from_chapter);

CREATE INDEX rel_located_at_temporal IF NOT EXISTS
FOR ()-[r:LOCATED_AT]-() ON (r.valid_from_chapter);

CREATE INDEX rel_possesses_temporal IF NOT EXISTS
FOR ()-[r:POSSESSES]-() ON (r.valid_from_chapter);

CREATE INDEX rel_relates_to_temporal IF NOT EXISTS
FOR ()-[r:RELATES_TO]-() ON (r.valid_from_chapter);

CREATE INDEX rel_member_of_temporal IF NOT EXISTS
FOR ()-[r:MEMBER_OF]-() ON (r.valid_from_chapter);

CREATE INDEX rel_grounded_in IF NOT EXISTS
FOR ()-[r:GROUNDED_IN]-() ON (r.char_offset_start);

// === VERIFICATION ===
// Run this to verify all constraints and indexes are created:
// SHOW CONSTRAINTS;
// SHOW INDEXES;
