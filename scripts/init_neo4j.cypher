// ============================================================
// WorldRAG — Neo4j Schema Initialization (GOLEM v1.1)
// ============================================================
// Run once on fresh database: cat scripts/init_neo4j.cypher | cypher-shell -u neo4j -p worldrag
// Or via Neo4j Browser at http://localhost:7474
//
// Ontology: Layer 1 (Core Narrative, GOLEM v1.1 aligned) + Layer 2 (LitRPG)
// Temporal model: chapter-based integers (valid_from_chapter / valid_to_chapter)
// ============================================================

// === DROP OLD CONSTRAINTS (pre-GOLEM migration) ===
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
// Drop legacy Item/Arc constraints (Phase C migration)
DROP CONSTRAINT item_book_unique IF EXISTS;

// === UNIQUENESS CONSTRAINTS ===
// All entity types use composite (name, book_id) to prevent cross-book collisions.

// ── Bibliographic ──
CREATE CONSTRAINT series_unique IF NOT EXISTS
FOR (s:Series) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT book_unique IF NOT EXISTS
FOR (b:Book) REQUIRE b.title IS UNIQUE;

CREATE CONSTRAINT chapter_unique IF NOT EXISTS
FOR (c:Chapter) REQUIRE (c.book_id, c.number) IS UNIQUE;

// ── Core GOLEM types ──
CREATE CONSTRAINT character_book_unique IF NOT EXISTS
FOR (c:Character) REQUIRE (c.canonical_name, c.book_id) IS UNIQUE;

CREATE CONSTRAINT object_book_unique IF NOT EXISTS
FOR (o:Object) REQUIRE (o.name, o.book_id) IS UNIQUE;

CREATE CONSTRAINT event_book_unique IF NOT EXISTS
FOR (e:Event) REQUIRE (e.name, e.chapter_start, e.book_id) IS UNIQUE;

CREATE CONSTRAINT location_book_unique IF NOT EXISTS
FOR (l:Location) REQUIRE (l.name, l.book_id) IS UNIQUE;

CREATE CONSTRAINT faction_book_unique IF NOT EXISTS
FOR (f:Faction) REQUIRE (f.name, f.book_id) IS UNIQUE;

CREATE CONSTRAINT concept_book_unique IF NOT EXISTS
FOR (c:Concept) REQUIRE (c.name, c.book_id) IS UNIQUE;

CREATE CONSTRAINT narrative_sequence_book_unique IF NOT EXISTS
FOR (ns:NarrativeSequence) REQUIRE (ns.canonical_name, ns.book_id) IS UNIQUE;

// ── New GOLEM types (Phase C) ──
CREATE CONSTRAINT character_stoff_unique IF NOT EXISTS
FOR (cs:CharacterStoff) REQUIRE (cs.canonical_name, cs.series_id) IS UNIQUE;

CREATE CONSTRAINT setting_unique IF NOT EXISTS
FOR (s:Setting) REQUIRE (s.name, s.book_id) IS UNIQUE;

CREATE CONSTRAINT social_rel_book_unique IF NOT EXISTS
FOR (sr:SocialRelationship) REQUIRE (sr.name, sr.book_id) IS UNIQUE;

CREATE CONSTRAINT narrative_stoff_unique IF NOT EXISTS
FOR (ns:NarrativeStoff) REQUIRE ns.name IS UNIQUE;

// NOT NULL constraints for new types (Neo4j Enterprise only — skipped on Community Edition)
// CREATE CONSTRAINT psych_state_name IF NOT EXISTS FOR (ps:PsychologicalState) REQUIRE ps.name IS NOT NULL;
// CREATE CONSTRAINT character_feature_name IF NOT EXISTS FOR (cf:CharacterFeature) REQUIRE cf.name IS NOT NULL;
// CREATE CONSTRAINT narrative_role_type IF NOT EXISTS FOR (nr:NarrativeRole) REQUIRE nr.role_type IS NOT NULL;
// CREATE CONSTRAINT narrative_unit_prop IF NOT EXISTS FOR (nu:NarrativeUnit) REQUIRE nu.proposition IS NOT NULL;
// CREATE CONSTRAINT textual_feature_name IF NOT EXISTS FOR (tf:TextualFeature) REQUIRE tf.name IS NOT NULL;

