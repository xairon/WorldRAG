"use client"

interface ExtractStepProps {
  projectSlug: string
  bookId: string
  onComplete: () => void
}

export function ExtractStep({ projectSlug, bookId, onComplete }: ExtractStepProps) {
  void projectSlug
  void bookId
  void onComplete
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-sm">Extract step — coming soon</p>
    </div>
  )
}
