# Glass Morphism Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the WorldRAG frontend with a "Crystalline Knowledge" glass morphism aesthetic — dual light/dark themes, distinctive typography, motion animations, and floating glass panels across Dashboard, Graph Explorer, Character Sheet, and E-Reader.

**Architecture:** Component-level redesign (modify in place). New design system in globals.css + shared utility components. Each page gets motion-powered entrance animations and glass panels. next-themes for dual theme. motion (Framer Motion) for animations.

**Tech Stack:** Next.js 16, React 19, Tailwind CSS 4, shadcn/ui, motion (Framer Motion v11+), next-themes, Sigma.js, Outfit + DM Sans + JetBrains Mono fonts.

---

## Task 1: Install Dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install motion and next-themes**

```bash
cd frontend && npm install motion next-themes
```

**Step 2: Verify installation**

```bash
cd frontend && node -e "require('motion'); require('next-themes'); console.log('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add motion and next-themes dependencies"
```

---

## Task 2: Design System — globals.css + Fonts

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/next.config.ts` (CSP font-src for Google Fonts)

**Step 1: Rewrite globals.css with new design system**

Replace the entire file with:

```css
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,500;0,7..72,600;0,7..72,700;1,7..72,400;1,7..72,500&display=swap');
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: "DM Sans", system-ui, -apple-system, sans-serif;
  --font-display: "Outfit", "DM Sans", system-ui, sans-serif;
  --font-serif: "Literata", "Georgia", "Cambria", serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, monospace;
  --color-sidebar-ring: var(--sidebar-ring);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar: var(--sidebar);
  --color-chart-5: var(--chart-5);
  --color-chart-4: var(--chart-4);
  --color-chart-3: var(--chart-3);
  --color-chart-2: var(--chart-2);
  --color-chart-1: var(--chart-1);
  --color-ring: var(--ring);
  --color-input: var(--input);
  --color-border: var(--border);
  --color-destructive: var(--destructive);
  --color-accent-foreground: var(--accent-foreground);
  --color-accent: var(--accent);
  --color-muted-foreground: var(--muted-foreground);
  --color-muted: var(--muted);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-secondary: var(--secondary);
  --color-primary-foreground: var(--primary-foreground);
  --color-primary: var(--primary);
  --color-popover-foreground: var(--popover-foreground);
  --color-popover: var(--popover);
  --color-card-foreground: var(--card-foreground);
  --color-card: var(--card);
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --radius-2xl: calc(var(--radius) + 8px);
  --radius-3xl: calc(var(--radius) + 12px);
  --radius-4xl: calc(var(--radius) + 16px);
}

/* ─── Light theme ─── */
:root {
  --radius: 0.625rem;
  --background: #f8f7f4;
  --foreground: #1e1b4b;
  --card: rgba(255, 255, 255, 0.7);
  --card-foreground: #1e1b4b;
  --popover: rgba(255, 255, 255, 0.85);
  --popover-foreground: #1e1b4b;
  --primary: #6d28d9;
  --primary-foreground: #faf5ff;
  --secondary: #f0eef5;
  --secondary-foreground: #1e1b4b;
  --muted: #f0eef5;
  --muted-foreground: #6b7280;
  --accent: #f0eef5;
  --accent-foreground: #1e1b4b;
  --destructive: #dc2626;
  --border: rgba(0, 0, 0, 0.06);
  --input: rgba(0, 0, 0, 0.08);
  --ring: #7c3aed;
  --chart-1: #7c3aed;
  --chart-2: #06b6d4;
  --chart-3: #10b981;
  --chart-4: #f59e0b;
  --chart-5: #ef4444;
  --sidebar: rgba(255, 255, 255, 0.6);
  --sidebar-foreground: #1e1b4b;
  --sidebar-primary: #6d28d9;
  --sidebar-primary-foreground: #faf5ff;
  --sidebar-accent: #f0eef5;
  --sidebar-accent-foreground: #1e1b4b;
  --sidebar-border: rgba(0, 0, 0, 0.06);
  --sidebar-ring: #7c3aed;

  /* Glass tokens */
  --glass-bg: rgba(255, 255, 255, 0.7);
  --glass-border: rgba(0, 0, 0, 0.06);
  --glass-shadow: 0 4px 24px rgba(0, 0, 0, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.8);
  --glass-blur: blur(20px) saturate(1.2);
  --glass-bg-hover: rgba(255, 255, 255, 0.85);

  /* Mesh gradient colors */
  --mesh-1: rgba(124, 58, 237, 0.06);
  --mesh-2: rgba(6, 182, 212, 0.04);
  --mesh-3: rgba(16, 185, 129, 0.03);
}