// ── LitRPG genre types ──
CREATE CONSTRAINT title_book_unique IF NOT EXISTS
FOR (t:Title) REQUIRE (t.name, t.book_id) IS UNIQUE;

CREATE CONSTRAINT system_unique IF NOT EXISTS
FOR (s:System) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT race_unique IF NOT EXISTS
FOR (r:Race) REQUIRE r.name IS UNIQUE;

CREATE CONSTRAINT skill_book_unique IF NOT EXISTS
FOR (s:Skill) REQUIRE (s.name, s.book_id) IS UNIQUE;

CREATE CONSTRAINT class_book_unique IF NOT EXISTS
FOR (c:Class) REQUIRE (c.name, c.book_id) IS UNIQUE;

CREATE CONSTRAINT creature_book_unique IF NOT EXISTS
FOR (cr:Creature) REQUIRE (cr.name, cr.book_id) IS UNIQUE;

// ── Paragraphs ──
CREATE CONSTRAINT paragraph_unique IF NOT EXISTS
FOR (p:Paragraph) REQUIRE (p.book_id, p.chapter_number, p.index) IS UNIQUE;

// ── V3: State tracking ──
CREATE CONSTRAINT state_change_unique IF NOT EXISTS
FOR (sc:StateChange) REQUIRE (sc.character_name, sc.book_id, sc.chapter, sc.category, sc.name, sc.action) IS UNIQUE;

CREATE CONSTRAINT bluebox_unique IF NOT EXISTS
FOR (bb:BlueBox) REQUIRE (bb.book_id, bb.chapter, bb.index) IS UNIQUE;

// ── Layer 3: Series-specific ──
CREATE CONSTRAINT bloodline_book_unique IF NOT EXISTS
FOR (b:Bloodline) REQUIRE (b.name, b.book_id) IS UNIQUE;

CREATE CONSTRAINT profession_unique IF NOT EXISTS
FOR (p:Profession) REQUIRE (p.name, p.book_id) IS UNIQUE;

CREATE CONSTRAINT church_book_unique IF NOT EXISTS
FOR (pc:PrimordialChurch) REQUIRE (pc.deity_name, pc.book_id) IS UNIQUE;

CREATE CONSTRAINT quest_book_unique IF NOT EXISTS
FOR (q:QuestObjective) REQUIRE (q.name, q.book_id) IS UNIQUE;

CREATE CONSTRAINT achievement_book_unique IF NOT EXISTS
FOR (a:Achievement) REQUIRE (a.name, a.book_id) IS UNIQUE;

CREATE CONSTRAINT community_unique IF NOT EXISTS
FOR (c:Community) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT stat_block_unique IF NOT EXISTS
FOR (s:StatBlock) REQUIRE (s.character_name, s.chapter) IS UNIQUE;

CREATE CONSTRAINT realm_unique IF NOT EXISTS
FOR (r:Realm) REQUIRE r.name IS UNIQUE;

// === NODE PROPERTY INDEXES ===

// ── Core types ──
CREATE INDEX character_name IF NOT EXISTS FOR (c:Character) ON (c.name);
CREATE INDEX character_first_appearance IF NOT EXISTS FOR (c:Character) ON (c.first_appearance_chapter);
CREATE INDEX character_batch IF NOT EXISTS FOR (c:Character) ON (c.batch_id);

CREATE INDEX event_chapter IF NOT EXISTS FOR (e:Event) ON (e.chapter_start);
CREATE INDEX event_significance IF NOT EXISTS FOR (e:Event) ON (e.significance);
CREATE INDEX event_category IF NOT EXISTS FOR (e:Event) ON (e.event_category);
CREATE INDEX event_batch IF NOT EXISTS FOR (e:Event) ON (e.batch_id);

CREATE INDEX object_name IF NOT EXISTS FOR (o:Object) ON (o.name);
CREATE INDEX object_batch IF NOT EXISTS FOR (o:Object) ON (o.batch_id);

CREATE INDEX location_batch IF NOT EXISTS FOR (l:Location) ON (l.batch_id);
CREATE INDEX faction_batch IF NOT EXISTS FOR (f:Faction) ON (f.batch_id);
CREATE INDEX concept_batch IF NOT EXISTS FOR (c:Concept) ON (c.batch_id);

