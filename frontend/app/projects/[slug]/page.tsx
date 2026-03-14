"use client"
import { useState, useCallback } from "react"
import { useParams } from "next/navigation"
import { Upload, Play } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { uploadBookToProject, triggerExtraction } from "@/lib/api/projects"
import { toast } from "sonner"

export default function ProjectBooksPage() {
  const params = useParams<{ slug: string }>()
  const [uploading, setUploading] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [bookId, setBookId] = useState<string | null>(null)

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const result = await uploadBookToProject(params.slug, file)
      setBookId(result.book_id)
      toast.success(`Uploaded: ${result.chapters_found} chapters found`)
    } catch {
      toast.error("Upload failed")
    } finally {
      setUploading(false)
    }
  }, [params.slug])

  const handleExtract = useCallback(async () => {
    setExtracting(true)
    try {
      const result = await triggerExtraction(params.slug, bookId ?? undefined)
      toast.success(`Extraction started (${result.mode} mode)`)
    } catch {
      toast.error("Extraction failed")
    } finally {
      setExtracting(false)
    }
  }, [params.slug, bookId])

  return (
    <div className="space-y-6">
      {/* Upload zone */}
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-10 gap-4">
          <Upload className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Drop an EPUB file or click to upload</p>
          <label className="cursor-pointer">
            <input
              type="file"
              accept=".epub,.pdf,.txt"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
            <Button variant="outline" size="sm" disabled={uploading} asChild>
              <span>{uploading ? "Uploading..." : "Choose file"}</span>
            </Button>
          </label>
        </CardContent>
      </Card>

      {/* Actions */}
      {bookId && (
        <div className="flex gap-2">
          <Button onClick={handleExtract} disabled={extracting} size="sm">
            <Play className="h-4 w-4 mr-2" />
            {extracting ? "Extracting..." : "Start Extraction"}
          </Button>
          <Badge variant="secondary" className="text-xs">
            Book ID: {bookId}
          </Badge>
        </div>
      )}
    </div>
  )
}
