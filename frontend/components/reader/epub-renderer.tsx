"use client"

// SECURITY: All epub XHTML is sanitized through DOMPurify before any DOM insertion.
// DOMPurify strips all scripts, event handlers, and unsafe attributes.
// This is the industry-standard approach for rendering user-provided HTML safely.
// See: https://github.com/cure53/DOMPurify

import { useEffect, useRef, useCallback, useState } from "react"
import DOMPurify from "dompurify"
import { createPortal } from "react-dom"
import { labelColor } from "@/lib/utils"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { EntityBadge } from "@/components/shared/entity-badge"
import { CharacterHoverContent } from "@/components/reader/character-hover-content"
import type { EntityAnnotation } from "@/lib/api/reader"
import type { ReaderTheme } from "@/hooks/use-reader-settings"
import { THEME_STYLES } from "@/hooks/use-reader-settings"
import "./epub-reader.css"

interface EpubRendererProps {
  xhtml: string
  css: string
  annotations: EntityAnnotation[]
  showAnnotations: boolean
  theme: ReaderTheme
  fontSize: number
  lineHeight: number
  fontFamily: "serif" | "sans"
  bookId?: string
  chapter?: number
}

/**
 * Sanitize XHTML from epub using DOMPurify (XSS protection).
 * Allows safe structural tags/classes, strips scripts and event handlers.
 */
function sanitizeHTML(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "p", "div", "span", "br", "hr", "a",
      "b", "strong", "i", "em", "u", "s", "small", "sub", "sup",
      "h1", "h2", "h3", "h4", "h5", "h6",
      "ul", "ol", "li", "dl", "dt", "dd",
      "blockquote", "pre", "code",
      "table", "thead", "tbody", "tr", "th", "td",
      "img", "figure", "figcaption",
      "section", "article", "aside", "header", "footer",
      "ruby", "rt", "rp",
    ],
    ALLOWED_ATTR: [
      "class", "id", "href", "src", "alt", "title",
      "colspan", "rowspan", "width", "height",
      "role", "lang",
    ],
    ALLOW_DATA_ATTR: false,
  })
}

/**
 * Safely set sanitized HTML content on an element.
 * DOMPurify has already stripped all dangerous content.
 */
function setSanitizedContent(element: HTMLElement, sanitizedHTML: string): void {
  // Clear existing content
  while (element.firstChild) {
    element.removeChild(element.firstChild)
  }
  // Parse sanitized HTML and append nodes
  const template = document.createElement("template")
  template.innerHTML = sanitizedHTML
  element.appendChild(template.content.cloneNode(true))
}

/**
 * Normalize text for matching: replace typographic quotes with straight ones,
 * collapse whitespace. Epub XHTML uses smart quotes while extraction uses straight.
 */
function normalizeForSearch(text: string): string {
  return text
    .replace(/[\u2018\u2019\u201A\u201B]/g, "'")  // smart single quotes → straight
    .replace(/[\u2013\u2014]/g, "-")               // en/em dash → hyphen
    .replace(/[\u00A0]/g, " ")                      // nbsp → space
}

/**
 * Classify system messages (.cita / .lettre) by content pattern.
 * Adds data-system-type attribute for CSS-based visual differentiation.
 */
function classifySystemMessages(container: HTMLElement): void {
  const rules: [string, RegExp][] = [
    ["level-up",        /DING/],
    ["xp-kill",         /Vous avez terrassé/],
    ["title-award",     /Titre décerné/i],
    ["skill-acquired",  /Compétence acquise/i],
    ["skill-available", /Compétences? de classe.*disponibles?/i],
    ["bloodline",       /[Ll]ignée/],
    ["evolution",       /[Éé]volution|évoluer/i],
    ["profession",      /profession/i],
    ["quest",           /[Oo]bjectif|[Dd]onjon|[Qq]uête|tutoriel.*[Dd]urée/],
    ["item-desc",       /^\s*\[.+?\(.+?\)\]\s*[–—-]/],
    ["system-speech",   /Bienvenue|Félicitations|Initiation|Chargement/i],
  ]

  container.querySelectorAll<HTMLElement>(".cita").forEach((el) => {
    const text = el.textContent || ""
    for (const [type, pattern] of rules) {
      if (pattern.test(text)) {
        el.dataset.systemType = type
        return
      }
    }
    el.dataset.systemType = "system-generic"
  })

  // Stat blocks are already .lettre, but tag them for consistency
  container.querySelectorAll<HTMLElement>(".lettre").forEach((el) => {
    el.dataset.systemType = "stat-block"
  })
}

/**
 * Walk DOM text nodes and inject annotation highlights.
 * Uses text-based matching (extraction_text) because paragraph char offsets
 * don't match XHTML DOM text offsets (different whitespace, smart quotes, etc.).
 */