CREATE INDEX narrative_seq_status IF NOT EXISTS FOR (ns:NarrativeSequence) ON (ns.status);

// ── New GOLEM type indexes ──
CREATE INDEX psych_state_character IF NOT EXISTS FOR (ps:PsychologicalState) ON (ps.character_name);
CREATE INDEX psych_state_chapter IF NOT EXISTS FOR (ps:PsychologicalState) ON (ps.chapter_start);
CREATE INDEX psych_state_batch IF NOT EXISTS FOR (ps:PsychologicalState) ON (ps.batch_id);

CREATE INDEX setting_batch IF NOT EXISTS FOR (s:Setting) ON (s.batch_id);

CREATE INDEX char_feature_character IF NOT EXISTS FOR (cf:CharacterFeature) ON (cf.character_name);
CREATE INDEX char_feature_batch IF NOT EXISTS FOR (cf:CharacterFeature) ON (cf.batch_id);

CREATE INDEX narrative_role_character IF NOT EXISTS FOR (nr:NarrativeRole) ON (nr.character_name);
CREATE INDEX narrative_role_batch IF NOT EXISTS FOR (nr:NarrativeRole) ON (nr.batch_id);

CREATE INDEX social_rel_batch IF NOT EXISTS FOR (sr:SocialRelationship) ON (sr.batch_id);
CREATE INDEX social_rel_type IF NOT EXISTS FOR (sr:SocialRelationship) ON (sr.relationship_type);

CREATE INDEX textual_feature_batch IF NOT EXISTS FOR (tf:TextualFeature) ON (tf.batch_id);

// ── LitRPG indexes ──
CREATE INDEX skill_name IF NOT EXISTS FOR (s:Skill) ON (s.name);
CREATE INDEX skill_batch IF NOT EXISTS FOR (s:Skill) ON (s.batch_id);
CREATE INDEX skill_type IF NOT EXISTS FOR (s:Skill) ON (s.skill_type);
CREATE INDEX class_name IF NOT EXISTS FOR (c:Class) ON (c.name);
CREATE INDEX class_batch IF NOT EXISTS FOR (c:Class) ON (c.batch_id);
CREATE INDEX title_batch IF NOT EXISTS FOR (t:Title) ON (t.batch_id);
CREATE INDEX creature_batch IF NOT EXISTS FOR (cr:Creature) ON (cr.batch_id);
CREATE INDEX creature_threat IF NOT EXISTS FOR (cr:Creature) ON (cr.threat_level);

// ── Other indexes ──
CREATE INDEX chunk_chapter IF NOT EXISTS FOR (c:Chunk) ON (c.chapter_id);
CREATE INDEX chunk_position IF NOT EXISTS FOR (c:Chunk) ON (c.position);
CREATE INDEX paragraph_type IF NOT EXISTS FOR (p:Paragraph) ON (p.type);
CREATE INDEX paragraph_chapter IF NOT EXISTS FOR (p:Paragraph) ON (p.chapter_number);
CREATE INDEX community_book IF NOT EXISTS FOR (c:Community) ON (c.book_id);
CREATE INDEX community_level IF NOT EXISTS FOR (c:Community) ON (c.level);
CREATE INDEX state_change_character IF NOT EXISTS FOR (sc:StateChange) ON (sc.character_name, sc.book_id);
CREATE INDEX state_change_chapter IF NOT EXISTS FOR (sc:StateChange) ON (sc.book_id, sc.chapter);
CREATE INDEX state_change_category IF NOT EXISTS FOR (sc:StateChange) ON (sc.category);
CREATE INDEX state_change_batch IF NOT EXISTS FOR (sc:StateChange) ON (sc.batch_id);
CREATE INDEX bluebox_batch IF NOT EXISTS FOR (bb:BlueBox) ON (bb.batch_id);
CREATE INDEX stat_block_character IF NOT EXISTS FOR (s:StatBlock) ON (s.character_name);
CREATE INDEX quest_status IF NOT EXISTS FOR (q:QuestObjective) ON (q.status);
CREATE INDEX achievement_name IF NOT EXISTS FOR (a:Achievement) ON (a.name);
CREATE INDEX realm_order IF NOT EXISTS FOR (r:Realm) ON (r.order);

// === FULLTEXT INDEXES ===

