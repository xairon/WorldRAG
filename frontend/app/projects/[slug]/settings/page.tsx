import { apiFetch } from "@/lib/api/client"
import { ProjectSettingsForm } from "@/components/settings/project-settings-form"
import { DeleteProjectDialog } from "@/components/settings/delete-project-dialog"

async function getProject(slug: string) {
  return apiFetch<{ slug: string; name: string; description: string; created_at: string }>(`/projects/${slug}`)
}

export default async function SettingsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const project = await getProject(slug)
  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-xl font-semibold mb-6">Settings</h1>
      <ProjectSettingsForm project={project} />
      <div className="border-t mt-8 pt-8">
        <h2 className="text-sm font-medium text-red-500 mb-2">Danger zone</h2>
        <p className="text-sm text-muted-foreground mb-4">Delete this project and all its data. This action cannot be undone.</p>
        <DeleteProjectDialog projectName={project.name} slug={slug} />
      </div>
    </div>
  )
}
