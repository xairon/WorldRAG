"use client"

import { useCallback } from "react"
import { useParams, useSearchParams, useRouter } from "next/navigation"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { useCharacterState } from "@/hooks/useCharacterState"
import { ChapterSlider } from "@/components/characters/chapter-slider"
import { CharacterHeader } from "@/components/characters/character-header"
import { StatGrid } from "@/components/characters/stat-grid"
import { SkillList } from "@/components/characters/skill-list"
import { ClassTimeline } from "@/components/characters/class-timeline"
import { EquipmentList } from "@/components/characters/equipment-list"
import { TitleList } from "@/components/characters/title-list"
import { ChangelogTab } from "@/components/characters/changelog-tab"

export default function CharacterSheetPage() {
  const params = useParams()
  const searchParams = useSearchParams()
  const router = useRouter()

  const name = params.name ? decodeURIComponent(params.name as string) : null
  const bookId = searchParams.get("book_id")
  const chapterParam = searchParams.get("chapter")
  const chapter = chapterParam ? parseInt(chapterParam, 10) : null

  const { data: snapshot, error, isLoading } = useCharacterState(
    name,
    bookId,
    chapter,
  )

  const handleChapterChange = useCallback(
    (newChapter: number) => {
      const nextParams = new URLSearchParams(searchParams.toString())
      nextParams.set("chapter", String(newChapter))
      router.replace(`?${nextParams.toString()}`)
    },
    [router, searchParams],
  )

  // Missing required params
  if (!name || !bookId || chapter === null || isNaN(chapter)) {
    return (
      <div className="space-y-6">
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-8 text-center">
          <p className="text-amber-400 text-sm">
            Missing required parameters. Navigate to a character from the graph or search.
          </p>
          <p className="text-slate-500 text-xs mt-2">
            Required: name (path), book_id, chapter (query params)
          </p>
        </div>
      </div>
    )
  }

  // Loading state
  if (isLoading && !snapshot) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-10 w-96" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
          <p className="text-red-400 text-sm">{error.message}</p>
        </div>
      </div>
    )
  }

  if (!snapshot) return null

  return (
    <ScrollArea className="h-[calc(100vh-5rem)]">
      <div className="space-y-6 pb-12">
        {/* Chapter Slider */}
        <ChapterSlider
          chapter={snapshot.as_of_chapter}
          totalChapters={snapshot.total_chapters_in_book}
          onChange={handleChapterChange}
        />

        {/* Character Header */}
        <CharacterHeader snapshot={snapshot} />

        {/* Tabs */}
        <Tabs defaultValue="stats">
          <TabsList className="bg-slate-900/50 border border-slate-800 rounded-lg">
            <TabsTrigger value="stats" className="text-xs">
              Stats
              {snapshot.stats.length > 0 && (
                <span className="ml-1 text-slate-600 font-mono">
                  {snapshot.stats.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="skills" className="text-xs">
              Skills
              {snapshot.skills.length > 0 && (
                <span className="ml-1 text-slate-600 font-mono">
                  {snapshot.skills.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="classes" className="text-xs">
              Classes
              {snapshot.classes.length > 0 && (
                <span className="ml-1 text-slate-600 font-mono">
                  {snapshot.classes.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="equipment" className="text-xs">
              Equipment
              {snapshot.items.length > 0 && (
                <span className="ml-1 text-slate-600 font-mono">
                  {snapshot.items.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="titles" className="text-xs">
              Titles
              {snapshot.titles.length > 0 && (
                <span className="ml-1 text-slate-600 font-mono">
                  {snapshot.titles.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="changelog" className="text-xs">
              Changelog
              {snapshot.chapter_changes.length > 0 && (
                <span className="ml-1 text-slate-600 font-mono">
                  {snapshot.chapter_changes.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="stats" className="mt-4">
            <StatGrid
              stats={snapshot.stats}
              chapterChanges={snapshot.chapter_changes}
            />
          </TabsContent>

          <TabsContent value="skills" className="mt-4">
            <SkillList skills={snapshot.skills} />
          </TabsContent>

          <TabsContent value="classes" className="mt-4">
            <ClassTimeline classes={snapshot.classes} />
          </TabsContent>

          <TabsContent value="equipment" className="mt-4">
            <EquipmentList items={snapshot.items} />
          </TabsContent>

          <TabsContent value="titles" className="mt-4">
            <TitleList titles={snapshot.titles} />
          </TabsContent>

          <TabsContent value="changelog" className="mt-4">
            <ChangelogTab changes={snapshot.chapter_changes} />
          </TabsContent>
        </Tabs>
      </div>
    </ScrollArea>
  )
}
