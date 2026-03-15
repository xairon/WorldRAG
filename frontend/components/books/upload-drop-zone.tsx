"use client"

import { useCallback, useRef, useState } from "react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

const ALLOWED_EXTENSIONS = [".epub", ".pdf", ".txt"]

function validateFile(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase()
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `Invalid file type: ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`
  }
  return null
}

export function UploadDropZone({
  slug,
  onUploadComplete,
}: {
  slug: string
  onUploadComplete: () => void
}) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const upload = useCallback(
    async (file: File) => {
      const error = validateFile(file)
      if (error) {
        toast.error(error)
        return
      }

      setIsUploading(true)
      try {
        const formData = new FormData()
        formData.append("file", file)

        const res = await fetch(`/api/projects/${slug}/books`, {
          method: "POST",
          body: formData,
        })

        if (!res.ok) {
          const body = await res.text()
          throw new Error(body || `Upload failed (${res.status})`)
        }

        toast.success(`Uploaded ${file.name}`)
        onUploadComplete()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Upload failed")
      } finally {
        setIsUploading(false)
      }
    },
    [slug, onUploadComplete],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) upload(file)
    },
    [upload],
  )

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) upload(file)
      // Reset so same file can be re-selected
      e.target.value = ""
    },
    [upload],
  )

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        "flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-sm text-muted-foreground transition-colors hover:border-muted-foreground/50",
        isDragOver && "border-blue-500 bg-blue-500/5",
        isUploading && "pointer-events-none opacity-60",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".epub,.pdf,.txt"
        onChange={handleChange}
        className="hidden"
      />
      {isUploading ? "Uploading..." : "Drop an EPUB, PDF, or TXT file here, or click to browse"}
    </div>
  )
}
