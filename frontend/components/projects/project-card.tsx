import Link from "next/link"

interface Project {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
}

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link href={`/projects/${project.slug}`} className="block">
      <div className="border rounded-lg p-4 hover:bg-muted/50 transition-colors">
        <h3 className="text-lg font-semibold truncate">{project.name}</h3>
        {project.description && (
          <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
            {project.description}
          </p>
        )}
        <div className="flex gap-4 mt-3 text-xs text-muted-foreground font-mono">
          <span>{project.books_count} books</span>
          <span>{project.entity_count} entities</span>
        </div>
      </div>
    </Link>
  )
}
