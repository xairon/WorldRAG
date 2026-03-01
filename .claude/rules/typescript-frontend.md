---
paths:
  - "frontend/**"
---

# TypeScript Frontend Rules

## Framework
- Next.js 16 with App Router (not Pages Router)
- React 19 with Server Components by default
- TypeScript strict mode

## Components
- Server Components by default, add 'use client' only when needed (state, effects, browser APIs)
- shadcn/ui for base components
- Tailwind CSS for styling (no CSS modules, no styled-components)

## Data Fetching
- Server Components: fetch directly in component
- Client Components: custom hooks in `hooks/` (e.g. use-chat-stream, use-extraction-progress)
- API client in `lib/api.ts` (typed, centralized), types in `lib/api/types.ts`

## State Management
- Zustand for global client state (stores in `stores/`: book-store, graph-store, ui-store)
- URL params for shareable state (search, filters)
- React state for local UI state

## Graph Visualization
- Sigma.js 3.0 + graphology for the graph explorer (not D3)
- ForceAtlas2 layout via graphology-layout-forceatlas2
- Graph components in `components/graph/`

## Types
- API types in `lib/api/types.ts` (synced with backend Pydantic models)
- No `any` — use `unknown` and narrow with type guards
- Discriminated unions for component variants

## Route Groups
- `(explorer)`: graph, search, characters, entity, timeline
- `(pipeline)`: extraction pipeline management
- `(reader)`: chat, library, read
