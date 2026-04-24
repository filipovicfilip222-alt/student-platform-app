/**
 * audit-log-table.tsx — Filterable view of admin actions.
 *
 * ROADMAP 4.7 / FRONTEND_STRUKTURA §3.6. Filters currently supported by
 * the backend-contract are `action`, `from_date`, `to_date` (see
 * types/admin.ts::AuditLogFilter). `admin_id` is not exposed as a free
 * text filter — admins search by action text + date range.
 */

"use client"

import { useState } from "react"
import { ClipboardList, Filter } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EmptyState } from "@/components/shared/empty-state"
import { useAuditLog } from "@/lib/hooks/use-audit-log"
import { formatDateTime } from "@/lib/utils/date"
import type { AuditLogFilter } from "@/types"

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

  const rows = query.data ?? []

  return (
    <div className="space-y-4">
      <form
        onSubmit={handleApply}
        className="grid gap-3 rounded-lg border border-border bg-background p-3 md:grid-cols-[1fr_180px_180px_auto_auto]"
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

      <div className="overflow-hidden rounded-lg border border-border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Kada</TableHead>
              <TableHead>Admin</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Impersonirani korisnik</TableHead>
              <TableHead>IP</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.isLoading ? (
              Array.from({ length: 5 }).map((_, idx) => (
                <TableRow key={idx}>
                  <TableCell colSpan={5}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))
            ) : query.isError ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8">
                  <EmptyState
                    icon={ClipboardList}
                    title="Audit log nije dostupan"
                    description="Backend endpoint /admin/audit-log još nije aktivan (ROADMAP 4.7)."
                  />
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8">
                  <EmptyState
                    icon={ClipboardList}
                    title="Nema zapisa"
                    description="Nema audit događaja za izabrane filtere."
                  />
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    {formatDateTime(row.created_at)}
                  </TableCell>
                  <TableCell className="font-medium">
                    {row.admin_full_name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {row.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {row.impersonated_user_full_name ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {row.ip_address}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
