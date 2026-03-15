import type { UIStatus } from "@/lib/constants"
import { ChapterRow } from "./chapter-row"

export interface ChapterData {
  number: number
  title: string
  words: number
  entityCount: number
  status: string
  entities: { type: string; count: number }[]
}

interface ChapterTableProps {
  chapters: ChapterData[]
}

export function ChapterTable({ chapters }: ChapterTableProps) {
  return (
    <div className="max-h-[500px] overflow-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
          <tr className="border-b text-left">
            <th className="px-3 py-2 font-medium text-muted-foreground w-12">#</th>
            <th className="px-3 py-2 font-medium text-muted-foreground">Chapter</th>
            <th className="px-3 py-2 font-medium text-muted-foreground text-right w-20">Words</th>
            <th className="px-3 py-2 font-medium text-muted-foreground text-right w-20">Entities</th>
            <th className="px-3 py-2 font-medium text-muted-foreground w-28">Status</th>
          </tr>
        </thead>
        <tbody>
          {chapters.map((chapter) => (
            <ChapterRow key={chapter.number} chapter={chapter} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
