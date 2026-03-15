"use client"

// SECURITY: All epub XHTML is sanitized through DOMPurify before any DOM insertion.
// DOMPurify strips all scripts, event handlers, and unsafe attributes.
// This is the industry-standard approach for rendering user-provided HTML safely.
// See: https://github.com/cure53/DOMPurify

import { useEffect, useRef } from "react"
import DOMPurify from "dompurify"
import "./epub-reader.css"

interface EpubRendererProps {
  xhtml: string
  css: string
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
 * Safely inject DOMPurify-sanitized HTML into a container element.
 * Uses template element parsing (no eval, no inline scripts possible
 * after DOMPurify sanitization).
 */
function setSanitizedContent(element: HTMLElement, sanitizedHTML: string): void {
  const template = document.createElement("template")
  template.innerHTML = sanitizedHTML  // Safe: already sanitized by DOMPurify
  element.replaceChildren(template.content.cloneNode(true))
}

/** Classify system messages (.cita / .lettre) by content pattern */
function classifySystemMessages(container: HTMLElement): void {
  const rules: [string, RegExp][] = [
    ["level-up", /DING/],
    ["xp-kill", /Vous avez terrassé/],
    ["title-award", /Titre décerné/i],
    ["skill-acquired", /Compétence acquise/i],
    ["skill-available", /Compétences? de classe.*disponibles?/i],
    ["bloodline", /[Ll]ignée/],
    ["evolution", /[Éé]volution|évoluer/i],
    ["profession", /profession/i],
    ["quest", /[Oo]bjectif|[Dd]onjon|[Qq]uête|tutoriel.*[Dd]urée/],
    ["item-desc", /^\s*\[.+?\(.+?\)\]\s*[–—-]/],
    ["system-speech", /Bienvenue|Félicitations|Initiation|Chargement/i],
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

  container.querySelectorAll<HTMLElement>(".lettre").forEach((el) => {
    el.dataset.systemType = "stat-block"
  })
}

export function EpubRenderer({ xhtml, css }: EpubRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const sanitizedHTML = sanitizeHTML(xhtml)

  // Scope epub CSS under .epub-content to avoid leaking styles
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

  useEffect(() => {
    if (!containerRef.current) return
    setSanitizedContent(containerRef.current, sanitizedHTML)
    classifySystemMessages(containerRef.current)
  }, [sanitizedHTML])

  return (
    <>
      {scopedCSS && <style>{scopedCSS}</style>}
      <div
        ref={containerRef}
        className="epub-content prose prose-lg dark:prose-invert max-w-none"
        style={{
          fontFamily: '"Literata", "Georgia", "Cambria", "Times New Roman", serif',
          fontSize: "18px",
          lineHeight: 1.8,
        }}
      />
    </>
  )
}
