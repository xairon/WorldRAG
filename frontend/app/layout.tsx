import type { Metadata } from "next"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Sidebar } from "@/components/shared/sidebar"
import { TopBar } from "@/components/shared/top-bar"
import "./globals.css"

export const metadata: Metadata = {
  title: "WorldRAG",
  description: "Knowledge Graph Explorer for Fiction Universes",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased bg-slate-950 text-slate-100 min-h-screen">
        <TooltipProvider>
          <Sidebar />
          <main className="md:ml-60 min-h-screen">
            <TopBar />
            <div className="p-6 lg:p-8">{children}</div>
          </main>
          <Toaster />
        </TooltipProvider>
      </body>
    </html>
  )
}
