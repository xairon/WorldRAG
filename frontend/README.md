# WorldRAG Frontend

Next.js 16 / React 19 / TypeScript frontend for WorldRAG.

## Stack

- **Framework**: Next.js 16 (App Router, Server Components)
- **UI**: shadcn/ui + Tailwind CSS
- **State**: Zustand (book-store, graph-store, ui-store, chat-store)
- **Graph**: Sigma.js 3.0 + graphology (ForceAtlas2 layout)
- **Chat**: SSE streaming with citation display

## Development

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm run lint       # eslint check
```

## Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── projects/[slug]/    # Project-scoped pages (graph, chat, reader)
│   └── layout.tsx          # Root layout with sidebar
├── components/             # React components
│   ├── chat/               # Chat UI (thread sidebar, citations, feedback)
│   ├── graph/              # Sigma.js graph explorer
│   ├── books/              # Book management
│   ├── extraction/         # Extraction pipeline controls
│   └── ui/                 # shadcn/ui base components
├── hooks/                  # Custom React hooks
├── stores/                 # Zustand stores
└── lib/                    # API client, utils, types
```