/* ─── Dark theme ─── */
.dark {
  --background: #0a0e1a;
  --foreground: #e2e8f0;
  --card: rgba(255, 255, 255, 0.03);
  --card-foreground: #e2e8f0;
  --popover: rgba(255, 255, 255, 0.06);
  --popover-foreground: #e2e8f0;
  --primary: #a78bfa;
  --primary-foreground: #0a0e1a;
  --secondary: rgba(255, 255, 255, 0.06);
  --secondary-foreground: #e2e8f0;
  --muted: rgba(255, 255, 255, 0.06);
  --muted-foreground: #94a3b8;
  --accent: rgba(255, 255, 255, 0.06);
  --accent-foreground: #e2e8f0;
  --destructive: #ef4444;
  --border: rgba(255, 255, 255, 0.08);
  --input: rgba(255, 255, 255, 0.1);
  --ring: #7c3aed;
  --chart-1: #7c3aed;
  --chart-2: #06b6d4;
  --chart-3: #10b981;
  --chart-4: #f59e0b;
  --chart-5: #ef4444;
  --sidebar: rgba(255, 255, 255, 0.02);
  --sidebar-foreground: #e2e8f0;
  --sidebar-primary: #a78bfa;
  --sidebar-primary-foreground: #0a0e1a;
  --sidebar-accent: rgba(255, 255, 255, 0.06);
  --sidebar-accent-foreground: #e2e8f0;
  --sidebar-border: rgba(255, 255, 255, 0.08);
  --sidebar-ring: #7c3aed;

  /* Glass tokens */
  --glass-bg: rgba(255, 255, 255, 0.03);
  --glass-border: rgba(255, 255, 255, 0.08);
  --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  --glass-blur: blur(24px) saturate(1.5);
  --glass-bg-hover: rgba(255, 255, 255, 0.06);

  /* Mesh gradient colors */
  --mesh-1: rgba(124, 58, 237, 0.05);
  --mesh-2: rgba(6, 182, 212, 0.03);
  --mesh-3: rgba(16, 185, 129, 0.02);
}

/* ─── Glass utility ─── */
.glass {
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow);
}

.glass-hover:hover {
  background: var(--glass-bg-hover);
}

/* ─── Noise grain overlay ─── */
.grain::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.015;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
}

/* ─── Scrollbar ─── */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--muted-foreground);
}

