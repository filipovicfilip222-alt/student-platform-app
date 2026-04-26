/**
 * password-strength-meter.tsx — Vizuelni feedback jačine lozinke.
 *
 * Skeleton:
 *   [▓▓▓░░░░░░░] 4-segment bar + tekstualna poruka + opciono prvi feedback iz zxcvbn-ts.
 *
 * Bundle-size protokol:
 *   `@zxcvbn-ts/language-common` sadrži ~700KB dictionary fajlova (10k
 *   common passwords + adjacency graphs). Ako bismo importovali static-no,
 *   register/reset-password bi naduvali first-load JS sa 165KB → 968KB.
 *   Stoga radimo **lazy dynamic import** unutar `useEffect`-a:
 *
 *     - Glavni bundle ne sadrži zxcvbn (chunk se izdvaja).
 *     - Tek kad korisnik fokusira password polje i komponenta mount-uje,
 *       browser fetch-uje chunk u pozadini (typically 50-100ms).
 *     - Dok stigne, vizuelno renderujemo placeholder bar (neutralna
 *       muted boja); kad zxcvbn stigne, recompute trigger-uje real score.
 *
 * Accessibility: `role="meter"` + `aria-valuenow/min/max` da screen
 * reader-i čitaju "Jačina lozinke 3 od 4".
 */

"use client"

import { useEffect, useMemo, useState } from "react"

import { cn } from "@/lib/utils"

interface ZxcvbnRunner {
  (password: string): { score: 0 | 1 | 2 | 3 | 4; warning?: string; suggestions: string[] }
}

let runnerPromise: Promise<ZxcvbnRunner> | null = null

/**
 * Lazy-load zxcvbn-ts core + en/common dictionaries. Cached in module
 * scope tako da posle prvog renderovanja meter-a (npr. /register) nema
 * dodatnog mrežnog troška na /reset-password u istoj sesiji.
 */
function loadRunner(): Promise<ZxcvbnRunner> {
  if (runnerPromise) return runnerPromise
  runnerPromise = (async () => {
    const [{ zxcvbn, zxcvbnOptions }, common, en] = await Promise.all([
      import("@zxcvbn-ts/core"),
      import("@zxcvbn-ts/language-common"),
      import("@zxcvbn-ts/language-en"),
    ])
    zxcvbnOptions.setOptions({
      translations: en.translations,
      graphs: common.adjacencyGraphs,
      dictionary: { ...common.dictionary, ...en.dictionary },
    })
    return (password: string) => {
      const result = zxcvbn(password)
      return {
        score: result.score as 0 | 1 | 2 | 3 | 4,
        warning: result.feedback?.warning ?? undefined,
        suggestions: result.feedback?.suggestions ?? [],
      }
    }
  })()
  return runnerPromise
}

export interface PasswordStrengthMeterProps {
  password: string
  /** Hide visually when password is empty (default: true). */
  hideWhenEmpty?: boolean
  className?: string
}

interface Strength {
  score: 0 | 1 | 2 | 3 | 4
  label: string
  toneClass: string
  fillClass: string
  hint?: string
}

const STRENGTH_BY_SCORE: Record<0 | 1 | 2 | 3 | 4, Omit<Strength, "score">> = {
  0: {
    label: "Veoma slaba",
    toneClass: "text-destructive",
    fillClass: "bg-destructive",
  },
  1: {
    label: "Slaba",
    toneClass: "text-destructive",
    fillClass: "bg-destructive",
  },
  2: {
    label: "Osrednja",
    toneClass: "text-warning",
    fillClass: "bg-warning",
  },
  3: {
    label: "Jaka",
    toneClass: "text-success",
    fillClass: "bg-success",
  },
  4: {
    label: "Veoma jaka",
    toneClass: "text-success",
    fillClass: "bg-success",
  },
}

/** Map zxcvbn engleski feedback na sažet srpski hint. */
function translateHint(rawHint: string | undefined, suggestions: string[]): string | undefined {
  if (!rawHint && suggestions.length === 0) return undefined
  const merged = `${rawHint ?? ""} ${suggestions.join(" ")}`.toLowerCase()
  if (merged.includes("repeat")) return "Izbegavajte ponavljanje karaktera."
  if (merged.includes("sequence")) return "Izbegavajte sekvence (abc, 123)."
  if (merged.includes("common")) return "Lozinka je previše uobičajena."
  if (merged.includes("name") || merged.includes("surname"))
    return "Ne koristite ime/prezime u lozinci."
  if (merged.includes("date") || merged.includes("year"))
    return "Datumi su lako pogađljivi."
  if (merged.includes("dictionary")) return "Reč je u rečniku — dodajte simbole."
  if (merged.includes("longer") || merged.includes("length"))
    return "Dodajte još karaktera."
  return undefined
}

/**
 * Quick fallback skor pre nego što zxcvbn chunk stigne. Ne pokušavamo da
 * imitiramo entropiju — samo dužinu + raznovrsnost znakova.
 */
function quickEstimate(password: string): 0 | 1 | 2 | 3 | 4 {
  if (password.length < 6) return 0
  if (password.length < 8) return 1
  let variety = 0
  if (/[a-z]/.test(password)) variety++
  if (/[A-Z]/.test(password)) variety++
  if (/\d/.test(password)) variety++
  if (/[^A-Za-z0-9]/.test(password)) variety++
  if (variety <= 1) return 1
  if (variety === 2) return 2
  if (password.length >= 12) return 3
  return 2
}

export function PasswordStrengthMeter({
  password,
  hideWhenEmpty = true,
  className,
}: PasswordStrengthMeterProps) {
  const [runner, setRunner] = useState<ZxcvbnRunner | null>(null)

  useEffect(() => {
    let alive = true
    loadRunner()
      .then((r) => {
        if (alive) setRunner(() => r)
      })
      .catch(() => {
        // Tihi failure — meter ostaje na quick-estimate fallback-u.
      })
    return () => {
      alive = false
    }
  }, [])

  const strength = useMemo<Strength | null>(() => {
    if (!password) return null
    if (runner) {
      const result = runner(password)
      return {
        score: result.score,
        ...STRENGTH_BY_SCORE[result.score],
        hint: translateHint(result.warning, result.suggestions),
      }
    }
    const score = quickEstimate(password)
    return { score, ...STRENGTH_BY_SCORE[score] }
  }, [password, runner])

  if (!password && hideWhenEmpty) return null

  const score = strength?.score ?? 0
  const label = strength?.label ?? "Unesite lozinku"
  const toneClass = strength?.toneClass ?? "text-muted-foreground"
  const fillClass = strength?.fillClass ?? "bg-muted"
  const filledSegments = strength ? Math.max(1, score) : 0

  return (
    <div
      className={cn("space-y-1.5", className)}
      role="meter"
      aria-label="Jačina lozinke"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={4}
      aria-valuetext={label}
    >
      <div className="flex gap-1.5" aria-hidden>
        {[0, 1, 2, 3].map((idx) => (
          <div
            key={idx}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors duration-200",
              idx < filledSegments ? fillClass : "bg-muted"
            )}
          />
        ))}
      </div>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className={cn("font-medium", toneClass)}>{label}</span>
        {strength?.hint && (
          <span className="text-muted-foreground">{strength.hint}</span>
        )}
      </div>
    </div>
  )
}
