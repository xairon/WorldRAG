"use client"

import { useState, useMemo } from "react"
import { MoreHorizontal, Pencil, Trash2, Merge, Check, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { ConfidenceBar } from "@/components/ui/confidence-bar"
import { useRenameEntity, useDeleteEntity, useMergeEntities } from "@/hooks/use-graph-mutations"
import { ENTITY_COLORS } from "@/lib/constants"
import type { GraphNode } from "@/lib/api/types"

interface EntityReviewTableProps {
  entities: GraphNode[]
  bookId: string
}

export function EntityReviewTable({ entities, bookId: _bookId }: EntityReviewTableProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [search, setSearch] = useState("")

  const renameMutation = useRenameEntity()
  const deleteMutation = useDeleteEntity()
  const mergeMutation = useMergeEntities()

  const filtered = useMemo(() => {
    let result = entities
    if (filterType) {
      result = result.filter((e) => e.labels.includes(filterType))
    }
    if (search) {
      const q = search.toLowerCase()
      result = result.filter((e) => e.name.toLowerCase().includes(q))
    }
    return result
  }, [entities, filterType, search])

  const entityTypes = useMemo(
    () => [...new Set(entities.flatMap((e) => e.labels))].sort(),
    [entities],
  )

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const startRename = (entity: GraphNode) => {
    setEditingId(entity.id)
    setEditName(entity.name)
  }

  const confirmRename = () => {
    if (!editingId || !editName.trim()) return
    renameMutation.mutate(
      { entityId: editingId, name: editName.trim(), canonicalName: editName.trim().toLowerCase() },
      { onSuccess: () => setEditingId(null) },
    )
  }

  const handleDelete = (id: string) => {
    if (confirm("Delete this entity and all its relationships?")) {
      deleteMutation.mutate(id)
    }
  }

  const handleMerge = () => {
    const ids = Array.from(selected)
    if (ids.length !== 2) return
    mergeMutation.mutate(
      { sourceId: ids[0], targetId: ids[1] },
      {
        onSuccess: () => {
          setSelected(new Set())
          setMergeDialogOpen(false)
        },
      },
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Input
          placeholder="Search entities..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs h-8 text-sm"
        />
        <div className="flex gap-1 flex-wrap">
          <Badge
            variant={filterType === null ? "default" : "outline"}
            className="cursor-pointer text-xs"
            onClick={() => setFilterType(null)}
          >
            All
          </Badge>
          {entityTypes.map((t) => (
            <Badge
              key={t}
              variant={filterType === t ? "default" : "outline"}
              className="cursor-pointer text-xs"
              onClick={() => setFilterType(filterType === t ? null : t)}
            >
              {t}
            </Badge>
          ))}
        </div>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">{selected.size} selected</span>
          {selected.size === 2 && (
            <Button variant="outline" size="sm" onClick={() => setMergeDialogOpen(true)}>
              <Merge className="mr-1.5 h-3 w-3" /> Merge
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={() => {
              if (confirm(`Delete ${selected.size} entities?`)) {
                selected.forEach((id) => deleteMutation.mutate(id))
                setSelected(new Set())
              }
            }}
          >
            <Trash2 className="mr-1.5 h-3 w-3" /> Delete
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="w-8 p-2" />
              <th className="text-left p-2 font-medium">Name</th>
              <th className="text-left p-2 font-medium">Type</th>
              <th className="text-left p-2 font-medium w-24">Confidence</th>
              <th className="w-10 p-2" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((entity) => (
              <tr key={entity.id} className="border-b last:border-0 hover:bg-muted/30">
                <td className="p-2">
                  <Checkbox
                    checked={selected.has(entity.id)}
                    onCheckedChange={() => toggleSelect(entity.id)}
                  />
                </td>
                <td className="p-2">
                  {editingId === entity.id ? (
                    <div className="flex items-center gap-1">
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="h-7 text-sm"
                        autoFocus
                        onKeyDown={(e) => e.key === "Enter" && confirmRename()}
                      />
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={confirmRename}>
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditingId(null)}>
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <span className="font-medium">{entity.name}</span>
                  )}
                </td>
                <td className="p-2">
                  <Badge
                    variant="outline"
                    className="text-xs"
                    style={{
                      borderColor: ENTITY_COLORS[entity.labels[0]]
                        ? `var(--color-${ENTITY_COLORS[entity.labels[0]]})`
                        : undefined,
                    }}
                  >
                    {entity.labels[0]}
                  </Badge>
                </td>
                <td className="p-2">
                  <ConfidenceBar value={entity.score ?? 1.0} />
                </td>
                <td className="p-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => startRename(entity)}>
                        <Pencil className="mr-2 h-3.5 w-3.5" /> Rename
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDelete(entity.id)}
                      >
                        <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Merge dialog */}
      <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Merge entities</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            The first selected entity will be merged into the second. All relationships
            will be transferred and the first entity will be deleted.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMergeDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleMerge} disabled={mergeMutation.isPending}>
              Merge
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
