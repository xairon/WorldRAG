// ============================================================
// WorldRAG — Neo4j Schema Initialization
// ============================================================
// Run once on fresh database: cat scripts/init_neo4j.cypher | cypher-shell -u neo4j -p worldrag
// Or via Neo4j Browser at http://localhost:7474
//
// Ontology: Layer 1 (Core Narrative) + Layer 2 (LitRPG)
// Temporal model: chapter-based integers (valid_from_chapter / valid_to_chapter)
// ============================================================

// === DROP OLD SINGLE-PROPERTY CONSTRAINTS (B9 migration) ===
// These old constraints allowed cross-book collisions. Drop them before
// creating the new composite (name, book_id) constraints.
DROP CONSTRAINT character_unique IF EXISTS;
DROP CONSTRAINT faction_unique IF EXISTS;
DROP CONSTRAINT location_unique IF EXISTS;
DROP CONSTRAINT concept_unique IF EXISTS;
DROP CONSTRAINT title_unique IF EXISTS;
DROP CONSTRAINT skill_unique IF EXISTS;
DROP CONSTRAINT class_unique IF EXISTS;
DROP CONSTRAINT item_unique IF EXISTS;
DROP CONSTRAINT creature_unique IF EXISTS;
DROP CONSTRAINT event_unique IF EXISTS;
DROP CONSTRAINT bloodline_unique IF EXISTS;
DROP CONSTRAINT church_unique IF EXISTS;
DROP CONSTRAINT quest_unique IF EXISTS;
DROP CONSTRAINT achievement_unique IF EXISTS;

// === UNIQUENESS CONSTRAINTS ===
// Prevent duplicate entities during concurrent extraction.
// All entity types use composite (name, book_id) to prevent cross-book collisions.

CREATE CONSTRAINT series_unique IF NOT EXISTS
FOR (s:Series) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT book_unique IF NOT EXISTS
FOR (b:Book) REQUIRE b.title IS UNIQUE;

CREATE CONSTRAINT chapter_unique IF NOT EXISTS
FOR (c:Chapter) REQUIRE (c.book_id, c.number) IS UNIQUE;

CREATE CONSTRAINT character_book_unique IF NOT EXISTS
FOR (c:Character) REQUIRE (c.canonical_name, c.book_id) IS UNIQUE;

CREATE CONSTRAINT faction_book_unique IF NOT EXISTS
FOR (f:Faction) REQUIRE (f.name, f.book_id) IS UNIQUE;

CREATE CONSTRAINT location_book_unique IF NOT EXISTS
FOR (l:Location) REQUIRE (l.name, l.book_id) IS UNIQUE;

CREATE CONSTRAINT concept_book_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE (c.name, c.book_id) IS UNIQUE;

CREATE CONSTRAINT title_book_unique IF NOT EXISTS
FOR (t:Title) REQUIRE (t.name, t.book_id) IS UNIQUE;

CREATE CONSTRAINT system_unique IF NOT EXISTS
FOR (s:System) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT race_unique IF NOT EXISTS
FOR (r:Race) REQUIRE r.name IS UNIQUE;

// Skills and classes — composite on (name, book_id)
CREATE CONSTRAINT skill_book_unique IF NOT EXISTS
FOR (s:Skill) REQUIRE (s.name, s.book_id) IS UNIQUE;

CREATE CONSTRAINT class_book_unique IF NOT EXISTS
FOR (c:Class) REQUIRE (c.name, c.book_id) IS UNIQUE;

CREATE CONSTRAINT item_book_unique IF NOT EXISTS
FOR (i:Item) REQUIRE (i.name, i.book_id) IS UNIQUE;

CREATE CONSTRAINT creature_book_unique IF NOT EXISTS
FOR (cr:Creature) REQUIRE (cr.name, cr.book_id) IS UNIQUE;

// Events — composite on name + chapter_start + book_id
CREATE CONSTRAINT event_book_unique IF NOT EXISTS
FOR (e:Event) REQUIRE (e.name, e.chapter_start, e.book_id) IS UNIQUE;

// Paragraphs — composite on book_id + chapter_number + index
CREATE CONSTRAINT paragraph_unique IF NOT EXISTS
FOR (p:Paragraph) REQUIRE (p.book_id, p.chapter_number, p.index) IS UNIQUE;

// ── V3: Character State Tracking ──────────────────────────────────────

// StateChange ledger
CREATE CONSTRAINT state_change_unique IF NOT EXISTS
  FOR (sc:StateChange)
  REQUIRE (sc.character_name, sc.book_id, sc.chapter, sc.category, sc.name, sc.action) IS UNIQUE;

CREATE INDEX state_change_character IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.character_name, sc.book_id);

CREATE INDEX state_change_chapter IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.book_id, sc.chapter);

