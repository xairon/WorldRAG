import { apiFetch } from "@/lib/api/client"
import { VaultCard } from "@/components/projects/vault-card"
import { CreateProjectDialog } from "@/components/projects/create-project-dialog"
import { EmptyState } from "@/components/shared/empty-state"
import { ThemeToggle } from "@/components/shared/theme-toggle"
import { Search } from "lucide-react"

interface Project {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
  cover_image?: string | null
}

async function getProjects(): Promise<Project[]> {
  try {
    const res = await apiFetch<{ projects: Project[] }>("/projects")
    return res.projects ?? (Array.isArray(res) ? (res as unknown as Project[]) : [])
  } catch {
    return []
  }
}

export default async function DashboardPage() {
  const projects = await getProjects()

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-[1400px] px-6 h-14 flex items-center justify-between">
          <h1 className="font-display font-bold text-xl tracking-tight">WorldRAG</h1>
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search projects..."
                className="h-9 w-64 rounded-lg border bg-muted/50 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <ThemeToggle />
            <CreateProjectDialog />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-8">
        {projects.length === 0 ? (
          <EmptyState
            title="Create your first universe"
            description="Each project is a workspace for a saga or book series. Upload your novels and let WorldRAG build the knowledge graph."
            action={<CreateProjectDialog />}
          />
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <VaultCard key={p.slug} project={p} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
