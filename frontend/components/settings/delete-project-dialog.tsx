"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { apiFetch } from "@/lib/api/client"

export function DeleteProjectDialog({
  projectName,
  slug,
}: {
  projectName: string
  slug: string
}) {
  const router = useRouter()
  const [confirmation, setConfirmation] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [open, setOpen] = useState(false)

  const canDelete = confirmation === projectName

  async function handleDelete() {
    setDeleting(true)
    try {
      await apiFetch(`/projects/${slug}`, { method: "DELETE" })
      router.push("/projects")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) setConfirmation("") }}>
      <DialogTrigger asChild>
        <Button variant="outline" className="border-red-500 text-red-500 hover:bg-red-500/10">
          Delete project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete project</DialogTitle>
          <DialogDescription>
            This will permanently delete <strong>{projectName}</strong> and all its data.
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="confirm-delete">
            Type <span className="font-mono font-semibold">{projectName}</span> to confirm
          </label>
          <Input
            id="confirm-delete"
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            placeholder={projectName}
          />
        </div>
        <DialogFooter>
          <Button
            variant="destructive"
            disabled={!canDelete || deleting}
            onClick={handleDelete}
          >
            {deleting ? "Deleting..." : "Delete permanently"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
