/**
 * data-table-pagination.tsx — Numbered pagination + page-size selector
 * za `<DataTable />`.
 *
 * Pretpostavke:
 *   - Roditelj prosleđuje izračunat `pageCount`. Komponenta ne zna ništa
 *     o tanstack/react-table-u — može se reuse-ovati i za server-pagination
 *     ako roditelj prepiše `currentPage`/`onPageChange`.
 *   - Page numbers strategija:
 *       • totalPages <= 7 → svi brojevi
 *       • inače → prvi + ... + 3 srednja oko currentPage + ... + poslednji
 *
 * A11y: koristimo `nav[aria-label]` + `aria-current="page"` na aktivnom
 * page button-u; previous/next dugmad imaju eksplicitne `aria-label`-e.
 */

"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

export interface DataTablePaginationProps {
  currentPage: number
  pageCount: number
  pageSize: number
  totalRows: number
  pageSizeOptions?: number[]
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  className?: string
}

function buildPageRange(current: number, total: number): Array<number | "…"> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  const range: Array<number | "…"> = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  if (start > 2) range.push("…")
  for (let i = start; i <= end; i++) range.push(i)
  if (end < total - 1) range.push("…")
  range.push(total)
  return range
}

export function DataTablePagination({
  currentPage,
  pageCount,
  pageSize,
  totalRows,
  pageSizeOptions = [10, 25, 50, 100],
  onPageChange,
  onPageSizeChange,
  className,
}: DataTablePaginationProps) {
  const fromRow = Math.min((currentPage - 1) * pageSize + 1, totalRows)
  const toRow = Math.min(currentPage * pageSize, totalRows)
  const pageRange = buildPageRange(currentPage, Math.max(1, pageCount))

  return (
    <nav
      aria-label="Paginacija tabele"
      className={cn(
        "flex flex-col gap-3 px-1 py-1 text-sm sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Prikazano {fromRow}–{toRow} od {totalRows}
      </p>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Po stranici</span>
          <Select
            value={String(pageSize)}
            onValueChange={(v) => onPageSizeChange(Number(v))}
          >
            <SelectTrigger className="h-8 w-[72px]" aria-label="Veličina stranice">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {pageSizeOptions.map((opt) => (
                <SelectItem key={opt} value={String(opt)}>
                  {opt}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage <= 1}
            aria-label="Prethodna stranica"
          >
            <ChevronLeft className="size-4" aria-hidden />
          </Button>

          {pageRange.map((page, idx) =>
            page === "…" ? (
              <span
                key={`ellipsis-${idx}`}
                className="px-2 text-xs text-muted-foreground"
                aria-hidden
              >
                …
              </span>
            ) : (
              <Button
                key={page}
                type="button"
                variant={page === currentPage ? "default" : "ghost"}
                size="icon"
                onClick={() => onPageChange(page)}
                aria-label={`Stranica ${page}`}
                aria-current={page === currentPage ? "page" : undefined}
              >
                {page}
              </Button>
            )
          )}

          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => onPageChange(Math.min(pageCount, currentPage + 1))}
            disabled={currentPage >= pageCount}
            aria-label="Sledeća stranica"
          >
            <ChevronRight className="size-4" aria-hidden />
          </Button>
        </div>
      </div>
    </nav>
  )
}
