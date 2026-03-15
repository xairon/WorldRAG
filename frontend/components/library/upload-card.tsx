"use client"

import { useState, useRef, useCallback } from "react"
import { Upload } from "lucide-react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

const ACCEPTED = [".epub", ".pdf", ".txt"]

export function UploadCard({ slug }: { slug: string }) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  const upload = useCallback(
    async (file: File) => {
      const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase()
      if (!ACCEPTED.includes(ext)) {
        toast.error(`Unsupported format: ${ext}. Use EPUB, PDF, or TXT.`)
        return
      }
      setUploading(true)
      try {
        const form = new FormData()
        form.append("file", file)
        form.append("book_num", "1")
        const res = await fetch(`/api/projects/${slug}/books`, { method: "POST", body: form })
        if (!res.ok) {
          const body = await res.text()
          throw new Error(body || `Upload failed (${res.status})`)
        }
        toast.success(`"${file.name}" added`)
        router.refresh()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Upload failed")
      } finally {
        setUploading(false)
      }
    },
    [slug, router],
  )

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) upload(file)
    e.target.value = ""
  }

  return (
    <div
      onClick={() => !uploading && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-xl border-2 border-dashed flex flex-col items-center justify-center cursor-pointer transition-all duration-150 aspect-[2/3]",
        isDragOver
          ? "border-primary bg-primary/5 scale-[1.02]"
          : "border-muted-foreground/20 hover:border-primary/50 hover:bg-muted/30",
        uploading && "opacity-50 pointer-events-none animate-pulse",
      )}
    >
      <Upload className="h-8 w-8 text-muted-foreground mb-2" />
      <span className="text-sm font-medium text-muted-foreground">
        {uploading ? "Uploading..." : "Add a book"}
      </span>
      <span className="text-xs text-muted-foreground mt-1">EPUB, PDF, TXT</span>
      <input
        ref={inputRef}
        type="file"
        accept=".epub,.pdf,.txt"
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  )
}
