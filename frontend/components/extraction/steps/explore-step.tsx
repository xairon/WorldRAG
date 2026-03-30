"use client"

interface ExploreStepProps {
  projectSlug: string
  bookId: string
  onStart: () => void
}

export function ExploreStep({ projectSlug, bookId, onStart }: ExploreStepProps) {
  void projectSlug
  void bookId
  void onStart
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-sm">Explore step — coming soon</p>
    </div>
  )
}
