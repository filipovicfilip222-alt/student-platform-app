/**
 * error-state.tsx — Friendly inline error placeholder.
 *
 * KORAK 8 — komponenta koja standardizuje "data fetch failed" tipove
 * stanja (npr. mutirani upit, 500-tice, network errors). Konzistentna sa
 * `<EmptyState />` po layoutu — ikona-circle u destructive tonu, naslov,
 * opciono optional description + retry CTA.
 *
 * Default-i:
 *   - icon: AlertTriangle
 *   - title: "Nešto je pošlo po zlu"
 *   - description: friendly prevod technical greške koju ne pokazujemo.
 *   - onRetry: ako je prosleđeno — renderujemo "Pokušaj ponovo" button.
 */

"use client"

import { AlertTriangle, RefreshCw } from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface ErrorStateProps {
  title?: string
  description?: string
  icon?: LucideIcon
  onRetry?: () => void
  isRetrying?: boolean
  embedded?: boolean
  className?: string
}

export function ErrorState({
  title = "Nešto je pošlo po zlu",
  description = "Pokušajte ponovo za par sekundi. Ako se problem ponovi, kontaktirajte podršku.",
  icon: Icon = AlertTriangle,
  onRetry,
  isRetrying = false,
  embedded = false,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-10 text-center",
        embedded
          ? "rounded-lg"
          : "rounded-xl border border-dashed border-destructive/40 bg-destructive/5",
        className
      )}
      role="alert"
    >
      <div className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <Icon className="size-6" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="mx-auto max-w-md text-xs leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          disabled={isRetrying}
          className="mt-1"
        >
          <RefreshCw
            className={cn(isRetrying && "animate-spin")}
            aria-hidden
          />
          Pokušaj ponovo
        </Button>
      )}
    </div>
  )
}
