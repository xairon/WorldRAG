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

// Skills and classes — MERGE by name (system_name optional property)
CREATE CONSTRAINT skill_unique IF NOT EXISTS
FOR (s:Skill) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT class_unique IF NOT EXISTS
FOR (c:Class) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT item_unique IF NOT EXISTS
FOR (i:Item) REQUIRE i.name IS UNIQUE;

CREATE CONSTRAINT creature_unique IF NOT EXISTS
FOR (cr:Creature) REQUIRE cr.name IS UNIQUE;

// Events — composite on name + chapter_start (same event name in different chapters)
CREATE CONSTRAINT event_unique IF NOT EXISTS
FOR (e:Event) REQUIRE (e.name, e.chapter_start) IS UNIQUE;

// Paragraphs — composite on book_id + chapter_number + index
CREATE CONSTRAINT paragraph_unique IF NOT EXISTS
FOR (p:Paragraph) REQUIRE (p.book_id, p.chapter_number, p.index) IS UNIQUE;

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

CREATE INDEX paragraph_type IF NOT EXISTS
FOR (p:Paragraph) ON (p.type);

CREATE INDEX paragraph_chapter IF NOT EXISTS
FOR (p:Paragraph) ON (p.chapter_number);

// Additional property indexes for common query patterns
CREATE INDEX character_role IF NOT EXISTS
FOR (c:Character) ON (c.role);

CREATE INDEX skill_type IF NOT EXISTS
FOR (s:Skill) ON (s.skill_type);

CREATE INDEX item_rarity IF NOT EXISTS
FOR (i:Item) ON (i.rarity);

CREATE INDEX creature_threat IF NOT EXISTS
FOR (cr:Creature) ON (cr.threat_level);

// Batch ID indexes for rollback operations
CREATE INDEX character_batch IF NOT EXISTS
FOR (c:Character) ON (c.batch_id);

CREATE INDEX event_batch IF NOT EXISTS
FOR (e:Event) ON (e.batch_id);

CREATE INDEX skill_batch IF NOT EXISTS
FOR (s:Skill) ON (s.batch_id);

CREATE INDEX class_batch IF NOT EXISTS
FOR (c:Class) ON (c.batch_id);

CREATE INDEX item_batch IF NOT EXISTS
FOR (i:Item) ON (i.batch_id);

CREATE INDEX creature_batch IF NOT EXISTS
FOR (cr:Creature) ON (cr.batch_id);

CREATE INDEX location_batch IF NOT EXISTS
FOR (l:Location) ON (l.batch_id);

CREATE INDEX faction_batch IF NOT EXISTS
FOR (f:Faction) ON (f.batch_id);

CREATE INDEX concept_batch IF NOT EXISTS
FOR (c:Concept) ON (c.batch_id);

CREATE INDEX title_batch IF NOT EXISTS
FOR (t:Title) ON (t.batch_id);

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

CREATE FULLTEXT INDEX creature_fulltext IF NOT EXISTS
FOR (cr:Creature) ON EACH [cr.name, cr.description, cr.species];

CREATE FULLTEXT INDEX faction_fulltext IF NOT EXISTS
FOR (f:Faction) ON EACH [f.name, f.description];

CREATE FULLTEXT INDEX title_fulltext IF NOT EXISTS
FOR (t:Title) ON EACH [t.name, t.description];

CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS
FOR (c:Chunk) ON EACH [c.text];

// Cross-label entity search (for Graph Explorer search endpoint)
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
FOR (n:Character|Skill|Class|Title|Event|Location|Item|Creature|Faction|Concept)
ON EACH [n.name, n.description];

// Compound index for embedding pipeline write-back (match on chapter_id + position)
CREATE INDEX chunk_chapter_position IF NOT EXISTS
FOR (c:Chunk) ON (c.chapter_id, c.position);

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

// DEPRECATED in V2: GROUNDED_IN relationships replaced by MENTIONED_IN.
// The GROUNDED_IN index is no longer needed for the current pipeline.
// CREATE INDEX rel_grounded_in IF NOT EXISTS
// FOR ()-[r:GROUNDED_IN]-() ON (r.char_offset_start);

CREATE INDEX rel_mentioned_in IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.char_start);

CREATE INDEX rel_mentioned_in_type IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.mention_type);

// === VERIFICATION ===
// Run this to verify all constraints and indexes are created:
// SHOW CONSTRAINTS;
// SHOW INDEXES;
