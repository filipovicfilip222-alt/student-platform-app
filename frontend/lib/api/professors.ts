/**
 * professors.ts — Professor / Asistent facing API wrappers.
 *
 * Implemented now (backend ROADMAP 3.1 done):
 *   - /professors/slots CRUD
 *   - /professors/blackout CRUD
 *
 * TODO: backend endpoints not yet implemented (ROADMAP 3.7). Methods are
 * declared so pages can reference them; they will 404 until backend catches up.
 */

import api from "@/lib/api"
import type {
  AssistantOption,
  BlackoutCreateRequest,
  BlackoutResponse,
  CannedResponseCreate,
  CannedResponseResponse,
  CannedResponseUpdate,
  CrmNoteCreate,
  CrmNoteResponse,
  FaqCreate,
  FaqResponse,
  FaqUpdate,
  ProfessorMeResponse,
  ProfessorProfileUpdate,
  SlotCreateRequest,
  SlotResponse,
  SlotUpdateRequest,
  Uuid,
} from "@/types"
import type { AppointmentResponse } from "@/types/appointment"

export const professorsApi = {
  // ── Availability slots ──────────────────────────────────────────────────
  listMySlots: () =>
    api.get<SlotResponse[]>("/professors/slots").then((r) => r.data),

  createSlot: (data: SlotCreateRequest) =>
    api.post<SlotResponse>("/professors/slots", data).then((r) => r.data),

  updateSlot: (slotId: Uuid, data: SlotUpdateRequest) =>
    api
      .put<SlotResponse>(`/professors/slots/${slotId}`, data)
      .then((r) => r.data),

  deleteSlot: (slotId: Uuid) =>
    api.delete<void>(`/professors/slots/${slotId}`).then((r) => r.data),

  // ── Blackout periods ────────────────────────────────────────────────────
  createBlackout: (data: BlackoutCreateRequest) =>
    api
      .post<BlackoutResponse>("/professors/blackout", data)
      .then((r) => r.data),

  deleteBlackout: (blackoutId: Uuid) =>
    api
      .delete<void>(`/professors/blackout/${blackoutId}`)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  listBlackouts: () =>
    api
      .get<BlackoutResponse[]>("/professors/blackout")
      .then((r) => r.data),

  // ── Requests inbox (ROADMAP 3.7) ────────────────────────────────────────
  // TODO: backend endpoint not yet implemented
  listRequestsInbox: (status: "PENDING" | "ALL" = "PENDING") =>
    api
      .get<AppointmentResponse[]>("/professors/requests", {
        params: { status },
      })
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  approveRequest: (appointmentId: Uuid) =>
    api
      .post<AppointmentResponse>(
        `/professors/requests/${appointmentId}/approve`
      )
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  rejectRequest: (appointmentId: Uuid, data: { reason: string }) =>
    api
      .post<AppointmentResponse>(
        `/professors/requests/${appointmentId}/reject`,
        data
      )
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  delegateRequest: (appointmentId: Uuid, data: { assistant_id: Uuid }) =>
    api
      .post<AppointmentResponse>(
        `/professors/requests/${appointmentId}/delegate`,
        data
      )
      .then((r) => r.data),

  // ── Profile settings ────────────────────────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  getMyProfile: () =>
    api
      .get<ProfessorMeResponse>("/professors/profile")
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  updateProfile: (data: ProfessorProfileUpdate) =>
    api
      .patch<ProfessorMeResponse>("/professors/profile", data)
      .then((r) => r.data),

  // ── Assistants assigned to this professor's subjects ────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.7 — delegate flow)
  listAssistants: () =>
    api
      .get<AssistantOption[]>("/professors/assistants")
      .then((r) => r.data),

  // ── FAQ ─────────────────────────────────────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  listFaq: () =>
    api.get<FaqResponse[]>("/professors/faq").then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  createFaq: (data: FaqCreate) =>
    api.post<FaqResponse>("/professors/faq", data).then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  updateFaq: (id: Uuid, data: FaqUpdate) =>
    api
      .patch<FaqResponse>(`/professors/faq/${id}`, data)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  deleteFaq: (id: Uuid) =>
    api.delete<void>(`/professors/faq/${id}`).then((r) => r.data),

  // ── Canned responses ────────────────────────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  listCannedResponses: () =>
    api
      .get<CannedResponseResponse[]>("/professors/canned-responses")
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  createCannedResponse: (data: CannedResponseCreate) =>
    api
      .post<CannedResponseResponse>("/professors/canned-responses", data)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  updateCannedResponse: (id: Uuid, data: CannedResponseUpdate) =>
    api
      .patch<CannedResponseResponse>(
        `/professors/canned-responses/${id}`,
        data
      )
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  deleteCannedResponse: (id: Uuid) =>
    api
      .delete<void>(`/professors/canned-responses/${id}`)
      .then((r) => r.data),

  // ── CRM notes (per student) ─────────────────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  listCrmNotes: (studentId: Uuid) =>
    api
      .get<CrmNoteResponse[]>("/professors/crm-notes", {
        params: { student_id: studentId },
      })
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  createCrmNote: (data: CrmNoteCreate) =>
    api
      .post<CrmNoteResponse>("/professors/crm-notes", data)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.7)
  deleteCrmNote: (id: Uuid) =>
    api
      .delete<void>(`/professors/crm-notes/${id}`)
      .then((r) => r.data),
}
