import { apiFetch } from "@/lib/api/client"
import { TopBar } from "@/components/layout/top-bar"
import { ProjectCard } from "@/components/projects/project-card"
import { CreateProjectDialog } from "@/components/projects/create-project-dialog"
import { EmptyState } from "@/components/shared/empty-state"

interface Project {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
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
    <div className="flex flex-col min-h-screen">
      <TopBar breadcrumbs={[{ label: "Projects" }]} />
      <main className="flex-1 p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <CreateProjectDialog />
        </div>

        {projects.length === 0 ? (
          <EmptyState
            title="No projects yet"
            description="Create your first project to start building knowledge graphs from your books."
            action={<CreateProjectDialog />}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <ProjectCard key={p.slug} project={p} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
