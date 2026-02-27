import { apiFetch } from "./client"

// ── Prompt info ───────────────────────────────────────────────

export interface PromptInfo {
  name: string
  pass_number: string
  description: string
  has_few_shot: boolean
  few_shot_count: number
}

// ── Regex patterns ────────────────────────────────────────────

export interface RegexPatternInfo {
  name: string
  entity_type: string
  pattern: string
  captures: Record<string, number>
  source: string
}

// ── Ontology ──────────────────────────────────────────────────

export interface PropertyInfo {
  name: string
  type: string
  required: boolean
  unique: boolean
  values: string[] | null
}

export interface OntologyNodeType {
  name: string
  layer: string
  properties: PropertyInfo[]
}

export interface OntologyRelType {
  name: string
  from_type: string
  to_type: string
  layer: string
  properties: PropertyInfo[]
}

// ── Extraction graph ──────────────────────────────────────────

export interface ExtractionGraphNode {
  name: string
  description: string
  node_type: string
}

export interface ExtractionGraphEdge {
  source: string
  target: string
  edge_type: string
  label: string
}

export interface ExtractionGraphInfo {
  nodes: ExtractionGraphNode[]
  edges: ExtractionGraphEdge[]
}

// ── Neo4j schema ──────────────────────────────────────────────

export interface ConstraintInfo {
  name: string
  label: string
  properties: string[]
}

export interface IndexInfo {
  name: string
  index_type: string
  label: string
  properties: string[]
}

export interface Neo4jSchemaInfo {
  constraints: ConstraintInfo[]
  indexes: IndexInfo[]
}

// ── Extraction models ─────────────────────────────────────────

export interface FieldInfo {
  name: string
  type: string
  required: boolean
  default: string | null
  description: string
}

export interface ExtractionModelInfo {
  name: string
  pass_name: string
  fields: FieldInfo[]
}

// ── Top-level config ──────────────────────────────────────────

export interface PipelineConfig {
  prompts: PromptInfo[]
  regex_patterns: RegexPatternInfo[]
  ontology_node_types: OntologyNodeType[]
  ontology_rel_types: OntologyRelType[]
  extraction_graph: ExtractionGraphInfo
  neo4j_schema: Neo4jSchemaInfo
  extraction_models: ExtractionModelInfo[]
}

export function getPipelineConfig(): Promise<PipelineConfig> {
  return apiFetch("/pipeline/config")
}
