/**
 * empty-state.tsx — "Nema podataka" placeholder za liste i tabele.
 *
 * ROADMAP 2.2 — shared shell primitives.
 * KORAK 8 (StudentPlus polish): dodali smo `tone` prop koji menja boju
 * ikona-circle-a (default neutral / primary burgundy / accent amber).
 * Default tone je "primary" jer u 90% slučajeva želimo brand-tone empty
 * state-ove (lepše izgleda nego siv pravougaonik).
 *
 * Primer:
 *   <EmptyState
 *     icon={Inbox}
 *     title="Nemate termine"
 *     description="Kada zakažete termin, on će se pojaviti ovde."
 *     action={<Button>Zakaži termin</Button>}
 *   />
 */

import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export type EmptyStateTone = "default" | "primary" | "accent"

const TONE_CLASSES: Record<EmptyStateTone, string> = {
  default: "bg-muted text-muted-foreground",
  primary: "bg-primary/10 text-primary",
  accent: "bg-accent/15 text-accent-foreground",
}

export interface EmptyStateProps {
  title: string
  description?: string
  icon?: LucideIcon
  /** Tone of the icon circle. Default `primary` for brand consistency. */
  tone?: EmptyStateTone
  /** Optional CTA (e.g. a `<Button>`). */
  action?: ReactNode
  /** Use a flatter style without dashed border (e.g. inside cards). */
  embedded?: boolean
  className?: string
}

export function EmptyState({
  title,
  description,
  icon: Icon,
  tone = "primary",
  action,
  embedded = false,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-10 text-center",
        embedded
          ? "rounded-lg"
          : "rounded-xl border border-dashed border-border bg-muted/30",
        className
      )}
      role="status"
    >
      {Icon && (
        <div
          className={cn(
            "flex size-14 items-center justify-center rounded-full",
            TONE_CLASSES[tone]
          )}
        >
          <Icon className="size-6" aria-hidden />
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && (
          <p className="mx-auto max-w-md text-xs leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  )
}
