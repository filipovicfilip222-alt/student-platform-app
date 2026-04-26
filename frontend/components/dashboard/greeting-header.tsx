/**
 * greeting-header.tsx — Vremenski-zavisan pozdrav za sve dashboard stranice.
 *
 * Renders:
 *   "Dobro jutro/dan/veče, {firstName}"  (text-3xl font-bold)
 *   "Nedelja, 27. april 2026."          (text-sm muted)
 *
 * Interna granica:
 *   00–11 → jutro
 *   12–17 → dan
 *   18–23 → veče
 *
 * Datum se izračunava jednom na mount-u — ne ažurira se ako otvoreni tab
 * pređe ponoć (low-priority edge case; drift od max 1 dana se rešava
 * SPA navigacijom). Ako bismo hteli auto-refresh, koristili bismo
 * `setInterval` na poll.
 *
 * Renderuje opcioni `actions` slot (npr. "Zakaži nove konsultacije" CTA).
 */

"use client"

import { format } from "date-fns"
import { sr } from "date-fns/locale"
import { useEffect, useMemo, useState } from "react"

import { cn } from "@/lib/utils"

export interface GreetingHeaderProps {
  /** First name to address; falls back to neutral salutation. */
  firstName?: string | null
  /** Override the salutation noun (e.g. "kolega", "profesore"). */
  fallbackName?: string
  /** Optional subtitle override. Default = today's date in sr-Latn long form. */
  subtitle?: string
  /** Right-side slot for primary CTA. */
  actions?: React.ReactNode
  className?: string
}

function getTimeBucket(hours: number): "jutro" | "dan" | "veče" {
  if (hours < 12) return "jutro"
  if (hours < 18) return "dan"
  return "veče"
}

function formatLongDate(date: Date): string {
  // date-fns sr locale već daje srpsku latinicu sa malim slovima dana —
  // ručno kapitalizujemo prvo slovo (Nedelja, Ponedeljak, ...).
  const formatted = format(date, "EEEE, d. MMMM yyyy.", { locale: sr })
  return formatted.charAt(0).toUpperCase() + formatted.slice(1)
}

export function GreetingHeader({
  firstName,
  fallbackName = "korisniče",
  subtitle,
  actions,
  className,
}: GreetingHeaderProps) {
  // Avoid SSR/CSR mismatch on time-of-day:
  // server renders neutral "Pozdrav", client hydrates to actual bucket.
  const [now, setNow] = useState<Date | null>(null)

  useEffect(() => {
    setNow(new Date())
  }, [])

  const greeting = useMemo(() => {
    if (!now) return "Pozdrav"
    const bucket = getTimeBucket(now.getHours())
    return `Dobro ${bucket}`
  }, [now])

  const dateLine = useMemo(() => {
    if (subtitle) return subtitle
    if (!now) return null
    return formatLongDate(now)
  }, [now, subtitle])

  const name = firstName?.trim() || fallbackName

  return (
    <header
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className
      )}
    >
      <div className="space-y-1.5">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          {greeting}, <span className="text-primary">{name}</span>
        </h1>
        {dateLine && (
          <p className="text-sm text-muted-foreground">{dateLine}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  )
}