// Per-type fulltext for targeted search
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

CREATE FULLTEXT INDEX object_fulltext IF NOT EXISTS
FOR (o:Object) ON EACH [o.name, o.description];

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

// New GOLEM type fulltext indexes
CREATE FULLTEXT INDEX setting_fulltext IF NOT EXISTS
FOR (s:Setting) ON EACH [s.name, s.description];

CREATE FULLTEXT INDEX social_rel_fulltext IF NOT EXISTS
FOR (sr:SocialRelationship) ON EACH [sr.name, sr.description];

CREATE FULLTEXT INDEX character_stoff_fulltext IF NOT EXISTS
FOR (cs:CharacterStoff) ON EACH [cs.canonical_name, cs.description];

CREATE FULLTEXT INDEX narrative_stoff_fulltext IF NOT EXISTS
FOR (ns:NarrativeStoff) ON EACH [ns.name, ns.description];

// Cross-label entity search (Graph Explorer + RAG fulltext retrieval)
// CRITICAL: Must include ALL entity labels for RAG to find them
DROP INDEX entity_fulltext IF EXISTS;
CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS
FOR (n:Character|Skill|Class|Title|Event|Location|Object|Creature|Faction|Concept
     |Setting|SocialRelationship|NarrativeSequence|PsychologicalState|CharacterFeature
     |NarrativeRole|CharacterStoff|NarrativeStoff|Prophecy)
ON EACH [n.name, n.description];

// Compound index for embedding pipeline write-back
CREATE INDEX chunk_chapter_position IF NOT EXISTS
FOR (c:Chunk) ON (c.chapter_id, c.position);

// === VECTOR INDEXES ===
// BGE-m3 / Voyage AI embeddings (1024 dimensions)

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

// Per-label entity vector indexes (Neo4j 5.x requires one per label)
CREATE VECTOR INDEX character_embedding IF NOT EXISTS
FOR (n:Character) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX skill_embedding IF NOT EXISTS
FOR (n:Skill) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX location_embedding IF NOT EXISTS
FOR (n:Location) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX event_embedding IF NOT EXISTS
FOR (n:Event) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX object_embedding IF NOT EXISTS
FOR (n:Object) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX creature_embedding IF NOT EXISTS
FOR (n:Creature) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX concept_embedding IF NOT EXISTS
FOR (n:Concept) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX faction_embedding IF NOT EXISTS
FOR (n:Faction) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

// New GOLEM type embeddings (Setting, SocialRelationship — standalone with rich descriptions)
// NOTE: PsychologicalState, NarrativeRole, CharacterFeature excluded per CDC decision #5
CREATE VECTOR INDEX setting_embedding IF NOT EXISTS
FOR (n:Setting) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX social_rel_embedding IF NOT EXISTS
FOR (n:SocialRelationship) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX character_stoff_embedding IF NOT EXISTS
FOR (n:CharacterStoff) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX narrative_stoff_embedding IF NOT EXISTS
FOR (n:NarrativeStoff) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1024, `vector.similarity_function`: 'cosine'}};

// === RELATIONSHIP INDEXES ===
// Temporal indexes for point-in-time queries

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

CREATE INDEX rel_involved_in_temporal IF NOT EXISTS
FOR ()-[r:INVOLVED_IN]-() ON (r.valid_from_chapter);

CREATE INDEX rel_member_of_temporal IF NOT EXISTS
FOR ()-[r:MEMBER_OF]-() ON (r.valid_from_chapter);

CREATE INDEX rel_has_class_valid_to IF NOT EXISTS
FOR ()-[r:HAS_CLASS]-() ON (r.valid_to_chapter);

CREATE INDEX rel_has_skill_valid_to IF NOT EXISTS
FOR ()-[r:HAS_SKILL]-() ON (r.valid_to_chapter);

CREATE INDEX rel_at_level_valid_to IF NOT EXISTS
FOR ()-[r:AT_LEVEL]-() ON (r.valid_to_chapter);

CREATE INDEX rel_mentioned_in IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.char_start);

CREATE INDEX rel_mentioned_in_type IF NOT EXISTS
FOR ()-[r:MENTIONED_IN]-() ON (r.mention_type);

// === VERIFICATION ===
// Run: SHOW CONSTRAINTS;
// Run: SHOW INDEXES;