/* ─── Graph canvas ─── */
.graph-canvas canvas {
  border-radius: 0.75rem;
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

**Step 2: Update next.config.ts CSP to allow Google Fonts**

In `frontend/next.config.ts`, update the Content-Security-Policy `font-src` and `style-src` to allow fonts.googleapis.com and fonts.gstatic.com:

Replace the CSP value:
```
font-src 'self' data:;
```
with:
```
font-src 'self' data: https://fonts.gstatic.com;
```

And replace:
```
style-src 'self' 'unsafe-inline';
```
with:
```
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
```

**Step 3: Verify build compiles**

```bash
cd frontend && npm run build
```
Expected: Build succeeds.

**Step 4: Commit**

```bash
git add frontend/app/globals.css frontend/next.config.ts
git commit -m "feat(ui): glass morphism design system — dual theme, new fonts, glass tokens"
```

---

## Task 3: Theme Provider + Layout + Gradient Mesh

**Files:**
- Modify: `frontend/app/layout.tsx`
- Create: `frontend/components/shared/gradient-mesh.tsx`
- Create: `frontend/components/shared/theme-toggle.tsx`

**Step 1: Create gradient-mesh.tsx**

```tsx
"use client"

export function GradientMesh() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden>
      <div
        className="absolute w-[600px] h-[600px] rounded-full opacity-100 animate-[drift1_20s_ease-in-out_infinite]"
        style={{
          background: "var(--mesh-1)",
          filter: "blur(120px)",
          top: "-10%",
          left: "-5%",
        }}
      />
      <div
        className="absolute w-[500px] h-[500px] rounded-full opacity-100 animate-[drift2_25s_ease-in-out_infinite]"
        style={{
          background: "var(--mesh-2)",
          filter: "blur(120px)",
          top: "40%",
          right: "-10%",
        }}
      />
      <div
        className="absolute w-[400px] h-[400px] rounded-full opacity-100 animate-[drift3_22s_ease-in-out_infinite]"
        style={{
          background: "var(--mesh-3)",
          filter: "blur(120px)",
          bottom: "-5%",
          left: "30%",
        }}
      />
    </div>
  )
}
```

Add to `globals.css` (append before `@layer base`):

```css
@keyframes drift1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.05); }
  66% { transform: translate(-20px, 15px) scale(0.95); }
}
@keyframes drift2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(-25px, 20px) scale(1.03); }
  66% { transform: translate(15px, -25px) scale(0.97); }
}
@keyframes drift3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(20px, 15px) scale(1.04); }
  66% { transform: translate(-15px, -20px) scale(0.96); }
}
```

**Step 2: Create theme-toggle.tsx**

```tsx
"use client"

import { useTheme } from "next-themes"
import { Sun, Moon } from "lucide-react"
import { useEffect, useState } from "react"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])
  if (!mounted) return <div className="h-8 w-8" />

  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="glass glass-hover rounded-lg p-2 transition-all"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4 text-amber-400" />
      ) : (
        <Moon className="h-4 w-4 text-violet-600" />
      )}
    </button>
  )
}
```

**Step 3: Rewrite layout.tsx**

```tsx
import type { Metadata } from "next"
import { ThemeProvider } from "next-themes"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Sidebar } from "@/components/shared/sidebar"
import { TopBar } from "@/components/shared/top-bar"
import { GradientMesh } from "@/components/shared/gradient-mesh"
import "./globals.css"

export const metadata: Metadata = {
  title: "WorldRAG",
  description: "Knowledge Graph Explorer for Fiction Universes",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased min-h-screen grain">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          <TooltipProvider>
            <GradientMesh />
            <Sidebar />
            <main className="md:ml-60 min-h-screen">
              <TopBar />
              <div className="p-6 lg:p-8">{children}</div>
            </main>
            <Toaster />
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
```

**Step 4: Verify build**

```bash
cd frontend && npm run build
```
Expected: Build succeeds.

**Step 5: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/globals.css frontend/components/shared/gradient-mesh.tsx frontend/components/shared/theme-toggle.tsx
git commit -m "feat(ui): add ThemeProvider, gradient mesh background, theme toggle"
```

---

## Task 4: Sidebar + TopBar Glass Redesign

**Files:**
- Modify: `frontend/components/shared/sidebar.tsx`
- Modify: `frontend/components/shared/top-bar.tsx`

**Step 1: Rewrite sidebar.tsx with glass styling and spring-animated active indicator**

Key changes:
- Replace `bg-slate-950/95` with `glass` class
- Replace `border-slate-800` with `border-[var(--glass-border)]`
- Replace `bg-indigo-600/10 text-indigo-400 border border-indigo-500/20` active styles with `glass bg-primary/10 text-primary` and a motion `layoutId` pill for the active indicator
- Replace all `text-slate-*` with semantic `text-foreground`, `text-muted-foreground`
- Add `font-display` class to "WorldRAG" heading
- Mobile toggle: `glass` styling
- Version footer: `glass` card

Use `motion` for the active indicator:
```tsx
import { motion } from "motion/react"

// Inside NavItem, when active:
{active && (
  <motion.div
    layoutId="sidebar-active"
    className="absolute inset-0 rounded-lg bg-primary/10 border border-primary/20"
    transition={{ type: "spring", stiffness: 350, damping: 30 }}
  />
)}
```

**Step 2: Rewrite top-bar.tsx with glass styling**

Key changes:
- Replace `bg-slate-950/80 border-slate-800` with `glass`
- Replace `text-slate-500 border-slate-800` on search button with `text-muted-foreground border-[var(--glass-border)]`
- Add ThemeToggle to the right side
- Import ThemeToggle from `./theme-toggle`

**Step 3: Verify build**

```bash
cd frontend && npm run build
```

**Step 4: Commit**

```bash
git add frontend/components/shared/sidebar.tsx frontend/components/shared/top-bar.tsx
git commit -m "feat(ui): glass morphism sidebar and top bar with animated active indicator"
```

---

## Task 5: Card Component Glass Variant

**Files:**
- Modify: `frontend/components/ui/card.tsx`

**Step 1: Update Card component to use glass tokens**

Replace the Card's default className to use glass styling:

```tsx
function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "glass text-card-foreground flex flex-col gap-6 rounded-xl py-6 transition-all",
        className
      )}
      {...props}
    />
  )
}
```

This makes every Card in the app automatically glass. The `glass` CSS class handles bg, backdrop-filter, border, and shadow.

**Step 2: Verify build**

```bash
cd frontend && npm run build
```

**Step 3: Commit**

```bash
git add frontend/components/ui/card.tsx
git commit -m "feat(ui): glass morphism Card component"
```

---

## Task 6: Dashboard Redesign

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/components/shared/animated-counter.tsx`

