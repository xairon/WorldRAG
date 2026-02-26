import useSWR from "swr"
import { getCharacterStateAt, getCharacterSummary } from "@/lib/api/characters"
import type { CharacterStateSnapshot, CharacterSummary } from "@/lib/api/characters"

type StateKey = [string, string, string, number]
type SummaryKey = [string, string, string | null | undefined, number | null | undefined]

export function useCharacterState(
  name: string | null,
  bookId: string | null,
  chapter: number | null,
) {
  return useSWR<CharacterStateSnapshot, Error, StateKey | null>(
    name && bookId && chapter ? ["character-state", name, bookId, chapter] : null,
    ([, n, b, c]) => getCharacterStateAt(n, c, b),
    { keepPreviousData: true },
  )
}

export function useCharacterSummary(
  name: string | null,
  bookId?: string | null,
  chapter?: number | null,
) {
  return useSWR<CharacterSummary, Error, SummaryKey | null>(
    name ? ["character-summary", name, bookId, chapter] : null,
    ([, n, b, c]) => getCharacterSummary(n, { bookId: b ?? undefined, chapter: c ?? undefined }),
    { dedupingInterval: 10000 },
  )
}
