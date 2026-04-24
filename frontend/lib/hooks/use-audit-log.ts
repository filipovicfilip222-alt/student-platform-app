/**
 * use-audit-log.ts — Admin audit log viewer.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.7).
 */

"use client"

import { useQuery } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import type { AuditLogFilter } from "@/types"

export function useAuditLog(filter: AuditLogFilter = {}) {
  return useQuery({
    queryKey: ["admin", "audit-log", filter] as const,
    queryFn: () => adminApi.listAuditLog(filter),
    staleTime: 15 * 1000,
  })
}
