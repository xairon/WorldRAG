"use client"

interface ReviewStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function ReviewStep({ projectSlug, bookId, onContinue }: ReviewStepProps) {
  void projectSlug
  void bookId
  void onContinue
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-sm">Review step — coming soon</p>
    </div>
  )
}