CREATE INDEX state_change_category IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.category);

// BlueBox grouping
CREATE CONSTRAINT bluebox_unique IF NOT EXISTS
  FOR (bb:BlueBox) REQUIRE (bb.book_id, bb.chapter, bb.index) IS UNIQUE;

// Layer 3: Bloodline — composite on (name, book_id)
CREATE CONSTRAINT bloodline_book_unique IF NOT EXISTS
  FOR (b:Bloodline) REQUIRE (b.name, b.book_id) IS UNIQUE;

// Layer 3: Profession — already composite
CREATE CONSTRAINT profession_unique IF NOT EXISTS
  FOR (p:Profession) REQUIRE (p.name, p.book_id) IS UNIQUE;

// Layer 3: PrimordialChurch — composite on (deity_name, book_id)
CREATE CONSTRAINT church_book_unique IF NOT EXISTS
  FOR (pc:PrimordialChurch) REQUIRE (pc.deity_name, pc.book_id) IS UNIQUE;

// V3 entity types — composite on (name, book_id)
CREATE CONSTRAINT quest_book_unique IF NOT EXISTS
  FOR (q:QuestObjective) REQUIRE (q.name, q.book_id) IS UNIQUE;

CREATE CONSTRAINT achievement_book_unique IF NOT EXISTS
  FOR (a:Achievement) REQUIRE (a.name, a.book_id) IS UNIQUE;

// G5: Community hierarchy — uniqueness on community ID
CREATE CONSTRAINT community_unique IF NOT EXISTS
  FOR (c:Community) REQUIRE c.id IS UNIQUE;

CREATE INDEX community_book IF NOT EXISTS
  FOR (c:Community) ON (c.book_id);

CREATE INDEX community_level IF NOT EXISTS
  FOR (c:Community) ON (c.level);

// Batch ID indexes for new types
CREATE INDEX state_change_batch IF NOT EXISTS
  FOR (sc:StateChange) ON (sc.batch_id);

CREATE INDEX bluebox_batch IF NOT EXISTS
  FOR (bb:BlueBox) ON (bb.batch_id);

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
    `vector.similarity_function`: 'cosine',
    `vector.hnsw.m`: 24,
    `vector.hnsw.ef_construction`: 200,
    `vector.quantization.enabled`: false
  }
};

// === RELATIONSHIP VECTOR INDEX ===
// For semantic search on RELATES_TO embeddings (LightRAG technique)
// Enables queries like "find all betrayals" or "find all level-ups"

CREATE VECTOR INDEX rel_relates_to_embedding IF NOT EXISTS
FOR ()-[r:RELATES_TO]-() ON (r.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1024,
    `vector.similarity_function`: 'cosine',
    `vector.hnsw.m`: 16,
    `vector.hnsw.ef_construction`: 150,
    `vector.quantization.enabled`: false
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

// G4: valid_to_chapter indexes for temporal closing queries
CREATE INDEX rel_has_class_valid_to IF NOT EXISTS
FOR ()-[r:HAS_CLASS]-() ON (r.valid_to_chapter);

CREATE INDEX rel_has_skill_valid_to IF NOT EXISTS
FOR ()-[r:HAS_SKILL]-() ON (r.valid_to_chapter);

CREATE INDEX rel_at_level_valid_to IF NOT EXISTS
FOR ()-[r:AT_LEVEL]-() ON (r.valid_to_chapter);

CREATE INDEX rel_relates_to_valid_to IF NOT EXISTS
FOR ()-[r:RELATES_TO]-() ON (r.valid_to_chapter);

CREATE INDEX rel_mentioned_in IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.char_start);

CREATE INDEX rel_mentioned_in_type IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.mention_type);

// ── V3: New entity types ─────────────────────────────────────────────

CREATE CONSTRAINT stat_block_unique IF NOT EXISTS
  FOR (s:StatBlock) REQUIRE (s.character_name, s.chapter) IS UNIQUE;

// quest_unique and achievement_unique now defined above as composite (name, book_id)

CREATE CONSTRAINT realm_unique IF NOT EXISTS
  FOR (r:Realm) REQUIRE r.name IS UNIQUE;

CREATE INDEX stat_block_character IF NOT EXISTS FOR (s:StatBlock) ON (s.character_name);
CREATE INDEX quest_status IF NOT EXISTS FOR (q:QuestObjective) ON (q.status);
CREATE INDEX achievement_name IF NOT EXISTS FOR (a:Achievement) ON (a.name);
CREATE INDEX realm_order IF NOT EXISTS FOR (r:Realm) ON (r.order);

// === VERIFICATION ===
// Run this to verify all constraints and indexes are created:
// SHOW CONSTRAINTS;
// SHOW INDEXES;
