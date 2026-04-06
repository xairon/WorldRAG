# Cahier des charges v2 : Refonte Frontend GOLEM

> **Version** : 2.0 — audit complet + data flows + interactions + accessibilité  
> **Date** : 2026-04-06  
> **Contexte** : Backend GOLEM v1.1 complet (24 types, 30+ relations, 12-step post-processing, MINE benchmark). Frontend nettoyé (-1201 lignes dead code, 4 bugs fixés). Ce CDC couvre la refonte complète.

---

## 1. Inventaire actuel post-cleanup

### 1.1 Pages (9 routes)

| Route | Type | Status | Issues |
|-------|------|--------|--------|
| `/` | Server | OK | — |
| `/projects/[slug]` | Server | OK | — |
| `/projects/[slug]/books/[bookId]` | Server | Missing `loading.tsx` |
| `/projects/[slug]/books/[bookId]/extraction` | Client | OK (5 steps) |
| `/projects/[slug]/graph` | Client | Multi-label fixed, filteredGraph stub still in container |
| `/projects/[slug]/chat` | Client | Thread ID not persisted, spoiler duplicated, no mobile threads |
| `/projects/[slug]/ontology` | Client | OK (GOLEM categories) |
| `/projects/[slug]/books/[bookId]/reader/[ch]` | Server | Missing `loading.tsx` |
| `/projects/[slug]/settings` | Server | OK |

### 1.2 Composants vivants (54)

| Domaine | Count | Key components |
|---------|-------|---------------|
| Layout | 6 | app-sidebar, top-bar, mobile-drawer, sidebar-* |
| Graph | 5 | graph-container, graph-canvas, graph-detail-panel, graph-toolbar, graph-legend |
| Chat | 8 | chat-message, chat-input, chat-header, thread-sidebar, source-panel, citation-highlight, confidence-badge, feedback-buttons, spoiler-guard |
| Extraction | 7 | pipeline-layout, step-indicator, 5 step components |
| Ontology | 5 | ontology-page-content, stat-cards, schema-graph, entity-type-table, relation-type-table |
| Books/Library | 4 | book-grid, book-card, upload-card, book-detail-* |
| Reader | 3 | epub-renderer, reader-nav, reader-progress |
| Shared | 5 | entity-badge (23 GOLEM icons), empty-state, error-boundary, status-badge, theme-toggle |
| UI primitives | 21 | shadcn/ui standard set + confidence-bar, error-state, sse-indicator |

### 1.3 Hooks (17)

| Hook | Endpoint | Used |
|------|----------|------|
| `useChatStream` | SSE /chat/stream | Yes |
| `useBooks` | GET /projects/{slug}/books | Yes |
| `useBookDetail` | GET /books/{bookId} | Yes |
| `useBookStats` | GET /books/{bookId}/stats | Yes |
| `useBookJobs` | GET /books/{bookId}/jobs | **No** (defined, never imported) |
| `useExtractionSSE` | EventSource /stream/extraction | Yes |
| `useTriggerExtraction` | POST /books/{bookId}/extract/v4 | Yes |
| `useRetryChapter` | POST /admin/dlq/retry | Yes |
| `useDLQEntries` | GET /admin/dlq | Yes |
| `useSubgraph` | GET /graph/subgraph/{bookId} | Yes |
| `useNeighbors` | GET /graph/neighbors/{entityId} | Yes |
| `useGraphSearch` | GET /graph/search | Yes |
| `useRenameEntity` | PATCH /graph/entity/{id} | Yes |
| `useDeleteEntity` | DELETE /graph/entity/{id} | Yes |
| `useMergeEntities` | POST /graph/entities/merge | Yes |
| `useDeleteRelation` | DELETE /graph/relationship/{id} | Yes |
| `useOntology` | GET /graph/ontology/{bookId} | Yes |

### 1.4 Stores (2 actifs)

| Store | Persisted | State |
|-------|-----------|-------|
| `chat-store` | localStorage | threadId, threads[], spoilerMaxChapter, selectedBookId |
| `ui-store` | No | mobileSidebarOpen |

### 1.5 Backend endpoints sans frontend (16)

