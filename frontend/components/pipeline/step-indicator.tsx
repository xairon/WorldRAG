"use client"

import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

export type StepStatus = "completed" | "active" | "upcoming"

export interface Step {
  label: string
  status: StepStatus
}

interface StepIndicatorProps {
  steps: Step[]
  onStepClick: (index: number) => void
}

export function StepIndicator({ steps, onStepClick }: StepIndicatorProps) {
  return (
    <nav aria-label="Pipeline progress">
      <ol className="flex items-center">
        {steps.map((step, index) => {
          const isLast = index === steps.length - 1
          const isCompleted = step.status === "completed"
          const isActive = step.status === "active"

          return (
            <li key={step.label} className="flex items-center">
              {/* Circle */}
              <button
                type="button"
                onClick={() => isCompleted && onStepClick(index)}
                disabled={!isCompleted}
                className={cn(
                  "relative flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all",
                  isCompleted &&
                    "border-green-500 bg-green-500 text-white cursor-pointer hover:bg-green-600 hover:border-green-600",
                  isActive &&
                    "border-primary bg-background text-primary cursor-default",
                  step.status === "upcoming" &&
                    "border-muted-foreground/30 bg-background text-muted-foreground/50 cursor-not-allowed"
                )}
                aria-current={isActive ? "step" : undefined}
              >
                {isCompleted ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <span className="flex items-center justify-center">
                    {isActive ? (
                      <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                    ) : (
                      <span className="text-xs font-medium">{index + 1}</span>
                    )}
                  </span>
                )}
              </button>

              {/* Label */}
              <span
                className={cn(
                  "ml-2 text-xs font-medium",
                  isActive && "font-bold text-foreground",
                  isCompleted && "text-green-600",
                  step.status === "upcoming" && "text-muted-foreground/50"
                )}
              >
                {step.label}
              </span>

              {/* Connector line */}
              {!isLast && (
                <div
                  className={cn(
                    "mx-3 h-px w-12 flex-shrink-0",
                    isCompleted ? "bg-green-500" : "border-t border-dashed border-muted-foreground/30 bg-transparent"
                  )}
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
