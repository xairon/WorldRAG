---
paths:
  - "frontend/**"
---

# TypeScript Frontend Rules

## Framework
- Next.js 15 with App Router (not Pages Router)
- React 19 with Server Components by default
- TypeScript strict mode

## Components
- Server Components by default, add 'use client' only when needed (state, effects, browser APIs)
- shadcn/ui for base components
- Tailwind CSS for styling (no CSS modules, no styled-components)

## Data Fetching
- Server Components: fetch directly in component
- Client Components: custom hooks in `lib/hooks/`
- API client in `lib/api.ts` (typed, centralized)

## State Management
- Zustand for global client state (stores in `lib/stores/`)
- URL params for shareable state (search, filters)
- React state for local UI state

## Types
- All API types in `lib/types.ts` (synced with backend Pydantic models)
- No `any` — use `unknown` and narrow with type guards
- Discriminated unions for component variants
