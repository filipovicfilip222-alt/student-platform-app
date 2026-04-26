/**
 * audit-log-table.tsx — Filterable view of admin actions.
 *
 * KORAK 4 — refaktor sa generic `<DataTable />`. Filteri su client-state
 * + apply button koji prosleđuje na backend (server-driven filtering).
 *
 * Pagination + sort su client-side preko DataTable-a; default sort = bez
 * (audit log je već DESC po `created_at` na backend strani).
 *
 * Backend filteri: `action`, `from_date`, `to_date`. `admin_id` nije
 * exposed kao free text — admins traže kombinacijom action + dates.
 */

"use client"

import { useState } from "react"
import { ClipboardList, Filter } from "lucide-react"
import type { ColumnDef } from "@tanstack/react-table"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DataTable } from "@/components/ui/data-table"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuditLog } from "@/lib/hooks/use-audit-log"
import { formatDateTime } from "@/lib/utils/date"
import type { AuditLogFilter } from "@/types"

interface AuditLogRow {
  id: string
  created_at: string
  admin_full_name: string
  action: string
  impersonated_user_full_name: string | null
  ip_address: string
}

const COLUMNS: ColumnDef<AuditLogRow>[] = [
  {
    accessorKey: "created_at",
    header: "Kada",
    cell: ({ getValue }) => (
      <span className="whitespace-nowrap text-xs text-muted-foreground">
        {formatDateTime(getValue<string>())}
      </span>
    ),
  },
  {
    accessorKey: "admin_full_name",
    header: "Admin",
    cell: ({ getValue }) => (
      <span className="font-medium">{getValue<string>()}</span>
    ),
  },
  {
    accessorKey: "action",
    header: "Action",
    cell: ({ getValue }) => (
      <Badge variant="outline" className="font-mono text-xs">
        {getValue<string>()}
      </Badge>
    ),
  },
  {
    accessorKey: "impersonated_user_full_name",
    header: "Impersonirani korisnik",
    cell: ({ getValue }) => (
      <span className="text-xs text-muted-foreground">
        {getValue<string | null>() ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "ip_address",
    header: "IP",
    cell: ({ getValue }) => (
      <span className="font-mono text-xs text-muted-foreground">
        {getValue<string>()}
      </span>
    ),
  },
]

export function AuditLogTable() {
  const [actionFilter, setActionFilter] = useState("")
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const [applied, setApplied] = useState<AuditLogFilter>({})

  const query = useAuditLog(applied)

  function handleApply(e: React.FormEvent) {
    e.preventDefault()
    setApplied({
      action: actionFilter.trim() || undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    })
  }

  function handleReset() {
    setActionFilter("")
    setFromDate("")
    setToDate("")
    setApplied({})
  }

  const rows = (query.data ?? []) as AuditLogRow[]

  return (
    <div className="space-y-4">
      <form
        onSubmit={handleApply}
        className="grid gap-3 rounded-xl border border-border bg-card p-3 md:grid-cols-[1fr_180px_180px_auto_auto]"
      >
        <div className="grid gap-1.5">
          <Label htmlFor="audit-action">Action</Label>
          <Input
            id="audit-action"
            placeholder="npr. USER_DEACTIVATED"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="audit-from">Od</Label>
          <Input
            id="audit-from"
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="audit-to">Do</Label>
          <Input
            id="audit-to"
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
          />
        </div>
        <div className="flex items-end">
          <Button type="submit" className="w-full">
            <Filter aria-hidden />
            Primeni
          </Button>
        </div>
        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={handleReset}
          >
            Resetuj
          </Button>
        </div>
      </form>

      <DataTable<AuditLogRow, unknown>
        data={rows}
        columns={COLUMNS}
        isLoading={query.isLoading}
        isError={query.isError}
        ariaLabel="Audit log"
        density="compact"
        emptyState={{
          icon: ClipboardList,
          title: "Nema zapisa",
          description: "Nema audit događaja za izabrane filtere.",
        }}
        errorState={{
          icon: ClipboardList,
          title: "Audit log nije dostupan",
          description:
            "Backend endpoint /admin/audit-log još nije aktivan (ROADMAP 4.7).",
        }}
      />
    </div>
  )
}
