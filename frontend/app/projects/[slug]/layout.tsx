import { apiFetch } from "@/lib/api/client"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { TopBar } from "@/components/layout/top-bar"

interface ProjectResponse {
  slug: string
  name: string
}

interface BookFile {
  id: string
  book_id: string
  original_filename: string
  status: string
}

async function getProject(slug: string): Promise<ProjectResponse | null> {
  try {
    return await apiFetch<ProjectResponse>(`/projects/${slug}`)
  } catch {
    return null
  }
}

async function getBooks(slug: string): Promise<BookFile[]> {
  try {
    return await apiFetch<BookFile[]>(`/projects/${slug}/books`)
  } catch {
    return []
  }
}

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const [project, books] = await Promise.all([getProject(slug), getBooks(slug)])

  if (!project) {
    return <div className="p-8">Project not found</div>
  }

  const sidebarBooks = books.map((b) => ({
    id: b.book_id ?? b.id,
    title: b.original_filename?.replace(/\.(epub|pdf|txt)$/i, "") ?? "Untitled",
    status: b.status ?? "pending",
  }))

  return (
    <div className="flex min-h-screen">
      <AppSidebar slug={slug} projectName={project.name} books={sidebarBooks} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          breadcrumbs={[
            { label: "Projects", href: "/projects" },
            { label: project.name },
          ]}
          drawer={{ slug, projectName: project.name, books: sidebarBooks }}
        />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  )
}