| Endpoint | Method | Data | Priority |
|----------|--------|------|----------|
| `/graph/entity/{id}` | GET | Full entity attrs | P0 (entity detail page) |
| `/graph/wiki/{type}/{name}` | GET | Entity wiki with connections | P0 (entity detail) |
| `/graph/neighbors/{id}` | GET | Ego graph | Already hooked, used in graph |
| `/graph/stats` | GET | Node/edge counts | P1 (KG dashboard) |
| `/graph/timeline/{bookId}` | GET | Chronological events | P0 (timeline page) |
| `/graph/characters/{name}` | GET | Profile + skills/classes | P0 (character profile) |
| `/characters/{name}/at/{ch}` | GET | State snapshot at chapter | P0 (character profile) |
| `/characters/{name}/progression` | GET | Progression timeline | P1 (character profile) |
| `/characters/{name}/compare` | GET | Chapter comparison | P2 (character profile) |
| `/characters/{name}/summary` | GET | Tooltip summary | P1 (graph hover) |
| `/admin/costs` | GET | Cost summary | P2 (admin dashboard) |
| `/admin/costs/{bookId}` | GET | Per-book cost | P2 |
| `/admin/quality-checks/{bookId}` | GET | Consistency checks | P1 (KG dashboard) |
| `/admin/dlq/size` | GET | DLQ count | P2 |
| `/admin/dlq/clear` | POST | Clear DLQ | P2 |
| `/admin/dlq/retry-all` | POST | Retry all | P2 |

---

## 2. Bugs restants à fixer

### 2.1 CRITICAL

**B1. Thread ID jamais persisté côté chat**

Le backend retourne un `thread_id` dans la réponse SSE `done`, mais `use-chat-stream.ts` ne le capture pas. `useChatStore.setThreadId()` n'est jamais appelé après une conversation. Résultat : les threads existent dans le sidebar mais le `thread_id` passé au backend est toujours null.

**Fix** : Dans `use-chat-stream.ts`, extraire `thread_id` du SSE `done` event et appeler `useChatStore.getState().setThreadId(id)`.

**B2. filteredGraph stub dans graph-container.tsx**

Le `filteredGraph` memo (lignes 271-274) retourne toujours `graph` inchangé. Le nodeReducer dans `graph-canvas.tsx` a été fixé pour filtrer via `hidden=true`, mais le `filteredGraph` memo est maintenant du code mort qui ajoute de la confusion.

**Fix** : Supprimer le `filteredGraph` memo, passer `graph` directement à `GraphCanvas`.

### 2.2 WARNING

**B3. Spoiler controls dupliqués dans Chat**

`ChatHeader` rend un `<Select>` de chapitres pour le spoiler cap. `chat/page.tsx` rend aussi `<SpoilerGuard>` avec un Slider. Les deux écrivent dans `useChatStore.spoilerMaxChapter`. L'utilisateur voit 2 contrôles pour la même chose.

**Fix** : Supprimer le Select dans `ChatHeader`. Garder `SpoilerGuard` (plus riche : slider + toggle).

**B4. ThreadSidebar invisible sur mobile**

`hidden xl:block` — aucun accès aux threads sous 1280px.

**Fix** : Ajouter un `Sheet` (mobile drawer) déclenché par un bouton dans `ChatHeader` sur les petits écrans.

**B5. `graph-detail-panel.tsx` prop `bookId` inutilisée**

Préfixée `_bookId` — dead prop.

**Fix** : Supprimer de l'interface et du caller.

**B6. `useBookJobs` hook jamais utilisé**

Défini dans `use-books.ts`, exporté, jamais importé.

**Fix** : Supprimer ou utiliser dans l'extraction page pour polling status.

**B7. ErrorBoundary jamais montée**

Définie dans `shared/error-boundary.tsx`, jamais placée dans un layout.

**Fix** : Monter dans `app/projects/[slug]/layout.tsx` autour du `{children}`.

---

## 3. Nouvelles pages

### 3.1 Character Profile

**Route** : `/projects/[slug]/characters/[name]`

**Endpoints backend** :
- `GET /graph/characters/{name}?book_id=` → CharacterProfile (skills, classes, titles, relationships, events)
- `GET /characters/{name}/at/{chapter}?book_id=` → State snapshot à un chapitre
- `GET /characters/{name}/progression?book_id=` → Timeline de progression

**Hooks à créer** :
```typescript
// hooks/use-character.ts
function useCharacterProfile(name: string, bookId: string): UseQueryResult<CharacterProfile>
function useCharacterAt(name: string, chapter: number, bookId: string): UseQueryResult<CharacterSnapshot>
function useCharacterProgression(name: string, bookId: string): UseQueryResult<ProgressionEntry[]>
```

