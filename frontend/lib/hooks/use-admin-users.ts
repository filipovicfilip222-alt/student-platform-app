/**
 * use-admin-users.ts — Admin user CRUD + bulk import.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.7).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import type { AdminUserCreate, AdminUserUpdate, Uuid } from "@/types"

const LIST_KEY = ["admin", "users"] as const

export function useAdminUsers(
  params: { q?: string; role?: string; faculty?: string } = {}
) {
  return useQuery({
    queryKey: [...LIST_KEY, params] as const,
    queryFn: () => adminApi.listUsers(params),
    staleTime: 30 * 1000,
  })
}

export function useAdminUser(id: Uuid | null | undefined) {
  return useQuery({
    queryKey: [...LIST_KEY, id] as const,
    queryFn: () => adminApi.getUser(id as Uuid),
    enabled: Boolean(id),
  })
}

function invalidator(qc: ReturnType<typeof useQueryClient>) {
  return () => qc.invalidateQueries({ queryKey: LIST_KEY })
}

export function useCreateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AdminUserCreate) => adminApi.createUser(data),
    onSuccess: invalidator(qc),
  })
}

export function useUpdateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: Uuid; data: AdminUserUpdate }) =>
      adminApi.updateUser(id, data),
    onSuccess: invalidator(qc),
  })
}

export function useDeactivateAdminUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => adminApi.deactivateUser(id),
    onSuccess: invalidator(qc),
  })
}

export function useBulkImportPreview() {
  return useMutation({
    mutationFn: (file: File) => adminApi.bulkImportPreview(file),
  })
}

export function useBulkImportConfirm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => adminApi.bulkImportConfirm(file),
    onSuccess: invalidator(qc),
  })
}