**Step 1: Create animated-counter.tsx**

```tsx
"use client"

import { useEffect, useRef, useState } from "react"

interface AnimatedCounterProps {
  value: number
  duration?: number
  className?: string
}

export function AnimatedCounter({ value, duration = 1200, className }: AnimatedCounterProps) {
  const [display, setDisplay] = useState(0)
  const startRef = useRef<number | null>(null)
  const frameRef = useRef<number>(0)

  useEffect(() => {
    const start = display
    const diff = value - start
    if (diff === 0) return

    startRef.current = null

    function step(ts: number) {
      if (!startRef.current) startRef.current = ts
      const elapsed = ts - startRef.current
      const progress = Math.min(elapsed / duration, 1)
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(start + diff * eased))
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step)
      }
    }

    frameRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frameRef.current)
  }, [value, duration])

  return <span className={className}>{new Intl.NumberFormat().format(display)}</span>
}
```

**Step 2: Rewrite page.tsx (Dashboard)**

Full redesign with:
- motion staggered entrance (`motion.div` with `initial`, `animate`, `transition.delay`)
- Hero section with large stat counters using AnimatedCounter
- Infrastructure as compact inline dots
- Quick actions as glass cards with accent glow on hover
- Book grid with glass cards and entity distribution color bar
- Replace all `text-slate-*` with `text-foreground`, `text-muted-foreground`
- Replace `Card` bg styling (now handled by glass utility)
- `font-display` class on headings (Outfit font)

Key imports to add:
```tsx
import { motion } from "motion/react"
import { AnimatedCounter } from "@/components/shared/animated-counter"
```

Stagger pattern:
```tsx
const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } },
}

<motion.div variants={container} initial="hidden" animate="show">
  <motion.div variants={item}>...</motion.div>
</motion.div>
```

**Step 3: Verify build**

```bash
cd frontend && npm run build
```

**Step 4: Commit**

```bash
git add frontend/app/page.tsx frontend/components/shared/animated-counter.tsx
git commit -m "feat(ui): redesign dashboard — glass cards, animated counters, staggered entrance"
```

---

## Task 7: Graph Explorer Redesign

**Files:**
- Modify: `frontend/app/(explorer)/graph/page.tsx`
- Modify: `frontend/components/graph/graph-controls.tsx`
- Modify: `frontend/components/graph/node-detail-panel.tsx`
- Modify: `frontend/components/graph/sigma-graph.tsx`

**Step 1: Redesign graph page — full-bleed layout**

Key changes:
- Remove outer `space-y-4` padding — graph canvas fills viewport
- Wrap header/toolbar in `absolute` positioned glass bar at top
- Left controls: `absolute left-4 top-20` floating glass panel (collapsible)
- Right detail panel: `absolute right-0 top-0 h-full` slide-in glass panel with motion animation
- Bottom zoom controls: `absolute bottom-4 left-1/2 -translate-x-1/2` pill-shaped glass bar
- Graph height: `calc(100vh - 3.5rem)` (subtract top bar)
- Empty state: centered in viewport with glass card