**Nouveau endpoint backend à créer** :
```
GET /graph/characters/{name}/psychology?book_id=
→ { states: PsychologicalState[], features: CharacterFeature[], roles: NarrativeRole[] }
```
Ce endpoint agrège les 3 types GOLEM liés au personnage. Cypher :
```cypher
MATCH (c:Character {canonical_name: $name, book_id: $book_id})
OPTIONAL MATCH (c)-[:HAS_STATE]->(ps:PsychologicalState)
OPTIONAL MATCH (c)-[:HAS_FEATURE]->(cf:CharacterFeature)  
OPTIONAL MATCH (c)-[:PLAYS_ROLE]->(nr:NarrativeRole)
OPTIONAL MATCH (c)-[:INVOLVED_IN]->(sr:SocialRelationship)<-[:INVOLVED_IN]-(other:Character)
RETURN c, collect(DISTINCT ps) AS states, collect(DISTINCT cf) AS features,
       collect(DISTINCT nr) AS roles, collect(DISTINCT {sr: sr, other: other}) AS relationships
```

**Hook** :
```typescript
function useCharacterPsychology(name: string, bookId: string): UseQueryResult<{
  states: { name: string, state_type: string, chapter_start: number, intensity: number, trigger_event?: string }[]
  features: { name: string, feature_type: string, valid_from_chapter: number }[]
  roles: { role_type: string, context: string, valid_from_chapter: number }[]
  relationships: { name: string, type: string, other_character: string, from_chapter: number }[]
}>
```

**Layout de la page** (desktop, 1280px+) :

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Graph    Character: Jake Thayne          Ch.1 → Ch.76│
│ agency: active | species: Human | first: Ch.1                  │
├──────────────────────────────┬──────────────────────────────────┤
│                              │                                  │
│  📊 Emotional Arc            │  🔗 Relationships                │
│  (recharts AreaChart)        │  ┌──────────────────────┐       │
│  x=chapter, y=intensity      │  │ jake-casper friendship│       │
│  color=state_type            │  │ friendship, ch.3-     │       │
│  hover=name+trigger          │  └──────────────────────┘       │
│                              │  ┌──────────────────────┐       │
│                              │  │ viper mentorship      │       │
│                              │  │ mentorship, ch.15-    │       │
│                              │  └──────────────────────┘       │
├──────────────────────────────┼──────────────────────────────────┤
│                              │                                  │
│  🏷️ Character Features       │  🎭 Narrative Roles              │
│  ┌─────────────────────┐    │  ch.1-30: protagonist            │
│  │ biographical         │    │  ch.31-50: mentor (for Miranda)  │
│  │ • human (ch.1)      │    │  ch.51+: anti-hero               │
│  │ • new haven (ch.1)  │    │                                  │
│  ├─────────────────────┤    │  ⚔️ Skills & Progression          │
│  │ physical             │    │  (table: name, type, rank, ch)   │
│  │ • green eyes (ch.1) │    │                                  │
│  ├─────────────────────┤    │                                  │
│  │ psychological        │    │                                  │
│  │ • loner (ch.1-20)   │    │                                  │
│  └─────────────────────┘    │                                  │
└──────────────────────────────┴──────────────────────────────────┘
```

**Mobile** (< 768px) : Stack vertical, tabs pour switch entre sections.

**Composants** :
```
components/characters/
  character-page-content.tsx    — orchestrator (fetches, tabs mobile, grid desktop)
  character-header.tsx          — name, agency, species, description, badges
  emotional-arc-chart.tsx       — recharts AreaChart, x=chapter, y=intensity, color=state_type
  feature-group.tsx             — grouped badges par feature_type avec valid_from_chapter
  relationship-card.tsx         — SR card avec participants, type, timeline bar
  role-timeline.tsx             — horizontal timeline des NarrativeRole
  skill-table.tsx               — sortable table (name, type, rank, acquired_chapter)
