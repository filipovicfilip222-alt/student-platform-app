/**
 * admin-dashboard-metrics.tsx — Top-level stats block for /admin.
 *
 * ROADMAP 4.7 — overview metrics. Reads `GET /admin/overview` via
 * `adminApi.getOverview()`; when the backend endpoint is not yet live
 * (ROADMAP 4.7 is still ❌), the card shows an `EmptyState`-style
 * placeholder so the rest of the admin shell remains usable.
 */

"use client"

import { useQuery } from "@tanstack/react-query"
import {
  Activity,
  FileClock,
  ShieldAlert,
  ShieldOff,
  Users,
  type LucideIcon,
} from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { adminApi } from "@/lib/api/admin"

export function AdminDashboardMetrics() {
  const query = useQuery({
    queryKey: ["admin", "overview"] as const,
    queryFn: () => adminApi.getOverview(),
    staleTime: 60 * 1000,
    retry: 0,
  })

  if (query.isError) {
    return (
      <Card>
        <CardContent className="p-4 text-xs text-muted-foreground">
          Metrike će biti dostupne čim backend endpoint
          <code className="mx-1 rounded bg-muted px-1 font-mono">
            /admin/overview
          </code>
          bude live (ROADMAP 4.7).
        </CardContent>
      </Card>
    )
  }

  const data = query.data

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <MetricCard
        title="Korisnika ukupno"
        value={data?.total_users}
        icon={Users}
        isLoading={query.isLoading}
      />
      <MetricCard
        title="Zahtevi na čekanju"
        value={data?.pending_document_requests}
        icon={FileClock}
        accent="text-amber-600"
        isLoading={query.isLoading}
      />
      <MetricCard
        title="Aktivni strike-ovi"
        value={data?.active_strikes}
        icon={ShieldAlert}
        accent="text-orange-600"
        isLoading={query.isLoading}
      />
      <MetricCard
        title="Blokirani studenti"
        value={data?.blocked_students}
        icon={ShieldOff}
        accent="text-red-600"
        isLoading={query.isLoading}
      />
      <MetricCard
        title="Termini (7 dana)"
        value={data?.appointments_last_7_days}
        icon={Activity}
        accent="text-emerald-600"
        isLoading={query.isLoading}
      />
    </div>
  )
}

interface MetricCardProps {
  title: string
  value: number | undefined
  icon: LucideIcon
  accent?: string
  isLoading: boolean
}

function MetricCard({
  title,
  value,
  icon: Icon,
  accent = "text-muted-foreground",
  isLoading,
}: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className={`size-4 ${accent}`} aria-hidden />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-7 w-16" />
        ) : (
          <div className="text-2xl font-bold">{value ?? "—"}</div>
        )}
      </CardContent>
    </Card>
  )
}
