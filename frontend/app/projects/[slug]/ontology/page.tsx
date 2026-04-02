"use client"

import { use } from "react"
import { OntologyPageContent } from "@/components/ontology/ontology-page-content"

export default function OntologyPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = use(params)
  return (
    <div className="container max-w-6xl py-8">
      <OntologyPageContent slug={slug} />
    </div>
  )
}