```

**Interactions** :
- Click sur un PsychologicalState dans le chart → highlight + show trigger_event
- Click sur un SocialRelationship card → navigate to other character's profile
- Click sur un NarrativeRole → navigate to NarrativeSequence in graph
- Slider "Chapter cap" → filter tous les éléments par valid_from_chapter
- Toggle "Cross-book comparison" (si CharacterStoff exists) → side-by-side books

**Accessibilité** :
- AreaChart : `role="img"`, `aria-label="Emotional arc for {name}"`
- Feature badges : `role="list"`, keyboard navigable
- All interactive cards : `role="button"`, `tabIndex=0`, `onKeyDown` enter/space

### 3.2 Timeline

**Route** : `/projects/[slug]/timeline`

**Endpoint** : `GET /graph/timeline/{bookId}` → `TimelineEvent[]` (existe, non-utilisé)

**Hook** :
```typescript
// hooks/use-timeline.ts
function useTimeline(bookId: string): UseQueryResult<TimelineEvent[]>
```

**Layout** :

```
┌────────────────────────────────────────────────────────┐
│ Timeline: The Primal Hunter       [book selector] 🔍   │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Ch.1 ─┬── Tutorial Begins (action, major) ●●●        │
│         │   participants: jake, system                 │
│         └── First Kill (combat, moderate) ●●           │
│              participants: jake                        │
│                                                        │
│  Ch.2 ─┬── Jake Meets Casper (encounter, moderate) ●● │
│         │   participants: jake, casper                 │
│         └── System Integration (revelation, major) ●●● │
│                                                        │
│  ══════ Tutorial Arc ══════════════════════════════     │
│                                                        │
│  Ch.3 ─── Arena Battle (combat, critical) ●●●●        │
│            participants: jake, casper, richard          │
│                                                        │
│  ...                                                   │
└────────────────────────────────────────────────────────┘
```

**Composants** :
```
components/timeline/
  timeline-page-content.tsx     — fetches, filters, scroll container
  timeline-event-card.tsx       — event with significance dots, participants
  sequence-lane.tsx             — NarrativeSequence swim lane overlay
  timeline-filters.tsx          — event_category filter, significance filter, chapter range
```

**Interactions** :
- Click event → expand details (description, trigger PsychologicalStates)
- Click participant → navigate to character profile
- Filter by event_category (checkboxes)
- Filter by significance (min slider)
- NarrativeSequence swim lanes : toggle visibility

### 3.3 Entity Detail

**Route** : `/projects/[slug]/entity/[id]`

**Endpoints** :
- `GET /graph/entity/{id}` → full node attributes
- `GET /graph/neighbors/{id}?depth=1&limit=50` → ego graph

**Hook** :
```typescript
// hooks/use-entity.ts
function useEntity(entityId: string): UseQueryResult<GraphNode & { properties: Record<string, unknown> }>
function useEntityNeighbors(entityId: string): UseQueryResult<SubgraphData>
```

**Layout** :
```
┌────────────────────────────────────────────────────────┐
│ ← Back    [EntityBadge: PsychologicalState]            │
│ "determination"                                        │
├─────────────────────────┬──────────────────────────────┤
│ Attributes              │ Mini Graph (Sigma.js)        │
│ state_type: emotion     │ ┌────────────────────────┐  │
│ character: jake         │ │    ●──HAS_STATE──●     │  │
│ intensity: 0.9          │ │    jake    determination│  │
│ chapter_start: 15       │ │         ──TRIGGERED──● │  │
│ trigger_event: ...      │ │              arena battle│  │
│                         │ └────────────────────────┘  │
├─────────────────────────┴──────────────────────────────┤
│ Relationships (grouped by type)                        │
│ ← HAS_STATE ← jake (Character)                        │
│ → STATE_TRIGGERED_BY → arena battle (Event)            │
│ → FOLLOWS_STATE → fear (PsychologicalState)            │
├────────────────────────────────────────────────────────┤
│ Source Passages (GROUNDED_IN)                          │
│ Ch.15: "Jake felt a surge of determination as..."      │
└────────────────────────────────────────────────────────┘
```

### 3.4 KG Dashboard

**Route** : `/projects/[slug]/kg-stats`

**Endpoints** :
- `GET /graph/stats` → GraphStats
- `GET /admin/quality-checks/{bookId}` → consistency check results

**Hook** :
```typescript
// hooks/use-kg-stats.ts
function useGraphStats(bookId?: string): UseQueryResult<GraphStats>
function useQualityChecks(bookId: string): UseQueryResult<QualityCheck[]>
```

**Layout** :
```
┌────────────────────────────────────────────────────────┐
│ Knowledge Graph Health        [book selector]          │
├────────────┬────────────┬────────────┬─────────────────┤
│ 10,355     │ 16,847     │ 24         │ MINE: 72%      │
│ nodes      │ edges      │ types      │ score          │
├────────────┴────────────┴────────────┴─────────────────┤
│                                                        │
│ Entity Distribution (recharts PieChart)                 │
│ [donut chart with GOLEM colors]                        │
│                                                        │
├────────────────────────────────────────────────────────┤
│ GOLEM Edge Coverage                                    │
│ HAS_STATE           ████████████████████░ 941          │
│ HAS_FEATURE         ██████████████░░░░░░ 447          │
│ FOLLOWS_STATE       ████░░░░░░░░░░░░░░░  15          │
│ ROLE_IN_SEQUENCE    ░░░░░░░░░░░░░░░░░░░   0  ⚠️     │
│ ...                                                    │
├────────────────────────────────────────────────────────┤
│ Quality Issues                                         │
│ ⚠️ 52 orphan PsychologicalState nodes                 │
│ ⚠️ 36 orphan CharacterFeature nodes                   │
│ ✅ 0 invalid SocialRelationships                      │
│ ✅ 0 UNKNOWN edges                                    │
└────────────────────────────────────────────────────────┘
```

---

## 4. Refactoring transversal

### 4.1 Shared utilities à créer

**`lib/utils/format-book-title.ts`** :
```typescript
export function formatBookTitle(raw: string): string {
  return raw.replace(/\.(epub|pdf|txt)$/i, "").replace(/ -- .*/g, "")
}
```
Remplace 4 duplications : `SidebarBookItem`, `BookCard`, `BooksTable` (deleted), `ProjectLayout`.

**`lib/utils/normalize-book.ts`** :
```typescript
export function normalizeBookId(book: { id?: string; book_id?: string }): string {
  return book.book_id ?? book.id ?? ""
}
```
Remplace 5 duplications : chat page, graph page, ontology page, project layout, sidebar.

**`hooks/use-upload-book.ts`** :
```typescript
export function useUploadBook(slug: string) {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append("file", file)
      form.append("book_num", "1")
      return apiFetch(`/projects/${slug}/books`, { method: "POST", body: form })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["books", slug] }),
  })
}
```
Centralise upload-card + upload-step.

### 4.2 Error boundaries

```typescript
// app/projects/[slug]/layout.tsx
<ErrorBoundary fallback={<ErrorState message="Something went wrong" />}>
  {children}
