import type { Metadata } from "next"
import { ThemeProvider } from "next-themes"
import { NuqsAdapter } from "nuqs/adapters/next/app"
import { Toaster } from "@/components/ui/sonner"
import { Providers } from "@/lib/query-client"
import "./globals.css"

export const metadata: Metadata = {
  title: "WorldRAG",
  description: "Knowledge Graph construction for fiction universes",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-background text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
          <NuqsAdapter>
            <Providers>
              {children}
              <Toaster />
            </Providers>
          </NuqsAdapter>
        </ThemeProvider>
      </body>
    </html>
  )
}
