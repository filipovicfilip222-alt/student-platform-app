/**
 * data-table.tsx — Generic, accessible, sortable, filterable data table.
 *
 * Wrapper iznad `@tanstack/react-table` v8 + shadcn `<Table>` primitive.
 *
 * Features (KORAK 4):
 *   - Column sorting (click header → asc/desc/none)
 *   - Pagination (controls renderuje `<DataTablePagination />`)
 *   - Density toggle (compact / default) — gledamo `density` prop
 *   - Sticky header (oduzeti class iz wrapper-a kad je `stickyHeader`)
 *   - Configurable empty / loading / error states preko props-a
 *   - Row-level actions slot kroz columnDef.cell
 *
 * Server-driven filtering (npr. `useAdminUsers(filters)`) ostaje izvan —
 * DataTable hendluje samo client-side prikaz, sort i paginate.
 *
 * Skriva pagination kontrole ako `pageCount <= 1`.
 */

"use client"

import {
  type ColumnDef,
  type Row,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { ChevronDown, ChevronUp, ChevronsUpDown, type LucideIcon } from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/shared/empty-state"
import { cn } from "@/lib/utils"

import { DataTablePagination } from "./data-table-pagination"

export type DataTableDensity = "compact" | "default"

export interface DataTableState<TData> {
  rows: ReadonlyArray<Row<TData>>
}

export interface DataTableEmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}

export interface DataTableProps<TData, TValue> {
  data: ReadonlyArray<TData>
  columns: ReadonlyArray<ColumnDef<TData, TValue>>
  /** Loading flag — renders skeleton rows. */
  isLoading?: boolean
  /** Error flag — renders the `errorState` / fallback empty state. */
  isError?: boolean
  /** State to render when `data.length === 0` (post-load, no error). */
  emptyState?: DataTableEmptyStateProps
  /** State to render when `isError === true`. */
  errorState?: DataTableEmptyStateProps
  /** Sticky `<thead>` (`top-0` u overflow container-u). */
  stickyHeader?: boolean
  /** Initial / controlled density. Default: `default`. */
  density?: DataTableDensity
  /** Override default page size; default: 10. */
  pageSize?: number
  /** Available page-size options (rendered in pagination). */
  pageSizeOptions?: number[]
  /** Hide pagination row entirely (e.g. for very small lists). */
  hidePagination?: boolean
  /** Optional `<aria-label>` for the underlying `<table>`. */
  ariaLabel?: string
  /** Slot rendered iznad tabele (toolbar). */
  toolbar?: ReactNode
  /** Slot rendered ispod tabele (npr. bulk action bar). */
  footer?: ReactNode
  /** Stabilan id za rowove. Default: `row.original.id` ako postoji, inače index. */
  getRowId?: (row: TData, index: number) => string
  className?: string
}

const ROW_HEIGHT = {
  compact: "h-9",
  default: "h-12",
} as const

const CELL_PADDING = {
  compact: "py-1.5",
  default: "py-2.5",
} as const

export function DataTable<TData, TValue>({
  data,
  columns,
  isLoading = false,
  isError = false,
  emptyState,
  errorState,
  stickyHeader = true,
  density = "default",
  pageSize = 10,
  pageSizeOptions = [10, 25, 50, 100],
  hidePagination = false,
  ariaLabel,
  toolbar,
  footer,
  getRowId,
  className,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([])

  const table = useReactTable<TData>({
    data: data as TData[],
    columns: columns as ColumnDef<TData, TValue>[],
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    getRowId: (row, index) => {
      if (getRowId) return getRowId(row, index)
      const candidate = (row as { id?: unknown }).id
      return candidate != null ? String(candidate) : String(index)
    },
  })

  const colSpan = columns.length
  const rowsModel = table.getRowModel().rows

  // Pre-compute placeholder skeleton rows (stable count tied to pageSize).
  const skeletonRows = useMemo(
    () => Array.from({ length: Math.min(pageSize, 5) }),
    [pageSize]
  )

  return (
    <div className={cn("space-y-3", className)}>
      {toolbar}

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="relative w-full overflow-x-auto">
          <Table aria-label={ariaLabel}>
            <TableHeader
              className={cn(
                "bg-muted/40",
                stickyHeader && "sticky top-0 z-10 backdrop-blur"
              )}
            >
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="hover:bg-muted/40">
                  {headerGroup.headers.map((header) => {
                    const sortDir = header.column.getIsSorted()
                    const canSort = header.column.getCanSort()
                    return (
                      <TableHead
                        key={header.id}
                        colSpan={header.colSpan}
                        className={cn(
                          "text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                        )}
                      >
                        {header.isPlaceholder ? null : canSort ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm"
                            aria-label={`Sortiraj po: ${typeof header.column.columnDef.header === "string" ? header.column.columnDef.header : header.column.id}`}
                          >
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                            {sortDir === "asc" ? (
                              <ChevronUp className="size-3" aria-hidden />
                            ) : sortDir === "desc" ? (
                              <ChevronDown className="size-3" aria-hidden />
                            ) : (
                              <ChevronsUpDown
                                className="size-3 opacity-40"
                                aria-hidden
                              />
                            )}
                          </button>
                        ) : (
                          flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )
                        )}
                      </TableHead>
                    )
                  })}
                </TableRow>
              ))}
            </TableHeader>

            <TableBody>
              {isLoading ? (
                skeletonRows.map((_, idx) => (
                  <TableRow
                    key={`skeleton-${idx}`}
                    className={ROW_HEIGHT[density]}
                  >
                    <TableCell colSpan={colSpan} className={CELL_PADDING[density]}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : isError && errorState ? (
                <TableRow>
                  <TableCell colSpan={colSpan} className="py-10">
                    <EmptyState
                      icon={errorState.icon}
                      title={errorState.title}
                      description={errorState.description}
                      action={errorState.action}
                    />
                  </TableCell>
                </TableRow>
              ) : rowsModel.length === 0 && emptyState ? (
                <TableRow>
                  <TableCell colSpan={colSpan} className="py-10">
                    <EmptyState
                      icon={emptyState.icon}
                      title={emptyState.title}
                      description={emptyState.description}
                      action={emptyState.action}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                rowsModel.map((row) => (
                  <TableRow
                    key={row.id}
                    className={cn(ROW_HEIGHT[density])}
                    data-state={row.getIsSelected() ? "selected" : undefined}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell
                        key={cell.id}
                        className={CELL_PADDING[density]}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {!hidePagination && rowsModel.length > 0 && (
        <DataTablePagination
          currentPage={table.getState().pagination.pageIndex + 1}
          pageCount={table.getPageCount()}
          pageSize={table.getState().pagination.pageSize}
          totalRows={table.getRowCount()}
          pageSizeOptions={pageSizeOptions}
          onPageChange={(p) => table.setPageIndex(p - 1)}
          onPageSizeChange={(size) => table.setPageSize(size)}
        />
      )}

      {footer}
    </div>
  )
}
