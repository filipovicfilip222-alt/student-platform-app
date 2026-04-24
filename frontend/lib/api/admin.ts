/**
 * admin.ts — ADMIN-only API wrappers.
 *
 * TODO: backend endpoints not yet implemented (ROADMAP 4.3 + 4.7 + 4.8).
 * Shapes are the frontend's best-guess contract; confirm with backend once
 * schemas/admin.py lands.
 */

import api from "@/lib/api"
import type {
  AdminOverviewMetrics,
  AdminUserCreate,
  AdminUserResponse,
  AdminUserUpdate,
  AuditLogFilter,
  AuditLogRow,
  BroadcastRequest,
  BroadcastResponse,
  BulkImportPreview,
  BulkImportResult,
  DocumentRequestApprove,
  DocumentRequestReject,
  DocumentRequestResponse,
  DocumentStatus,
  ImpersonationEndResponse,
  ImpersonationStartResponse,
  MessageResponse,
  StrikeRow,
  UnblockRequest,
  Uuid,
} from "@/types"

// TODO: backend endpoint not yet implemented (ROADMAP 4.7)
export const adminApi = {
  // ── Overview metrics ────────────────────────────────────────────────────
  getOverview: () =>
    api
      .get<AdminOverviewMetrics>("/admin/overview")
      .then((r) => r.data),

  // ── Users CRUD ──────────────────────────────────────────────────────────
  listUsers: (params: { q?: string; role?: string; faculty?: string } = {}) =>
    api
      .get<AdminUserResponse[]>("/admin/users", { params })
      .then((r) => r.data),

  getUser: (id: Uuid) =>
    api
      .get<AdminUserResponse>(`/admin/users/${id}`)
      .then((r) => r.data),

  createUser: (data: AdminUserCreate) =>
    api
      .post<AdminUserResponse>("/admin/users", data)
      .then((r) => r.data),

  updateUser: (id: Uuid, data: AdminUserUpdate) =>
    api
      .patch<AdminUserResponse>(`/admin/users/${id}`, data)
      .then((r) => r.data),

  deactivateUser: (id: Uuid) =>
    api
      .post<MessageResponse>(`/admin/users/${id}/deactivate`)
      .then((r) => r.data),

  // ── Bulk CSV import ─────────────────────────────────────────────────────
  bulkImportPreview: (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return api
      .post<BulkImportPreview>("/admin/users/bulk-import/preview", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data)
  },

  bulkImportConfirm: (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return api
      .post<BulkImportResult>("/admin/users/bulk-import/confirm", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data)
  },

  // ── Impersonation ───────────────────────────────────────────────────────
  // Endpoints + response shape fixed by docs/websocket-schema.md §6.1.
  // TTL is 30 min (expires_in: 1800), no refresh — on 401 the admin must
  // re-impersonate from the users table.
  impersonateStart: (userId: Uuid) =>
    api
      .post<ImpersonationStartResponse>(
        `/admin/impersonate/${userId}`
      )
      .then((r) => r.data),

  impersonateEnd: () =>
    api
      .post<ImpersonationEndResponse>("/admin/impersonate/end")
      .then((r) => r.data),

  // ── Strikes & blocks ────────────────────────────────────────────────────
  listStrikes: () =>
    api.get<StrikeRow[]>("/admin/strikes").then((r) => r.data),

  unblockStudent: (studentId: Uuid, data: UnblockRequest) =>
    api
      .post<MessageResponse>(`/admin/strikes/${studentId}/unblock`, data)
      .then((r) => r.data),

  // ── Document requests (admin queue) ─────────────────────────────────────
  listDocumentRequests: (params: { status?: DocumentStatus } = {}) =>
    api
      .get<DocumentRequestResponse[]>("/admin/document-requests", { params })
      .then((r) => r.data),

  approveDocumentRequest: (id: Uuid, data: DocumentRequestApprove) =>
    api
      .post<DocumentRequestResponse>(
        `/admin/document-requests/${id}/approve`,
        data
      )
      .then((r) => r.data),

  rejectDocumentRequest: (id: Uuid, data: DocumentRequestReject) =>
    api
      .post<DocumentRequestResponse>(
        `/admin/document-requests/${id}/reject`,
        data
      )
      .then((r) => r.data),

  completeDocumentRequest: (id: Uuid) =>
    api
      .post<DocumentRequestResponse>(
        `/admin/document-requests/${id}/complete`
      )
      .then((r) => r.data),

  // ── Broadcast ───────────────────────────────────────────────────────────
  sendBroadcast: (data: BroadcastRequest) =>
    api
      .post<BroadcastResponse>("/admin/broadcast", data)
      .then((r) => r.data),

  listBroadcastHistory: () =>
    api
      .get<BroadcastResponse[]>("/admin/broadcast")
      .then((r) => r.data),

  // ── Audit log ───────────────────────────────────────────────────────────
  listAuditLog: (params: AuditLogFilter = {}) =>
    api
      .get<AuditLogRow[]>("/admin/audit-log", { params })
      .then((r) => r.data),
}