function injectAnnotations(
  container: HTMLElement,
  annotations: EntityAnnotation[],
  theme: ReaderTheme,
): void {
  if (annotations.length === 0) return

  // Build full text from DOM text nodes
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  const textNodes: { node: Text; start: number; end: number }[] = []
  let fullText = ""

  let node = walker.nextNode() as Text | null
  while (node) {
    const text = node.textContent || ""
    if (text.length > 0) {
      textNodes.push({ node, start: fullText.length, end: fullText.length + text.length })
      fullText += text
    }
    node = walker.nextNode() as Text | null
  }

  if (textNodes.length === 0) return

  const t = THEME_STYLES[theme]

  // Normalized DOM text for searching (handles smart quotes, dashes, etc.)
  const normalizedFullText = normalizeForSearch(fullText)

  // Group annotations by extraction_text to match sequential occurrences
  const groups = new Map<string, EntityAnnotation[]>()
  for (const ann of annotations) {
    const key = ann.extraction_text || ann.entity_name
    if (!key || key.length < 2) continue
    const existing = groups.get(key)
    if (existing) existing.push(ann)
    else groups.set(key, [ann])
  }

  // For each group, find all occurrences in DOM text and pair with annotations
  interface DomMatch { domStart: number; domEnd: number; annotation: EntityAnnotation }
  const matches: DomMatch[] = []

  for (const [searchText, anns] of groups) {
    // Sort annotations by original offset
    anns.sort((a, b) => a.char_offset_start - b.char_offset_start)

    // Normalize search text to match DOM text (smart quotes → straight, etc.)
    const normalizedSearch = normalizeForSearch(searchText)

    // For very long extraction texts (>80 chars), use first 60 chars to locate
    // then highlight the full length. This avoids issues with truncation.
    const searchKey = normalizedSearch.length > 80 ? normalizedSearch.slice(0, 60) : normalizedSearch
    const highlightLen = normalizedSearch.length > 80 ? normalizedSearch.length : searchText.length

    // Find all occurrences in normalized DOM text
    const occurrences: number[] = []
    let pos = 0
    while ((pos = normalizedFullText.indexOf(searchKey, pos)) !== -1) {
      occurrences.push(pos)
      pos += searchKey.length
    }

    // Pair annotations with occurrences sequentially
    const count = Math.min(anns.length, occurrences.length)
    for (let i = 0; i < count; i++) {
      matches.push({
        domStart: occurrences[i],
        domEnd: occurrences[i] + highlightLen,
        annotation: anns[i],
      })
    }
  }

  // Sort matches by DOM position (reverse for safe DOM manipulation)
  matches.sort((a, b) => b.domStart - a.domStart)

  // Inject highlights in reverse order (avoids offset shifts)
  for (const m of matches) {
    const ann = m.annotation
    const color = labelColor(ann.entity_type)

    // Find the text node containing the start of this match
    for (const tn of textNodes) {
      if (tn.end <= m.domStart || tn.start >= m.domEnd) continue

      const sliceStart = Math.max(0, m.domStart - tn.start)
      const sliceEnd = Math.min(tn.node.textContent!.length, m.domEnd - tn.start)
      if (sliceStart >= sliceEnd) continue

      const nodeText = tn.node.textContent!
      const before = nodeText.slice(0, sliceStart)
      const matched = nodeText.slice(sliceStart, sliceEnd)
      const after = nodeText.slice(sliceEnd)

      const parent = tn.node.parentNode
      if (!parent) continue

      const fragment = document.createDocumentFragment()
      if (before) fragment.appendChild(document.createTextNode(before))

      const mark = document.createElement("mark")
      mark.className = "entity-highlight"
      mark.textContent = matched
      mark.dataset.entityName = ann.entity_name
      mark.dataset.entityType = ann.entity_type
      mark.dataset.mentionType = ann.mention_type || "langextract"
      mark.dataset.extractionText = (ann.extraction_text || "").slice(0, 200)

      const underlineStyle = ann.mention_type === "alias" ? "dashed"
        : ann.mention_type === "pronoun" ? "dotted" : "solid"

      mark.style.setProperty("background-color", `${color}${t.annotationBgOpacity}`)
      mark.style.setProperty("border-bottom", `2px ${underlineStyle} ${color}${t.annotationBorderOpacity}`)

      fragment.appendChild(mark)
      if (after) fragment.appendChild(document.createTextNode(after))

      parent.replaceChild(fragment, tn.node)
      break
    }
  }
}

function AnnotationPopover({
  anchor,
  entityName,
  entityType,
  mentionType,
  extractionText,
  bookId,
  chapter,
}: {
  anchor: HTMLElement
  entityName: string
  entityType: string
  mentionType: string
  extractionText: string
  bookId?: string
  chapter?: number
}) {
  const isCharacter = entityType === "Character"

  return createPortal(
    <HoverCard open={true}>
      <HoverCardTrigger asChild>
        <span
          style={{
            position: "fixed",
            left: anchor.getBoundingClientRect().left,
            top: anchor.getBoundingClientRect().top,
            width: anchor.getBoundingClientRect().width,
            height: anchor.getBoundingClientRect().height,
            pointerEvents: "none",
          }}
        />
      </HoverCardTrigger>
      <HoverCardContent
        side="top"
        align="start"
        className="w-64 p-3 space-y-2"
      >
        {isCharacter ? (
          <CharacterHoverContent
            characterName={entityName}
            bookId={bookId}
            chapter={chapter}
          />
        ) : (
          <>
            <div className="flex items-center gap-2">
              <EntityBadge name={entityName} type={entityType} size="sm" />
            </div>
            {mentionType && mentionType !== "langextract" && (
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                {mentionType.replace("_", " ")}
              </span>
            )}
            {extractionText && (
              <p className="text-xs text-slate-500 leading-relaxed line-clamp-3">
                {extractionText}
              </p>
            )}
          </>
        )}
      </HoverCardContent>
    </HoverCard>,
    document.body,
  )
}

