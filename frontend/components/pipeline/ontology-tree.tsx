"use client"

import { useMemo } from "react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { labelBadgeClass } from "@/lib/utils"
import type { OntologyNodeType, OntologyRelType } from "@/lib/api/pipeline"

interface OntologyTreeProps {
  nodeTypes: OntologyNodeType[]
  relTypes: OntologyRelType[]
}

const LAYER_LABELS: Record<string, string> = {
  core: "Layer 1 -- Core Narrative",
  litrpg: "Layer 2 -- LitRPG",
  primal_hunter: "Layer 3 -- Primal Hunter",
}

export function OntologyTree({ nodeTypes, relTypes }: OntologyTreeProps) {
  const layers = useMemo(() => {
    const result: Record<string, { nodes: OntologyNodeType[]; rels: OntologyRelType[] }> = {}
    for (const nt of nodeTypes) {
      if (!result[nt.layer]) result[nt.layer] = { nodes: [], rels: [] }
      result[nt.layer].nodes.push(nt)
    }
    for (const rt of relTypes) {
      if (!result[rt.layer]) result[rt.layer] = { nodes: [], rels: [] }
      result[rt.layer].rels.push(rt)
    }
    return result
  }, [nodeTypes, relTypes])

  return (
    <ScrollArea className="h-[65vh]">
      <Accordion type="multiple" defaultValue={Object.keys(layers)} className="space-y-2">
        {Object.entries(layers).map(([layer, { nodes, rels }]) => (
          <AccordionItem key={layer} value={layer} className="border border-[var(--glass-border)] rounded-lg px-4">
            <AccordionTrigger className="text-sm font-medium hover:no-underline">
              <div className="flex items-center gap-2">
                <span>{LAYER_LABELS[layer] ?? layer}</span>
                <Badge variant="secondary" className="text-[10px]">
                  {nodes.length} nodes
                </Badge>
                <Badge variant="outline" className="text-[10px]">
                  {rels.length} rels
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pb-2">
                {/* Node types */}
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                    Node Types
                  </h4>
                  <Accordion type="multiple" className="space-y-1">
                    {nodes.map((nt) => (
                      <AccordionItem
                        key={nt.name}
                        value={nt.name}
                        className="border border-[var(--glass-border)]/60 rounded-md px-3"
                      >
                        <AccordionTrigger className="text-xs hover:no-underline py-2">
                          <div className="flex items-center gap-2">
                            <Badge className={labelBadgeClass(nt.name)} variant="outline">
                              {nt.name}
                            </Badge>
                            <span className="text-muted-foreground">
                              {nt.properties.length} properties
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          {nt.properties.length > 0 ? (
                            <table className="w-full text-[11px] mb-2">
                              <thead>
                                <tr className="text-muted-foreground">
                                  <th className="text-left py-1 font-medium">Property</th>
                                  <th className="text-left py-1 font-medium">Type</th>
                                  <th className="text-center py-1 font-medium">Req</th>
                                  <th className="text-center py-1 font-medium">Unique</th>
                                  <th className="text-left py-1 font-medium">Values</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-[var(--glass-border)]">
                                {nt.properties.map((p) => (
                                  <tr key={p.name}>
                                    <td className="py-1 font-mono text-foreground">{p.name}</td>
                                    <td className="py-1 text-muted-foreground">{p.type}</td>
                                    <td className="py-1 text-center">{p.required ? "Y" : ""}</td>
                                    <td className="py-1 text-center">{p.unique ? "Y" : ""}</td>
                                    <td className="py-1 text-muted-foreground">
                                      {p.values?.join(", ") ?? ""}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : (
                            <p className="text-[11px] text-muted-foreground pb-2">No properties defined</p>
                          )}
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </div>

                {/* Relationship types */}
                {rels.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                      Relationship Types
                    </h4>
                    <div className="space-y-1">
                      {rels.map((rt) => (
                        <div
                          key={rt.name}
                          className="flex items-center gap-2 px-3 py-1.5 text-xs rounded-md bg-background"
                        >
                          <span className="font-mono text-cyan-400">{rt.name}</span>
                          <span className="text-muted-foreground/60">:</span>
                          <span className="text-muted-foreground">{rt.from_type || "*"}</span>
                          <span className="text-muted-foreground/60">&rarr;</span>
                          <span className="text-muted-foreground">{rt.to_type || "*"}</span>
                          {rt.properties.length > 0 && (
                            <span className="text-muted-foreground/60 ml-auto">
                              {rt.properties.map((p) => p.name).join(", ")}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </ScrollArea>
  )
}
