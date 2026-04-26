/**
 * data-table-toolbar.tsx — Compact filter/search bar za `<DataTable />`.
 *
 * Roditelj kompletno kontroliše state — toolbar je presentational shell:
 *   - leva strana = search input (opciono, ako `searchValue !== undefined`)
 *   - sredina    = filter chip-ovi (opciono — array of `<FilterChip />`)
 *   - desna strana = `actions` slot (Bulk import / Novi korisnik / Reset…)
 *
 * Active filter chips (FilterChip varijanta sa X) signaliziraju aktivni
 * filter; klik na X poziva onClear callback.
 */

"use client"

import { Search, X } from "lucide-react"
import type { ReactNode } from "react"

import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export interface DataTableToolbarProps {
  searchValue?: string
  searchPlaceholder?: string
  onSearchChange?: (value: string) => void
  /** Prikazuju se levo od action slot-a kao "active filter" chip-ovi. */
  filters?: ReactNode
  actions?: ReactNode
  className?: string
}

export function DataTableToolbar({
  searchValue,
  searchPlaceholder = "Pretraga…",
  onSearchChange,
  filters,
  actions,
  className,
}: DataTableToolbarProps) {
  const showSearch = searchValue !== undefined
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-border bg-card p-3 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
        {showSearch && (
          <div className="relative w-full sm:max-w-xs">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              value={searchValue ?? ""}
              onChange={(e) => onSearchChange?.(e.target.value)}
              placeholder={searchPlaceholder}
              className="pl-8"
              aria-label="Pretraga"
            />
          </div>
        )}

        {filters && (
          <div className="flex flex-wrap items-center gap-2">{filters}</div>
        )}
      </div>

      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </div>
  )
}

export interface FilterChipProps {
  label: string
  /** Optional displayed value (e.g. "Profesor"). */
  value?: string
  onClear?: () => void
  className?: string
}

/**
 * Active filter chip (npr. "Uloga: Profesor ✕"). Ako se prosledi
 * onClear, chip dobija X dugme.
 */
export function FilterChip({ label, value, onClear, className }: FilterChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary",
        className
      )}
    >
      <span className="text-muted-foreground">{label}:</span>
      {value && <span>{value}</span>}
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="rounded-full p-0.5 transition-colors hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          aria-label={`Ukloni filter: ${label}`}
        >
          <X className="size-3" aria-hidden />
        </button>
      )}
    </span>
  )
}