</ErrorBoundary>
```

### 4.3 Loading states

Créer `loading.tsx` dans :
- `app/projects/[slug]/books/[bookId]/loading.tsx`
- `app/projects/[slug]/books/[bookId]/reader/[chapterNumber]/loading.tsx`

---

## 5. Améliorations pages existantes

### 5.1 Graph Explorer

**SocialRelationship comme noeud intermédiaire** :
Dans le `nodeReducer`, détecter `entityType === "SocialRelationship"` et rendre avec :
- Taille réduite (`size * 0.6`)
- Forme diamant (via `type: "diamond"` si Sigma le supporte, sinon shape override)
- Opacité réduite quand pas hovered

**Supprimer filteredGraph stub** :
```diff
- const filteredGraph = useMemo(() => {
-   if (!graph || activeLabels.length === 0) return graph
-   return graph
- }, [graph, activeLabels])
...
- graph={filteredGraph}
+ graph={graph}
```

### 5.2 Chat

**Thread ID persistence** :
```typescript
// use-chat-stream.ts, dans le handler SSE "done"
if (event.type === "done" && event.data?.thread_id) {
  useChatStore.getState().setThreadId(event.data.thread_id)
}
```

**Supprimer spoiler Select dupliqué** dans `ChatHeader` — garder `SpoilerGuard`.

**Mobile thread drawer** :
```typescript
// chat-header.tsx
<Sheet>
  <SheetTrigger asChild>
    <Button variant="ghost" size="icon" className="xl:hidden">
      <MessageSquare className="h-4 w-4" />
    </Button>
  </SheetTrigger>
  <SheetContent side="left">
    <ThreadSidebar />
  </SheetContent>
