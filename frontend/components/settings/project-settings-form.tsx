"use client"

import { useState, useCallback } from "react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/api/client"

interface Project {
  slug: string
  name: string
  description: string
  created_at: string
}

export function ProjectSettingsForm({ project }: { project: Project }) {
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description ?? "")
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const hasChanges = name !== project.name || description !== (project.description ?? "")

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaved(false)
    try {
      await apiFetch(`/projects/${project.slug}`, {
        method: "PUT",
        body: JSON.stringify({ name, description }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }, [name, description, project.slug])

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="project-name">
          Name
        </label>
        <Input
          id="project-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium" htmlFor="project-description">
          Description
        </label>
        <Textarea
          id="project-description"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">Slug</label>
        <p className="font-mono text-muted-foreground text-sm">{project.slug}</p>
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">Created</label>
        <p className="text-sm text-muted-foreground">
          {new Date(project.created_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Button disabled={!hasChanges || saving} onClick={handleSave}>
          {saving ? "Saving..." : "Save"}
        </Button>
        {saved && (
          <span className="text-sm text-emerald-600">Saved</span>
        )}
      </div>
    </div>
  )
}
