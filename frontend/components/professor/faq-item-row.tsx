/**
 * faq-item-row.tsx — Single row in the professor's FAQ list.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Includes inline up/down buttons for
 * re-ordering (dispatched via parent — parent calls updateFaq with a new
 * sort_order) instead of a full DnD library, plus Edit / Delete actions.
 */

"use client"

import { ArrowDown, ArrowUp, Pencil, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { FaqResponse } from "@/types"

export interface FaqItemRowProps {
  faq: FaqResponse
  isFirst: boolean
  isLast: boolean
  disabled?: boolean
  onMoveUp: () => void
  onMoveDown: () => void
  onEdit: () => void
  onDelete: () => void
}

export function FaqItemRow({
  faq,
  isFirst,
  isLast,
  disabled,
  onMoveUp,
  onMoveDown,
  onEdit,
  onDelete,
}: FaqItemRowProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border bg-card p-3">
      <div className="flex shrink-0 flex-col gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Pomeri gore"
          onClick={onMoveUp}
          disabled={disabled || isFirst}
        >
          <ArrowUp aria-hidden />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Pomeri dole"
          onClick={onMoveDown}
          disabled={disabled || isLast}
        >
          <ArrowDown aria-hidden />
        </Button>
      </div>

      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium text-sm text-foreground">{faq.question}</p>
        <p className="whitespace-pre-line text-sm text-muted-foreground">
          {faq.answer}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Izmeni FAQ"
          onClick={onEdit}
          disabled={disabled}
        >
          <Pencil aria-hidden />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Obriši FAQ"
          onClick={onDelete}
          disabled={disabled}
        >
          <Trash2 aria-hidden className="text-destructive" />
        </Button>
      </div>
    </div>
  )
}
