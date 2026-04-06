# Cahier des charges : Frontend GOLEM — Nouvelles pages & refonte UI

> **Version** : 1.0  
> **Date** : 2026-04-06  
> **Contexte** : Le backend GOLEM v1.1 est complet (24 node types, 30+ relations, 12-step post-processing, MINE benchmark). Le frontend doit exploiter ces données.

---

## 1. État actuel

### Pages existantes
| Page | Route | Status |
|------|-------|--------|
| Dashboard (Projects) | `/` | OK |
| Library | `/projects/[slug]` | OK |
| Book Detail | `/projects/[slug]/books/[bookId]` | OK |
| Extraction Pipeline | `/projects/[slug]/books/[bookId]/extraction` | OK (5 steps) |
| Graph Explorer | `/projects/[slug]/graph` | OK (multi-label fix done) |
| Chat RAG | `/projects/[slug]/chat` | OK (8 routes incl. psychological_qa) |
| Ontology Viewer | `/projects/[slug]/ontology` | OK (GOLEM categories) |
| Reader | `/projects/[slug]/books/[bookId]/reader/[ch]` | OK (EPUB) |
| Settings | `/projects/[slug]/settings` | OK |

### Pages manquantes (backend prêt, pas de frontend)
| Page | Backend endpoint | Data disponible |
|------|-----------------|-----------------|
| **Character Profile** | `GET /graph/characters/{name}` | Skills, classes, titles, relationships, stats progression |
| **Timeline** | `GET /graph/timeline/{bookId}` | Events chronologiques avec participants |
| **Entity Detail** | `GET /graph/neighbors/{id}` | Voisinage 2-hop, attributs, relations |
| **KG Stats / Admin** | `GET /graph/stats` | Node counts, edge counts, entity distribution |
| **MINE Benchmark** | `scripts/evaluate_kg.py` | Score per-chapter, facts, inferability |

---

## 2. Nouvelles pages à créer

### 2.1 Character Profile (`/projects/[slug]/characters/[name]`)

**Données GOLEM exploitées** : PsychologicalState chains, CharacterFeature timeline, NarrativeRole evolution, SocialRelationship graph, CharacterStoff cross-book.

**Sections** :
1. **Header** : nom, agency, species, description, first appearance
2. **Emotional Arc** : Timeline chart (recharts AreaChart) des PsychologicalState par chapitre, couleur par state_type (emotion=red, belief=blue, motivation=green, goal=purple, fear=orange)
3. **Character Features** : Grouped badges (biographical / physical / psychological) avec valid_from_chapter
4. **Relationships** : SocialRelationship cards avec participants, type, evolution timeline
5. **Narrative Roles** : Timeline des rôles (protagonist ch.1-30, mentor ch.31-50...)
6. **Skills & Progression** : Table des skills/classes/titles avec acquisition chapter (données LitRPG existantes)
7. **Cross-Book** (si CharacterStoff) : Comparaison features/roles entre books

**API** : `GET /graph/characters/{name}` (existe) + nouveau `GET /graph/characters/{name}/psychology?book_id=` pour les PsychologicalState chains.

**Composants** :
- `components/characters/character-header.tsx`
- `components/characters/emotional-arc-chart.tsx` (recharts)
- `components/characters/feature-timeline.tsx`
- `components/characters/relationship-cards.tsx`
- `components/characters/role-timeline.tsx`

### 2.2 Timeline (`/projects/[slug]/timeline`)

**Données GOLEM exploitées** : Event.event_category, PRECEDES/FOLLOWS chains, SEQUENCED_IN → NarrativeSequence, significance scale.

**Design** : Vue verticale (scroll) avec :
1. Axe vertical = chapitres
2. Events positionnés par chapter_start, taille par significance
3. Couleur par event_category
4. NarrativeSequences comme "swim lanes" latéraux
5. Hover : description, participants, trigger PsychologicalStates

**API** : `GET /graph/timeline/{bookId}` (existe).

**Composants** :
- `components/timeline/timeline-view.tsx` (main layout)
- `components/timeline/event-card.tsx`
- `components/timeline/sequence-lane.tsx`

### 2.3 Entity Detail (`/projects/[slug]/entity/[id]`)

**Design** : Page générique pour n'importe quel type d'entité. Affiche :
1. Attributs du noeud (toutes les props Neo4j)
2. Relations (groupées par type, avec direction)
3. Mini sous-graphe Sigma.js centré sur cette entité (1-hop)
4. Chunks source (GROUNDED_IN / MENTIONED_IN)

**API** : `GET /graph/neighbors/{id}` (existe) + `GET /graph/entity/{id}` (à créer côté backend).

### 2.4 KG Dashboard (`/projects/[slug]/kg-stats`)

**Design** : Vue admin du Knowledge Graph :
1. **Stats cards** : total nodes, total edges, entity type distribution (donut chart)
2. **GOLEM coverage** : quels edge types ont 0 instances (health check)
3. **Quality metrics** : orphan count, hallucinated edges count
4. **MINE score** (si disponible) : score global + per-chapter breakdown

**API** : `GET /graph/stats` (existe, non-utilisé).

---

## 3. Améliorations pages existantes

### 3.1 Graph Explorer

- **SocialRelationship comme noeud intermédiaire** : Les SR nodes doivent apparaître dans le graphe avec un style distinct (plus petit, diamant shape via nodeReducer)
- **Setting clusters** : Settings comme overlay ou container visuel regroupant les entités IN_SETTING
- **PsychologicalState chains** : Option de vue "emotional arc" superposée au graphe (timeline overlay)

### 3.2 Chat

- **Thread persistence backend** : Sauver les threads côté serveur, pas localStorage
- **Spoiler controls** : Fusionner les 2 contrôles redondants (ChatHeader Select + SpoilerGuard Slider)
- **Mobile thread access** : Drawer sheet pour le thread sidebar sur mobile

### 3.3 Extraction Review

- **GOLEM entity grouping** : Grouper les entités par catégorie GOLEM dans la review table (comme l'ontology viewer)
- **Entity donut** : Remettre le donut chart (supprimé comme dead code mais utile dans la review step)

---

## 4. Tech improvements

### 4.1 Shared utilities à créer
- `lib/utils/format-book-title.ts` — centraliser `.replace(/\.(epub|pdf|txt)$/i, "")` (dupliqué 4x)
- `lib/utils/normalize-book.ts` — centraliser `b.book_id ?? b.id` (dupliqué 5x)
- `hooks/use-upload-book.ts` — mutation React Query pour upload (dupliqué upload-card + upload-step)

### 4.2 Error boundaries
- Monter `ErrorBoundary` dans le layout principal
- Ajouter recovery UI dans le graph canvas (Sigma crash)

### 4.3 Loading states
- `loading.tsx` pour `/reader/[ch]` et `/books/[bookId]`

---

## 5. Plan d'implémentation

### Phase 1 : Character Profile (3 jours)
Le plus impactant — exploite 5 types GOLEM et donne une vue unique sur les personnages.

### Phase 2 : Timeline + Entity Detail (2 jours)
Exploite les Event chains et NarrativeSequence.

### Phase 3 : KG Dashboard + améliorations existantes (2 jours)
MINE scores, graph improvements, shared utils.

### Phase 4 : Chat improvements + polish (2 jours)
Thread persistence, mobile, loading states, error boundaries.

**Total estimé : ~9 jours**
