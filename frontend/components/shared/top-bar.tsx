"use client"

import { ThemeToggle } from "./theme-toggle"

export function TopBar() {
  return (
    <div className="glass sticky top-0 z-30 flex h-14 items-center justify-end px-6">
      <ThemeToggle />
    </div>
  )
}
