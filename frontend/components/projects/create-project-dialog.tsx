"use client"

import { useState, useCallback } from "react"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { createProject } from "@/lib/api/projects"

interface CreateProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

function nameToSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
}

export function CreateProjectDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateProjectDialogProps) {
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [slugTouched, setSlugTouched] = useState(false)
  const [description, setDescription] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const handleNameChange = useCallback(
    (value: string) => {
      setName(value)
      if (!slugTouched) {
        setSlug(nameToSlug(value))
      }
    },
    [slugTouched]
  )

  const handleSlugChange = useCallback((value: string) => {
    setSlugTouched(true)
    setSlug(nameToSlug(value))
  }, [])

  const resetForm = useCallback(() => {
    setName("")
    setSlug("")
    setSlugTouched(false)
    setDescription("")
  }, [])

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!name.trim() || !slug.trim()) return

      setSubmitting(true)
      try {
        await createProject({
          name: name.trim(),
          slug: slug.trim(),
          description: description.trim() || undefined,
        })
        toast.success(`Project "${name.trim()}" created`)
        resetForm()
        onCreated()
        onOpenChange(false)
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to create project"
        toast.error(message)
      } finally {
        setSubmitting(false)
      }
    },
    [name, slug, description, resetForm, onCreated, onOpenChange]
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
          <DialogDescription>
            Create a new project to organize your books and knowledge graph.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label
              htmlFor="project-name"
              className="text-sm font-medium leading-none"
            >
              Name
            </label>
            <Input
              id="project-name"
              placeholder="My Epic Saga"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              required
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="project-slug"
              className="text-sm font-medium leading-none"
            >
              Slug
            </label>
            <Input
              id="project-slug"
              placeholder="my-epic-saga"
              value={slug}
              onChange={(e) => handleSlugChange(e.target.value)}
              required
              className="font-mono text-sm"
            />
            <p className="text-[11px] text-muted-foreground">
              Used in URLs: /projects/{slug || "..."}
            </p>
          </div>

          <div className="space-y-2">
            <label
              htmlFor="project-description"
              className="text-sm font-medium leading-none"
            >
              Description
            </label>
            <Textarea
              id="project-description"
              placeholder="A brief description of this project..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !name.trim()}>
              {submitting ? "Creating..." : "Create Project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
