"use client"

import { useParams } from "next/navigation"
import { OntologyDashboard } from "@/components/ontology/ontology-dashboard"

export default function OntologyPage() {
  const { slug } = useParams<{ slug: string }>()
  return <OntologyDashboard slug={slug} />
}
