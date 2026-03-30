"use client"

interface ConfigureStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function ConfigureStep({ projectSlug, bookId, onContinue }: ConfigureStepProps) {
  void projectSlug
  void bookId
  void onContinue
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <p className="text-sm">Configure step — coming soon</p>
    </div>
  )
}
