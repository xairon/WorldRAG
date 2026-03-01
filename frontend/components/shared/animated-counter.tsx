"use client"

import { useEffect, useRef, useState } from "react"

interface AnimatedCounterProps {
  value: number
  duration?: number
  className?: string
}

export function AnimatedCounter({ value, duration = 1200, className }: AnimatedCounterProps) {
  const [display, setDisplay] = useState(0)
  const startRef = useRef<number | null>(null)
  const frameRef = useRef<number>(0)
  const prevRef = useRef(0)

  useEffect(() => {
    const start = prevRef.current
    const diff = value - start
    if (diff === 0) return

    startRef.current = null

    function step(ts: number) {
      if (!startRef.current) startRef.current = ts
      const elapsed = ts - startRef.current
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = Math.round(start + diff * eased)
      setDisplay(current)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step)
      } else {
        prevRef.current = value
      }
    }

    frameRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frameRef.current)
  }, [value, duration])

  return <span className={className}>{new Intl.NumberFormat().format(display)}</span>
}