**Step 2: Redesign graph-controls.tsx — floating glass panel**

- Replace `rounded-xl border border-slate-800 bg-slate-900/50` with `glass rounded-2xl`
- Replace all `text-slate-*` with semantic colors
- Add collapse/expand button
- Zoom controls move to separate bottom pill (not in this panel)

**Step 3: Redesign node-detail-panel.tsx — glass slide-in**

- Wrap in `motion.div` with `initial={{ x: 100, opacity: 0 }}` `animate={{ x: 0, opacity: 1 }}`
- `glass rounded-2xl` styling
- Replace all slate colors with semantic tokens

**Step 4: Update sigma-graph.tsx — node glow effects**

- Update node rendering: add `haloColor` and `haloSize` for glow effect (Sigma v3 supports `nodeReducer` for this)
- Selected node: pulsing CSS animation on highlight
- Dark background: `backgroundColor: "transparent"` on Sigma settings (let the page background show)

**Step 5: Verify build**

```bash
cd frontend && npm run build
```

**Step 6: Commit**

```bash
git add frontend/app/(explorer)/graph/page.tsx frontend/components/graph/
git commit -m "feat(ui): glass graph explorer — full-bleed canvas, floating panels, node glow"
```

---

## Task 8: Character Sheet Redesign

**Files:**
- Modify: `frontend/app/(explorer)/characters/page.tsx`
- Modify: `frontend/app/(explorer)/characters/[name]/page.tsx`
- Modify: `frontend/components/characters/character-header.tsx`
- Modify: `frontend/components/characters/stat-grid.tsx`
- Modify: `frontend/components/characters/skill-list.tsx`
- Modify: `frontend/components/characters/class-timeline.tsx`
- Modify: `frontend/components/characters/chapter-slider.tsx`

**Step 1: Redesign characters list page**

- Glass cards with motion stagger
- Character dot uses entity-type glow (box-shadow)
- Hover: `glass-hover` + slight scale with motion `whileHover`
- Replace all slate colors with semantic tokens
- `font-display` on heading

**Step 2: Redesign character detail page**

- Full-width glass header with entity-type colored accent glow (colored box-shadow)
- `motion.div` entrance for the header
- Tab switching: `motion.div` with `key={activeTab}` for crossfade (using AnimatePresence)

**Step 3: Redesign character-header.tsx**

- Glass panel with colored top border matching entity type
- Outfit font for character name
- DM Sans for description

**Step 4: Redesign stat-grid.tsx**

- Large JetBrains Mono numbers
- Delta indicators: green arrow up / red arrow down with `text-emerald-400` / `text-red-400`
- Glass stat cells with subtle inner glow

**Step 5: Redesign skill-list.tsx**

- Glass cards
- Visual rank bar (gradient from muted to primary color, width = proficiency %)
- Acquired chapter badge

**Step 6: Redesign class-timeline.tsx**

- Horizontal visual timeline: nodes connected by lines
- Glass node circles with entity color
- Chapter numbers below each node
- Active class highlighted with glow

**Step 7: Redesign chapter-slider.tsx**

- Glass container
- Custom styled slider: glass track, glowing thumb with primary color shadow
- Chapter number tooltip follows thumb

**Step 8: Verify build**

```bash
cd frontend && npm run build
```

**Step 9: Commit**

```bash
git add frontend/app/(explorer)/characters/ frontend/components/characters/
git commit -m "feat(ui): glass character sheet — glowing headers, animated stats, visual timeline"
```

---

## Task 9: E-Reader Redesign

**Files:**
- Modify: `frontend/app/(reader)/read/[bookId]/[chapter]/page.tsx`
- Modify: `frontend/components/reader/reader-toolbar.tsx`
- Modify: `frontend/components/reader/epub-renderer.tsx`
- Modify: `frontend/components/reader/annotation-sidebar.tsx`
- Modify: `frontend/hooks/use-reader-settings.ts`

**Step 1: Add new reading themes to use-reader-settings.ts**

Add two new themes to the existing set:
- `"black"` (OLED): bg `#000000`, text `#c0c0c0`, heading `#e0e0e0`
- `"twilight"`: bg `#1a1f36`, text `#b0b8d0`, heading `#d0d8f0`

