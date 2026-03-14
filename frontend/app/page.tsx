"use client"

import { useEffect, useState, useCallback } from "react"
import { Plus, FolderOpen } from "lucide-react"
import { motion } from "motion/react"
import { listProjects } from "@/lib/api/projects"
import type { Project } from "@/lib/api/projects"
import { useProjectStore } from "@/stores/project-store"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { ProjectCard } from "@/components/projects/project-card"
import { CreateProjectDialog } from "@/components/projects/create-project-dialog"

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.4, 0.25, 1] as const } },
}

export default function DashboardPage() {
  const { projects, setProjects, setLoading, loading } = useProjectStore()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await listProjects()
      setProjects(res.projects)
    } catch {
      setError("Failed to load projects. Please try again.")
    } finally {
      setLoading(false)
    }
  }, [setProjects, setLoading])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  if (loading && projects.length === 0) {
    return (
      <div className="space-y-8">
        <div>
          <Skeleton className="h-10 w-56 mb-2" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div variants={item}>
        <h1 className="font-display text-4xl font-light tracking-tight">
          Your Projects
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage your fiction universe knowledge graphs
        </p>
      </motion.div>

      {/* Error state */}
      {error && (
        <motion.div variants={item}>
          <Card className="border-destructive/50 bg-destructive/5">
            <CardContent className="flex flex-col items-center justify-center py-8 gap-3">
              <p className="text-sm text-destructive font-medium">{error}</p>
              <button
                onClick={fetchProjects}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Retry
              </button>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Project grid */}
      {!error && projects.length === 0 ? (
        <motion.div variants={item}>
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <FolderOpen className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground mb-1 font-medium">
                No projects yet
              </p>
              <p className="text-sm text-muted-foreground mb-5">
                Create your first project to get started.
              </p>
              <button
                onClick={() => setDialogOpen(true)}
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus className="h-4 w-4" />
                New Project
              </button>
            </CardContent>
          </Card>
        </motion.div>
      ) : !error ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project: Project) => (
            <motion.div key={project.id} variants={item}>
              <ProjectCard
                slug={project.slug}
                name={project.name}
                description={project.description}
                booksCount={project.books_count}
                hasProfile={project.has_profile}
                entityCount={project.entity_count}
                updatedAt={project.updated_at}
              />
            </motion.div>
          ))}

          {/* New project card */}
          <motion.div variants={item}>
            <Card
              className="h-full border-dashed cursor-pointer transition-all duration-200 hover:border-primary/40 hover:bg-muted/30 group"
              onClick={() => setDialogOpen(true)}
            >
              <CardContent className="pt-5 pb-4 flex flex-col items-center justify-center h-full min-h-[140px] gap-2">
                <div className="rounded-full p-3 bg-muted/50 group-hover:bg-primary/10 transition-colors">
                  <Plus className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
                <span className="text-sm font-medium text-muted-foreground group-hover:text-primary transition-colors">
                  New Project
                </span>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      ) : null}

      <CreateProjectDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreated={fetchProjects}
      />
    </motion.div>
  )
}
