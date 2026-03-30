"use client"

import { AnimatePresence, motion } from "motion/react"
import { StepIndicator, type Step } from "@/components/pipeline/step-indicator"

export type PipelineStepKey = "upload" | "configure" | "extract" | "review" | "explore"

const STEP_LABELS: Record<PipelineStepKey, string> = {
  upload: "Upload",
  configure: "Configure",
  extract: "Extract",
  review: "Review",
  explore: "Explore",
}

const STEP_ORDER: PipelineStepKey[] = ["upload", "configure", "extract", "review", "explore"]

interface PipelineLayoutProps {
  currentStep: PipelineStepKey
  completedSteps: Set<PipelineStepKey>
  onStepClick: (step: PipelineStepKey) => void
  children: React.ReactNode
}

export function PipelineLayout({
  currentStep,
  completedSteps,
  onStepClick,
  children,
}: PipelineLayoutProps) {
  const steps: Step[] = STEP_ORDER.map((key) => ({
    label: STEP_LABELS[key],
    status: completedSteps.has(key)
      ? "completed"
      : key === currentStep
        ? "active"
        : "upcoming",
  }))

  function handleStepClick(index: number) {
    const key = STEP_ORDER[index]
    if (completedSteps.has(key)) {
      onStepClick(key)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-center px-4 pt-6">
        <StepIndicator steps={steps} onStepClick={handleStepClick} />
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
