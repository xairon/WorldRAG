# Glass Morphism Frontend Redesign — "Crystalline Knowledge"

**Date**: 2026-03-01
**Scope**: Dashboard, Graph Explorer, Character Sheet, E-Reader + shared design system
**Approach**: Component-level redesign (Option A — modify in place)

## Design System

### Typography
- **Display/headings**: Outfit (geometric, clean, weights 300-700)
- **Body**: DM Sans (warm, readable, pairs with Outfit)
- **Reader**: Literata (keep existing)
- **Mono**: JetBrains Mono

### Color System (Dual Theme)

**Dark theme:**
- Background: `#0a0e1a` with animated gradient mesh (indigo/violet at 3-5% opacity)
- Glass: `rgba(255,255,255,0.03)` + `backdrop-blur-xl` + `backdrop-saturate-150`
- Borders: `rgba(255,255,255,0.08)`
- Primary: Electric violet `#7c3aed` → Indigo `#6366f1` gradient
- Accents: Cyan `#06b6d4`, Emerald `#10b981`, Amber `#f59e0b`
- Text: `#e2e8f0` primary, `#94a3b8` muted

**Light theme:**
- Background: Warm off-white `#f8f7f4` with subtle grain texture
- Glass: `rgba(255,255,255,0.7)` + `backdrop-blur-lg` + soft shadows
- Borders: `rgba(0,0,0,0.06)`
- Primary: `#6d28d9` → `#4f46e5`
- Text: `#1e1b4b` primary, `#6b7280` muted

### Glass Effect
```css
.glass-dark {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(24px) saturate(1.5);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12),
              inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.glass-light {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px) saturate(1.2);
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06),
              inset 0 1px 0 rgba(255, 255, 255, 0.8);
}
```

### Animations (Motion library)
- Page: staggered fade-up reveals (children delay 50ms)
- Cards: scale(1.01) + glow on hover with spring physics
- Graph nodes: soft radial glow, pulse on idle, ring on select
- Stats: count-up animation on load
- Sidebar: active indicator slides with spring easing
- Tabs: crossfade with directional slide

### Background Effects
- Animated gradient mesh (2-3 color blobs, slow orbit, 3-5% opacity)
- Noise grain overlay (1-2% opacity, mix-blend-mode: overlay)

## Page Designs

### 1. Dashboard — "Mission Control"

**Layout**: Asymmetric bento grid with hero section.

- Hero: large animated stat counters (Nodes / Relationships / Books) on gradient mesh
- Infrastructure: compact inline status dots (not full card)
- Quick Actions: 4 glass cards with icon, label, accent glow on hover
- Books: glass cards with entity-type color bar on left edge
- Staggered entrance animations

### 2. Graph Explorer — "The Observatory"

**Layout**: Full-bleed graph canvas, floating glass panels.

- Graph canvas fills viewport (no padding)
- Filter sidebar: floating collapsible glass panel (left)
- Node detail: slide-in glass panel (right) with spring animation
- Zoom controls: pill-shaped glass bar (bottom center)
- Node glow effects matching entity color
- Selected node pulsing ring
- Dark void gradient background

### 3. Character Sheet — "The Codex"

**Layout**: Full-width header, tabbed glass sections.

- Header: entity-type colored accent glow, character info
- Chapter slider: glass track, glowing thumb, tooltip
- Stats: large monospace numbers with delta indicators (↑↓)
- Tab switching: crossfade with slide direction
- Skills: rank bar visualization (gradient fill)
- Classes: horizontal visual timeline with nodes
- Equipment: rarity colored border glow

### 4. E-Reader — "The Sanctum"

**Layout**: Distraction-free, floating glass toolbar.

- Toolbar auto-hides on scroll down, reappears on scroll up
- Reading themes: Deep Black, Paper Cream, Twilight, Light, Dark
- Annotations: subtle underline + dot (not full bg highlight)
- Annotation sidebar: glass panel slides over content
- Settings: visual theme previews
- Chapter transitions: crossfade
- Reading progress bar at top (thin accent line)

## Shared Changes

### Sidebar
- Glass background instead of solid
- Active nav: glowing pill indicator with spring slide
- Section labels: Outfit font 10px caps

### TopBar
- Glass bar with noise grain
- Search button subtle glow
- Book selector as glass dropdown

### Layout
- ThemeProvider (next-themes) for dual light/dark
- Background gradient mesh component (animated, full-page)

## New Dependencies
- `motion` (Framer Motion v11+) — animations
- `next-themes` — theme switching (already installed)

## Existing Entity Color System
Preserved as-is (LABEL_COLORS, LABEL_BADGE_CLASSES in lib/utils.ts):
- Character=indigo, Skill=emerald, Class=amber, Title=pink
- Event=red, Location=blue, Item=violet, Creature=orange
- Faction=teal, Concept=slate

## Files to Modify

### Design System (foundation)
- `frontend/app/globals.css` — new theme vars, glass utilities, fonts, grain overlay
- `frontend/app/layout.tsx` — ThemeProvider, gradient mesh, font classes
- `frontend/components/ui/card.tsx` — glass card variant
- `frontend/lib/utils.ts` — glass utility helpers

### Shared Components
- `frontend/components/shared/sidebar.tsx` — glass bg, animated active indicator
- `frontend/components/shared/top-bar.tsx` — glass bar, glow search

### New Shared Components
- `frontend/components/shared/gradient-mesh.tsx` — animated background
- `frontend/components/shared/theme-toggle.tsx` — light/dark toggle
- `frontend/components/shared/animated-counter.tsx` — count-up stat animation

### Dashboard
- `frontend/app/page.tsx` — full redesign: hero, bento grid, glass cards

### Graph Explorer
- `frontend/app/(explorer)/graph/page.tsx` — full-bleed layout, floating panels
- `frontend/components/graph/sigma-graph.tsx` — glow effects, void background
- `frontend/components/graph/graph-controls.tsx` — glass floating panel
- `frontend/components/graph/node-detail-panel.tsx` — glass slide-in panel

### Character Sheet
- `frontend/app/(explorer)/characters/page.tsx` — glass character grid
- `frontend/app/(explorer)/characters/[name]/page.tsx` — codex layout
- `frontend/components/characters/character-header.tsx` — glow accent
- `frontend/components/characters/stat-grid.tsx` — monospace deltas
- `frontend/components/characters/skill-list.tsx` — rank bars
- `frontend/components/characters/class-timeline.tsx` — horizontal visual timeline
- `frontend/components/characters/chapter-slider.tsx` — glass slider

### E-Reader
- `frontend/app/(reader)/read/[bookId]/[chapter]/page.tsx` — sanctum layout
- `frontend/components/reader/reader-toolbar.tsx` — auto-hide glass toolbar
- `frontend/components/reader/epub-renderer.tsx` — new themes, progress bar
- `frontend/components/reader/annotation-sidebar.tsx` — glass slide-over
- `frontend/components/reader/reading-toolbar.tsx` — visual theme picker