**Step 2: Redesign reader-toolbar.tsx — auto-hide glass toolbar**

Key changes:
- Glass styling instead of solid bg
- Auto-hide behavior: track scroll direction, hide on scroll down, show on scroll up
- Use `motion.div` with `animate={{ y: visible ? 0 : -100 }}`
- Visual theme preview buttons (small colored circles) instead of text labels
- Add reading progress bar at top (thin 2px accent-colored line, width = scroll %)

**Step 3: Redesign annotation rendering**

- Change from full background highlight to subtle underline + dot
- Underline color matches entity type (using `border-bottom` 2px)
- Small dot before entity name on hover
- Less disruptive to reading flow

**Step 4: Redesign annotation-sidebar.tsx — glass slide-over**

- Glass panel that slides over content from right (not pushing layout)
- `motion.div` with `initial={{ x: "100%" }}` `animate={{ x: 0 }}`
- Backdrop blur over reading content
- Entity list with type badges

**Step 5: Update reader page**

- Add scroll progress tracking (thin accent bar at top)
- Smooth chapter transitions (motion AnimatePresence with crossfade)
- Use semantic color tokens for text

**Step 6: Verify build**

```bash
cd frontend && npm run build
```

**Step 7: Commit**

```bash
git add frontend/app/(reader)/read/ frontend/components/reader/ frontend/hooks/use-reader-settings.ts
git commit -m "feat(ui): glass e-reader — auto-hide toolbar, new themes, subtle annotations"
```

---

## Task 10: Book Selector + Remaining Shared Components

**Files:**
- Modify: `frontend/components/shared/book-selector.tsx`
- Modify: `frontend/components/shared/search-command.tsx`

**Step 1: Update book-selector.tsx**

- Replace `bg-slate-900/50 border-slate-800` with `glass glass-hover`
- Replace all `text-slate-*` with semantic tokens
- Dropdown content: glass styling

**Step 2: Update search-command.tsx**

- Glass overlay styling
- Semantic color tokens

**Step 3: Verify build**

```bash
cd frontend && npm run build
```

**Step 4: Commit**

```bash
git add frontend/components/shared/
git commit -m "feat(ui): glass book selector and search command"
```

---

## Task 11: Visual QA + Polish

**Files:**
- Various touch-ups

**Step 1: Start dev server and check all pages visually**

```bash
cd frontend && npm run dev
```

Check each page in both light and dark themes:
1. Dashboard — stat counters animate, glass cards render, gradient mesh visible
2. Graph Explorer — full-bleed canvas, floating panels work, node glow visible
3. Characters — glass cards, stagger animation, character detail tabs crossfade
4. E-Reader — toolbar auto-hides, themes work, annotations subtle
5. Sidebar — active pill animates between nav items
6. TopBar — theme toggle works

**Step 2: Fix any rendering issues found**

Common things to watch for:
- Glass panels not showing backdrop-blur (need `backdrop-filter` support)
- Light theme contrast issues
- Motion layout animations conflicting with flex/grid
- Z-index stacking issues with floating panels

**Step 3: Run production build**

```bash
cd frontend && npm run build
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(ui): glass morphism polish pass — visual QA fixes"
```

---

## Summary

| Task | Description | Files | Est. |
|------|-------------|-------|------|
| 1 | Install dependencies | package.json | 2 min |
| 2 | Design system (CSS + fonts) | globals.css, next.config.ts | 10 min |
| 3 | ThemeProvider + layout + mesh | layout.tsx, 2 new components | 10 min |
| 4 | Sidebar + TopBar glass | 2 files | 15 min |
| 5 | Card glass variant | card.tsx | 5 min |
| 6 | Dashboard redesign | page.tsx, animated-counter | 20 min |
| 7 | Graph Explorer redesign | page.tsx, 3 components | 25 min |
| 8 | Character Sheet redesign | 2 pages, 5 components | 25 min |
| 9 | E-Reader redesign | page.tsx, 3 components, hook | 20 min |
| 10 | Shared components | book-selector, search-command | 10 min |
| 11 | Visual QA + polish | Various | 15 min |
