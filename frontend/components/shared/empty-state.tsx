/**
 * empty-state.tsx — "No data" placeholder used by lists and tables.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * Accepts a lucide icon component so feature pages can stay expressive
 * (e.g. <Inbox /> for an empty inbox, <CalendarX /> for empty calendar).
 */

import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export interface EmptyStateProps {
  title: string
  description?: string
  icon?: LucideIcon
  /** Optional CTA (e.g. a <Button>). */
  action?: ReactNode
  className?: string
}

export function EmptyState({
  title,
  description,
  icon: Icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-12 text-center",
        className
      )}
      role="status"
    >
      {Icon && (
        <div className="flex size-12 items-center justify-center rounded-full bg-background text-muted-foreground ring-1 ring-border">
          <Icon className="size-6" aria-hidden />
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && (
          <p className="max-w-md text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}
