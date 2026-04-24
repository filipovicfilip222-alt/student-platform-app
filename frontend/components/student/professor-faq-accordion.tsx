/**
 * professor-faq-accordion.tsx — FAQ rendered above the booking calendar.
 *
 * ROADMAP 3.5 / Faza 3.5. The PRD mandates that FAQ is placed **above**
 * the calendar so students self-serve common questions before booking.
 */

import { HelpCircle } from "lucide-react"

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { FaqResponse } from "@/types"

export interface ProfessorFaqAccordionProps {
  faq: FaqResponse[]
}

export function ProfessorFaqAccordion({ faq }: ProfessorFaqAccordionProps) {
  const sorted = [...faq].sort((a, b) => a.sort_order - b.sort_order)

  if (sorted.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader className="p-5 pb-2">
        <CardTitle className="inline-flex items-center gap-2 text-base font-semibold">
          <HelpCircle className="size-4 text-muted-foreground" aria-hidden />
          Često postavljena pitanja
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5 pt-0">
        <Accordion type="single" collapsible className="divide-y">
          {sorted.map((item) => (
            <AccordionItem key={item.id} value={item.id}>
              <AccordionTrigger className="pr-2 text-sm">
                {item.question}
              </AccordionTrigger>
              <AccordionContent>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {item.answer}
                </p>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  )
}
