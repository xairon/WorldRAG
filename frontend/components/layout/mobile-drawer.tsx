"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Menu } from "lucide-react"
import { useUIStore } from "@/stores/ui-store"
import { SidebarProjectNav } from "./sidebar-project-nav"
import { SidebarBookList } from "./sidebar-book-list"

interface MobileDrawerProps {
  slug: string
  projectName: string
  books: { id: string; title: string; status: string }[]
}

export function MobileDrawer({ slug, projectName, books }: MobileDrawerProps) {
  const { mobileSidebarOpen, setMobileSidebarOpen } = useUIStore()
  const pathname = usePathname()

  // Auto-close drawer on navigation
  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [pathname, setMobileSidebarOpen])

  return (
    <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
      <SheetTrigger asChild>
        <button className="md:hidden p-2 hover:bg-muted rounded-md" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[260px] p-0">
        <div className="px-3 py-3 border-b">
          <span className="text-sm font-semibold">{projectName}</span>
        </div>
        <div className="py-2">
          <SidebarProjectNav slug={slug} collapsed={false} />
        </div>
        <div className="border-t mx-3" />
        <div className="py-2">
          <SidebarBookList slug={slug} books={books} collapsed={false} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
