/**
 * document-requests.ts — Student-facing document request API.
 *
 * Admin-side operations (list all / approve / reject / complete) live in
 * lib/api/admin.ts.
 *
 * TODO: backend endpoint not yet implemented (ROADMAP 4.8).
 */

import api from "@/lib/api"
import type {
  DocumentRequestCreate,
  DocumentRequestResponse,
  Uuid,
} from "@/types"

export const documentRequestsApi = {
  // TODO: backend endpoint not yet implemented (ROADMAP 4.8)
  listMine: () =>
    api
      .get<DocumentRequestResponse[]>("/students/document-requests")
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.8)
  create: (data: DocumentRequestCreate) =>
    api
      .post<DocumentRequestResponse>("/students/document-requests", data)
      .then((r) => r.data),

  // TODO: backend endpoint not yet implemented (ROADMAP 4.8)
  getOne: (id: Uuid) =>
    api
      .get<DocumentRequestResponse>(`/students/document-requests/${id}`)
      .then((r) => r.data),
}