export function EpubRenderer({
  xhtml,
  css,
  annotations,
  showAnnotations,
  theme,
  fontSize,
  lineHeight,
  fontFamily,
  bookId,
  chapter,
}: EpubRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoveredEntity, setHoveredEntity] = useState<{
    anchor: HTMLElement
    entityName: string
    entityType: string
    mentionType: string
    extractionText: string
  } | null>(null)

  const t = THEME_STYLES[theme]
  const font = fontFamily === "serif"
    ? '"Literata", "Georgia", "Cambria", "Times New Roman", serif'
    : '"Inter", system-ui, -apple-system, sans-serif'

  // DOMPurify sanitizes all epub XHTML (XSS protection)
  const sanitizedHTML = sanitizeHTML(xhtml)

  const cssVars = {
    "--reader-text": t.text,
    "--reader-heading": t.heading,
    "--reader-bg": t.bg,
    "--reader-text-muted": t.textMuted,
    "--reader-surface": t.surface,
    "--reader-border": t.border,
    "--reader-speaker": t.speaker,
    "--reader-bluebox-border": t.bluebox.border,
    "--reader-bluebox-bg": t.bluebox.bg,
    "--reader-bluebox-text": t.bluebox.text,
    "--reader-bluebox-corner": t.bluebox.corner,
    "--reader-bluebox-glow": `${t.bluebox.border}15`,
    "--reader-scene-break": t.sceneBreak,
    "--reader-select-bg": t.selectBg,
    "--reader-font-size": `${fontSize}px`,
    "--reader-line-height": String(lineHeight),
  } as React.CSSProperties

  // Inject sanitized HTML, classify system messages, and add annotations
  useEffect(() => {
    if (!containerRef.current) return
    setSanitizedContent(containerRef.current, sanitizedHTML)
    classifySystemMessages(containerRef.current)
    if (showAnnotations && annotations.length > 0) {
      injectAnnotations(containerRef.current, annotations, theme)
    }
  }, [sanitizedHTML, annotations, showAnnotations, theme])

  // Delegated event listeners for hover cards
  const handleMouseEnter = useCallback((e: MouseEvent) => {
    const mark = (e.target as HTMLElement).closest("mark.entity-highlight") as HTMLElement | null
    if (!mark) return
    setHoveredEntity({
      anchor: mark,
      entityName: mark.dataset.entityName || "",
      entityType: mark.dataset.entityType || "",
      mentionType: mark.dataset.mentionType || "",
      extractionText: mark.dataset.extractionText || "",
    })
  }, [])

  const handleMouseLeave = useCallback((e: MouseEvent) => {
    const mark = (e.target as HTMLElement).closest("mark.entity-highlight")
    if (!mark) return
    setTimeout(() => setHoveredEntity(null), 200)
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    el.addEventListener("mouseenter", handleMouseEnter, true)
    el.addEventListener("mouseleave", handleMouseLeave, true)
    return () => {
      el.removeEventListener("mouseenter", handleMouseEnter, true)
      el.removeEventListener("mouseleave", handleMouseLeave, true)
    }
  }, [handleMouseEnter, handleMouseLeave])

  // Scope epub CSS under .epub-content
  const scopedCSS = css
    ? css.replace(
        /([^\n{}@]+)\{/g,
        (match, selector: string) => {
          const trimmed = selector.trim()
          if (trimmed.startsWith("@") || !trimmed) return match
          const scoped = trimmed
            .split(",")
            .map((s: string) => `.epub-content ${s.trim()}`)
            .join(", ")
          return `${scoped} {`
        },
      )
    : ""

  return (
    <>
      {scopedCSS && <style>{scopedCSS}</style>}

      <div
        ref={containerRef}
        className="epub-content"
        style={{
          ...cssVars,
          fontSize: `${fontSize}px`,
          lineHeight,
          fontFamily: font,
          color: t.text,
        }}
      />

      {hoveredEntity && (
        <AnnotationPopover
          anchor={hoveredEntity.anchor}
          entityName={hoveredEntity.entityName}
          entityType={hoveredEntity.entityType}
          mentionType={hoveredEntity.mentionType}
          extractionText={hoveredEntity.extractionText}
          bookId={bookId}
          chapter={chapter}
        />
      )}
    </>
  )
}
