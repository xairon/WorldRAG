"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"

interface VaultProject {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
  cover_image?: string | null
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function CoverMosaic({ images, name }: { images: string[]; name: string }) {
  if (images.length === 0) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
        <span className="text-4xl font-display font-bold text-primary/40">
          {name.charAt(0).toUpperCase()}
        </span>
      </div>
    )
  }

  if (images.length === 1) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={images[0]} alt="" className="w-full h-full object-cover" />
    )
  }

  const slots = images.slice(0, 4)
  return (
    <div className="w-full h-full grid grid-cols-2 grid-rows-2">
      {slots.map((src, i) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={i} src={src} alt="" className="w-full h-full object-cover" />
      ))}
      {slots.length < 4 &&
        Array.from({ length: 4 - slots.length }).map((_, i) => (
          <div key={`empty-${i}`} className="bg-muted" />
        ))}
    </div>
  )
}

export function VaultCard({ project }: { project: VaultProject }) {
  const router = useRouter()
  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [newName, setNewName] = useState(project.name)
  const [confirmName, setConfirmName] = useState("")
  const [loading, setLoading] = useState(false)

  const coverImages = project.cover_image ? [project.cover_image] : []

  async function handleRename(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setLoading(true)
    try {
      await fetch(`/api/projects/${project.slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() }),
      })
      toast.success("Project renamed")
      setRenameOpen(false)
      router.refresh()
    } catch {
      toast.error("Failed to rename project")
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete() {
    setLoading(true)
    try {
      await fetch(`/api/projects/${project.slug}`, { method: "DELETE" })
      toast.success("Project deleted")
      setDeleteOpen(false)
      router.refresh()
    } catch {
      toast.error("Failed to delete project")
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="group relative rounded-xl border overflow-hidden transition-all duration-150 hover:scale-[1.02] hover:shadow-lg">
        <Link href={`/projects/${project.slug}`} className="block">
          <div className="aspect-[16/10] overflow-hidden bg-muted">
            <CoverMosaic images={coverImages} name={project.name} />
          </div>
          <div className="p-4">
            <h3 className="font-display font-semibold text-lg truncate pr-8">
              {project.name}
            </h3>
            {project.description && (
              <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                {project.description}
              </p>
            )}
            <div className="flex items-center justify-between mt-3">
              <div className="flex gap-3 text-xs text-muted-foreground font-mono">
                <span>{project.books_count} book{project.books_count !== 1 ? "s" : ""}</span>
                <span>{project.entity_count} entities</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {timeAgo(project.updated_at)}
              </span>
            </div>
          </div>
        </Link>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-2 right-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity bg-background/60 backdrop-blur-sm"
              onClick={(e) => e.preventDefault()}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => { setNewName(project.name); setRenameOpen(true) }}>
              <Pencil className="h-3.5 w-3.5 mr-2" /> Rename
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => { setConfirmName(""); setDeleteOpen(true) }}
              className="text-red-500 focus:text-red-500"
            >
              <Trash2 className="h-3.5 w-3.5 mr-2" /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Rename project</DialogTitle></DialogHeader>
          <form onSubmit={handleRename} className="space-y-4">
            <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Project name" autoFocus />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setRenameOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={loading || !newName.trim()}>{loading ? "Saving..." : "Save"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle className="text-red-500">Delete project</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will permanently delete <strong>{project.name}</strong> and all its data. Type the project name to confirm.
          </p>
          <Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} placeholder={project.name} autoFocus />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>Cancel</Button>
            <Button variant="destructive" disabled={loading || confirmName !== project.name} onClick={handleDelete}>
              {loading ? "Deleting..." : "Delete permanently"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
