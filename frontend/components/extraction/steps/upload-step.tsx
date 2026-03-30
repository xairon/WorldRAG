"use client"

interface UploadStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function UploadStep({ projectSlug, bookId, onContinue }: UploadStepProps) {
  void projectSlug
  void bookId
  void onContinue
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-sm">Upload step — coming soon</p>
    </div>
  )
}
