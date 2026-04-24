/**
 * appointments.ts — Shared appointment detail / chat / files / participants.
 *
 * Consumed by both student and professor pages of /appointments/[id].
 *
 * TODO: backend endpoints not yet implemented (ROADMAP 3.6). All methods are
 * declared so UI can wire up now; they'll return 404 until backend lands.
 */

import api from "@/lib/api"
import type {
  AppointmentDetailResponse,
  ChatMessageCreate,
  ChatMessageResponse,
  FileResponse,
  MessageResponse,
  ParticipantResponse,
  Uuid,
} from "@/types"

export const appointmentsApi = {
  // ── Detail ──────────────────────────────────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  getDetail: (id: Uuid) =>
    api
      .get<AppointmentDetailResponse>(`/appointments/${id}`)
      .then((r) => r.data),

  // ── Chat (polling fallback until ROADMAP 4.1 WS) ────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  listMessages: (appointmentId: Uuid) =>
    api
      .get<ChatMessageResponse[]>(`/appointments/${appointmentId}/messages`)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  sendMessage: (appointmentId: Uuid, data: ChatMessageCreate) =>
    api
      .post<ChatMessageResponse>(
        `/appointments/${appointmentId}/messages`,
        data
      )
      .then((r) => r.data),

  // ── Files ───────────────────────────────────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  listFiles: (appointmentId: Uuid) =>
    api
      .get<FileResponse[]>(`/appointments/${appointmentId}/files`)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  uploadFile: (appointmentId: Uuid, file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    return api
      .post<FileResponse>(`/appointments/${appointmentId}/files`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data)
  },

  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  deleteFile: (appointmentId: Uuid, fileId: Uuid) =>
    api
      .delete<MessageResponse>(
        `/appointments/${appointmentId}/files/${fileId}`
      )
      .then((r) => r.data),

  // ── Participants (group consultations) ──────────────────────────────────
  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  listParticipants: (appointmentId: Uuid) =>
    api
      .get<ParticipantResponse[]>(
        `/appointments/${appointmentId}/participants`
      )
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  confirmParticipation: (appointmentId: Uuid, participantId: Uuid) =>
    api
      .post<ParticipantResponse>(
        `/appointments/${appointmentId}/participants/${participantId}/confirm`
      )
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 3.6)
  declineParticipation: (appointmentId: Uuid, participantId: Uuid) =>
    api
      .post<ParticipantResponse>(
        `/appointments/${appointmentId}/participants/${participantId}/decline`
      )
      .then((r) => r.data),
}
