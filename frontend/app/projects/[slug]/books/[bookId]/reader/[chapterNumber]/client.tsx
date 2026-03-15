"use client"

import { EpubRenderer } from "@/components/reader/epub-renderer"

export function EpubReaderClient({ xhtml, css }: { xhtml: string; css: string }) {
  return <EpubRenderer xhtml={xhtml} css={css} />
}
