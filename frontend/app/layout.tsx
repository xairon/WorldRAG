import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Network } from "lucide-react";
import { BookOpen, MessageSquare, LayoutDashboard } from "lucide-react";
import NavLink from "@/components/NavLink";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "WorldRAG",
  description: "Knowledge Graph Explorer for Fiction Universes",
};

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/books", label: "Books", icon: BookOpen },
  { href: "/graph", label: "Graph Explorer", icon: Network },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-slate-950 text-slate-100 min-h-screen`}
      >
        {/* Sidebar — hidden on mobile */}
        <aside className="fixed left-0 top-0 z-40 h-screen w-60 border-r border-slate-800 bg-slate-950/80 backdrop-blur-xl hidden md:block">
          <div className="flex h-16 items-center gap-2 px-5 border-b border-slate-800">
            <Network className="h-6 w-6 text-indigo-400" />
            <span className="text-lg font-bold tracking-tight">
              World<span className="text-indigo-400">RAG</span>
            </span>
          </div>

          <nav aria-label="Main navigation" className="mt-4 flex flex-col gap-1 px-3">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <NavLink key={href} href={href}>
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="absolute bottom-4 left-0 right-0 px-5">
            <div className="rounded-lg bg-slate-900/50 border border-slate-800 p-3 text-xs text-slate-500">
              <div className="font-medium text-slate-400 mb-1">WorldRAG v0.1</div>
              KG Construction System
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="md:ml-60 min-h-screen">
          <div className="p-6 lg:p-8">{children}</div>
        </main>
      </body>
    </html>
  );
}
