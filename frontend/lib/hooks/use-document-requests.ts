/**
 * use-document-requests.ts — Student + admin document request hooks.
 *
 * Student-side uses documentRequestsApi. Admin-side uses adminApi.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.8).
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { adminApi } from "@/lib/api/admin"
import { documentRequestsApi } from "@/lib/api/document-requests"
import type {
  DocumentRequestApprove,
  DocumentRequestCreate,
  DocumentRequestReject,
  DocumentStatus,
  Uuid,
} from "@/types"

// ── Student ──────────────────────────────────────────────────────────────────

const MY_DOC_REQ_KEY = ["document-requests", "mine"] as const

export function useMyDocumentRequests() {
  return useQuery({
    queryKey: MY_DOC_REQ_KEY,
    queryFn: () => documentRequestsApi.listMine(),
    staleTime: 30 * 1000,
  })
}

export function useCreateDocumentRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: DocumentRequestCreate) =>
      documentRequestsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: MY_DOC_REQ_KEY }),
  })
}

// ── Admin ────────────────────────────────────────────────────────────────────

const ADMIN_DOC_REQ_KEY = ["document-requests", "admin"] as const

export function useAdminDocumentRequests(status?: DocumentStatus) {
  return useQuery({
    queryKey: [...ADMIN_DOC_REQ_KEY, status ?? "ALL"] as const,
    queryFn: () => adminApi.listDocumentRequests({ status }),
    staleTime: 15 * 1000,
  })
}

function makeAdminInvalidator(qc: ReturnType<typeof useQueryClient>) {
  return () => qc.invalidateQueries({ queryKey: ADMIN_DOC_REQ_KEY })
}

export function useApproveDocumentRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: Uuid; data: DocumentRequestApprove }) =>
      adminApi.approveDocumentRequest(id, data),
    onSuccess: makeAdminInvalidator(qc),
  })
}

export function useRejectDocumentRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: Uuid; data: DocumentRequestReject }) =>
      adminApi.rejectDocumentRequest(id, data),
    onSuccess: makeAdminInvalidator(qc),
  })
}

export function useCompleteDocumentRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => adminApi.completeDocumentRequest(id),
    onSuccess: makeAdminInvalidator(qc),
  })
}
