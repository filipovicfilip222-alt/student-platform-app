/**
 * quick-actions-grid.tsx — Grid od 4-6 ikon-CTA kartica za dashboard.
 *
 * Generic — primalac (student / profesor / admin dashboard) prosleđuje
 * svoju listu actions. Svaka stavka renderuje kao Link sa hover-lift i
 * subtilnom burgundy shadow tint-om.
 *
 * A11y: cela kartica je `<Link>` sa fokus ringom; ikona je dekorativna
 * (`aria-hidden`).
 */

import Link from "next/link"
import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/utils"

export interface QuickAction {
  href: string
  title: string
  description: string
  icon: LucideIcon
  /** Optional accent (e.g. "fon"|"etf") — drives the icon halo color. */
  tone?: "primary" | "accent" | "info" | "success"
}

export interface QuickActionsGridProps {
  actions: QuickAction[]
  className?: string
  /** Override grid columns; default = `2 sm:3 lg:4`. */
  cols?: string
}

const TONE_STYLES: Record<NonNullable<QuickAction["tone"]>, string> = {
  primary: "bg-primary/10 text-primary",
  accent: "bg-accent/15 text-accent-foreground dark:text-accent",
  info: "bg-info/10 text-info",
  success: "bg-success/10 text-success",
}

export function QuickActionsGrid({
  actions,
  className,
  cols = "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4",
}: QuickActionsGridProps) {
  return (
    <div className={cn("grid gap-3", cols, className)}>
      {actions.map(({ href, title, description, icon: Icon, tone = "primary" }) => (
        <Link
          key={href + title}
          href={href}
          className="group relative flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-[0_4px_16px_-4px_hsl(var(--primary)/0.18)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <span
            className={cn(
              "flex size-10 items-center justify-center rounded-lg transition-transform group-hover:scale-110",
              TONE_STYLES[tone]
            )}
            aria-hidden
          >
            <Icon className="size-5" />
          </span>
          <div className="space-y-0.5">
            <p className="text-sm font-semibold text-foreground group-hover:text-primary">
              {title}
            </p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </Link>
      ))}
    </div>
  )
}
