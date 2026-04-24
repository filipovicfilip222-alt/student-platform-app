/**
 * students.ts — Student-facing API wrappers.
 *
 * Mirrors backend/app/api/v1/students.py.
 * Each method returns the unwrapped response body (no AxiosResponse).
 *
 * NB: list endpoints currently return bare `T[]`; they will migrate to
 * `Paginated<T>` when ROADMAP 1.6 lands. Callers typed as `T[]` here will
 * need to adapt when that happens.
 */

import api from "@/lib/api"
import type {
  AppointmentCancelResponse,
  AppointmentCreateRequest,
  AppointmentResponse,
  AvailableSlotResponse,
  ConsultationType,
  Faculty,
  IsoDate,
  MessageResponse,
  ProfessorProfileResponse,
  ProfessorSearchResponse,
  Uuid,
} from "@/types"

export interface ProfessorSearchParams {
  q?: string
  faculty?: Faculty
  subject?: string
  type?: ConsultationType
}

export interface SlotRangeParams {
  start_date?: IsoDate
  end_date?: IsoDate
}

export type MyAppointmentsView = "upcoming" | "history"

export const studentsApi = {
  // ── Professor discovery ─────────────────────────────────────────────────
  searchProfessors: (params: ProfessorSearchParams = {}) =>
    api
      .get<ProfessorSearchResponse[]>("/students/professors/search", { params })
      .then((r) => r.data),

  getProfessorProfile: (id: Uuid) =>
    api
      .get<ProfessorProfileResponse>(`/students/professors/${id}`)
      .then((r) => r.data),

  getProfessorSlots: (id: Uuid, params: SlotRangeParams = {}) =>
    api
      .get<AvailableSlotResponse[]>(`/students/professors/${id}/slots`, {
        params,
      })
      .then((r) => r.data),

  // ── Appointments ────────────────────────────────────────────────────────
  createAppointment: (data: AppointmentCreateRequest) =>
    api
      .post<AppointmentResponse>("/students/appointments", data)
      .then((r) => r.data),

  cancelAppointment: (id: Uuid) =>
    api
      .delete<AppointmentCancelResponse>(`/students/appointments/${id}`)
      .then((r) => r.data),

  listMyAppointments: (view: MyAppointmentsView = "upcoming") =>
    api
      .get<AppointmentResponse[]>("/students/appointments", {
        params: { view },
      })
      .then((r) => r.data),

  // ── Waitlist ─────────────────────────────────────────────────────────────
  joinWaitlist: (slotId: Uuid) =>
    api
      .post<MessageResponse>(`/students/waitlist/${slotId}`)
      .then((r) => r.data),

  leaveWaitlist: (slotId: Uuid) =>
    api
      .delete<MessageResponse>(`/students/waitlist/${slotId}`)
      .then((r) => r.data),
}
