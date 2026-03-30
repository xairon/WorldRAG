"use client"

import { use } from "react"
import { parseAsStringEnum, useQueryState } from "nuqs"
import { useBookDetail } from "@/hooks/use-books"
import {
  PipelineLayout,
  type PipelineStepKey,
} from "@/components/pipeline/pipeline-layout"
import { UploadStep } from "@/components/extraction/steps/upload-step"
import { ConfigureStep } from "@/components/extraction/steps/configure-step"
import { ExtractStep } from "@/components/extraction/steps/extract-step"
import { ReviewStep } from "@/components/extraction/steps/review-step"
import { ExploreStep } from "@/components/extraction/steps/explore-step"

const STEP_KEYS: PipelineStepKey[] = ["upload", "configure", "extract", "review", "explore"]

function computeCompletedSteps(status: string | undefined): Set<PipelineStepKey> {
  const completed = new Set<PipelineStepKey>()
  if (!status) return completed

  // upload is complete once a book exists
  completed.add("upload")

  if (
    status === "ingested" ||
    status === "extracting" ||
    status === "extracted" ||
    status === "embedding" ||
    status === "embedded"
  ) {
    completed.add("configure")
  }

  if (status === "extracted" || status === "embedding" || status === "embedded") {
    completed.add("extract")
  }

  if (status === "embedded") {
    completed.add("review")
  }

  return completed
}

export default function ExtractionPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = use(params)

  const [step, setStep] = useQueryState(
    "step",
    parseAsStringEnum<PipelineStepKey>(STEP_KEYS).withDefault("upload")
  )

  const { data: bookDetail } = useBookDetail(bookId)
  const bookStatus = bookDetail?.book.status

  const completedSteps = computeCompletedSteps(bookStatus)

  function handleStepClick(key: PipelineStepKey) {
    void setStep(key)
  }

  function goTo(key: PipelineStepKey) {
    void setStep(key)
  }

  return (
    <PipelineLayout
      currentStep={step}
      completedSteps={completedSteps}
      onStepClick={handleStepClick}
    >
      {step === "upload" && (
        <UploadStep
          projectSlug={slug}
          bookId={bookId}
          onContinue={() => goTo("configure")}
        />
      )}
      {step === "configure" && (
        <ConfigureStep
          projectSlug={slug}
          bookId={bookId}
          onContinue={() => goTo("extract")}
        />
      )}
      {step === "extract" && (
        <ExtractStep
          projectSlug={slug}
          bookId={bookId}
          onComplete={() => goTo("review")}
        />
      )}
      {step === "review" && (
        <ReviewStep
          projectSlug={slug}
          bookId={bookId}
          onContinue={() => goTo("explore")}
        />
      )}
      {step === "explore" && (
        <ExploreStep
          projectSlug={slug}
          bookId={bookId}
          onStart={() => goTo("explore")}
        />
      )}
    </PipelineLayout>
  )
}