</Sheet>
```

### 5.3 Extraction Review

Ajouter groupement GOLEM dans `EntityReviewTable` (réutiliser le pattern de `EntityTypeTable.groupByCategory`).

Recréer un donut chart léger (recharts `PieChart`) dans la review step pour visualiser la distribution des types extraits.

---

## 6. Navigation globale

Ajouter au sidebar (`sidebar-project-nav.tsx`) :

```typescript
const NAV_ITEMS = [
  { href: "graph", icon: Network, label: "Graph Explorer" },
  { href: "timeline", icon: Calendar, label: "Timeline" },       // NEW
  { href: "chat", icon: MessageSquare, label: "Chat" },
  { href: "ontology", icon: Layers, label: "Ontology" },
  { href: "kg-stats", icon: BarChart3, label: "KG Health" },     // NEW
  { href: "settings", icon: Settings, label: "Settings" },
]
```

Character Profile n'est pas dans le nav — on y accède via click sur un Character dans le graph/chat/timeline.

---

## 7. Types TypeScript à ajouter

```typescript
// lib/api/types.ts — additions

interface CharacterPsychology {
  states: PsychologicalStateEntry[]
  features: CharacterFeatureEntry[]
  roles: NarrativeRoleEntry[]
  relationships: SocialRelationshipEntry[]
}

interface PsychologicalStateEntry {
  name: string
  state_type: "emotion" | "motivation" | "belief" | "goal" | "fear"
  chapter_start: number
  chapter_end?: number
  intensity: number
  description?: string
  trigger_event?: string
}

interface CharacterFeatureEntry {
  name: string
  feature_type: "biographical" | "physical" | "psychological"
  valid_from_chapter: number
  valid_to_chapter?: number
  description?: string
}

interface NarrativeRoleEntry {
  role_type: string
  context?: string
  valid_from_chapter: number
  valid_to_chapter?: number
}

interface SocialRelationshipEntry {
  name: string
  relationship_type: string
  other_character: string
  valid_from_chapter: number
  valid_to_chapter?: number
  description?: string
}

interface QualityCheck {
  check: string
  count: number
  severity: "ok" | "warning" | "critical"
}

interface MINEResult {
  score: number
  chapters_evaluated: number
  total_facts: number
  total_inferable: number
  per_chapter: { chapter: number, facts: number, inferable: number, score: number }[]
}
```

---

## 8. Plan d'implémentation

### Phase 1 : Fondations + Bug fixes (1 jour)
- Fix B1-B7 (thread ID, filteredGraph, spoiler, mobile, error boundary, loading states)
- Créer shared utils (format-book-title, normalize-book, use-upload-book)
- Ajouter loading.tsx manquants
- Monter ErrorBoundary

### Phase 2 : Character Profile (3 jours)
- Nouveau endpoint backend `/graph/characters/{name}/psychology`
- Hook `useCharacterPsychology`
- 7 composants : header, emotional-arc-chart, feature-group, relationship-card, role-timeline, skill-table, page-content
- Page route + layout
- Tests Playwright (2 scénarios)

### Phase 3 : Timeline + Entity Detail (2 jours)
- Hook `useTimeline` + `useEntity`
- 4 composants timeline + 3 composants entity detail
- Mini Sigma.js dans entity detail (réutilise GraphCanvas avec props subset)
- Navigation sidebar mise à jour

### Phase 4 : KG Dashboard (1 jour)
- Hook `useGraphStats` + `useQualityChecks`
- 4 composants : stats cards, entity distribution donut, edge coverage bars, quality issues list
- Navigation sidebar

### Phase 5 : Polish existant (2 jours)
- Graph : SocialRelationship diamond nodes, Setting visual clusters
- Chat : mobile thread drawer, extraction review GOLEM grouping
- Donut chart recréé pour extraction review
- Responsive polish sur toutes les nouvelles pages

**Total : 9 jours, 5 phases**

---

## 9. Stack & conventions

| Aspect | Choix | Justification |
|--------|-------|---------------|
| Data fetching | TanStack React Query v5 | Déjà en place, hooks pattern |
| State | Zustand (chat store) + nuqs (URL) | Déjà en place |
| Charts | recharts v3 | Déjà en place, AreaChart + PieChart suffisent |
| Graph | Sigma.js 3 + graphology | Déjà en place, réutiliser GraphCanvas |
| UI | shadcn/ui + Tailwind v4 | Déjà en place |
| Animations | motion (Framer v12) | Déjà en place, page transitions |
| Icons | lucide-react | Déjà en place, 23 GOLEM entity icons |
| Testing | Playwright | Installé mais aucun test — à créer |
