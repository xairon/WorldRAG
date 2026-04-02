# Ontology Viewer Redesign — Sub-project 3

## Goal

Rewrite the ontology viewer with TanStack Query data fetching, a polished SVG schema graph (circular layout by layer, motion animations, click-to-filter), book selector for multi-book, and proper loading/error/empty states.

## Architecture

### Data Flow

- TanStack Query hook `useOntology(bookId)` wraps `GET /graph/ontology/{book_id}`
- Book selection via `useBooks(slug)` (already exists) + URL state via nuqs
- Schema graph and tables share the same `OntologyData` from the query
- Click a node in the schema graph → filters both tables to show only that entity type's relations

### Components (all < 150L)

```
components/ontology/
  ontology-page-content.tsx    # Orchestrator: book selector, query, layout
  schema-graph.tsx             # Rewritten: circular layout, motion animations, click-to-filter
  entity-type-table.tsx        # Kept, cleaned up (extract ConfidenceBar, use shared one)
  relation-type-table.tsx      # Kept, minor cleanup
  stat-cards.tsx               # Kept as-is (already good)
```

### Schema Graph Redesign

Replace 200-iteration O(n²) force simulation with **deterministic circular layout by layer**:

- **Core types** (Character, Event, Location, etc.) — inner circle, larger nodes
- **Genre types** (Skill, Class, Title, etc.) — middle ring
- **Induced types** — outer ring, smaller nodes, dashed border

Benefits: instant render (no simulation), deterministic (same data = same layout), responsive.

**Interactions:**
- Hover a node → highlight connected edges, dim unconnected nodes (like current, but smoother with motion)
- Click a node → set `selectedType` state → filters tables below to show only relations involving that type
- Click background → clear filter

**Visual polish:**
- Gradient edges (source color → target color)
- Glow filter on nodes (keep from current, it's nice)
- Count label inside each node circle
- Animated entrance (nodes fade in with stagger)

### No Backend Changes

`GET /graph/ontology/{book_id}` already returns everything needed.

---

## Files Created / Modified / Deleted

| Action | File | Change |
|--------|------|--------|
| Create | `frontend/hooks/use-ontology.ts` | TanStack Query hook |
| Rewrite | `frontend/components/ontology/ontology-page-content.tsx` | New orchestrator (replaces ontology-dashboard.tsx) |
| Rewrite | `frontend/components/ontology/schema-graph.tsx` | Circular layout, motion, click-to-filter |
| Modify | `frontend/components/ontology/entity-type-table.tsx` | Use shared ConfidenceBar, accept filter prop |
| Modify | `frontend/components/ontology/relation-type-table.tsx` | Accept filter prop |
| Keep | `frontend/components/ontology/stat-cards.tsx` | No changes |
| Modify | `frontend/app/projects/[slug]/ontology/page.tsx` | Use new orchestrator |
| Delete | `frontend/components/ontology/ontology-dashboard.tsx` | Replaced by ontology-page-content.tsx |
