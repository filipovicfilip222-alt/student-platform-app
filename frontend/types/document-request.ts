/**
 * document-request.ts — Student document-request types.
 *
 * TODO: sync with backend when schema is implemented.
 *       backend/app/schemas/document_request.py does not exist yet
 *       (ROADMAP 4.8). The SQLAlchemy model `DocumentRequest` is the only
 *       source right now — these shapes match its columns.
 */

import type {
  DocumentStatus,
  DocumentType,
  IsoDate,
  IsoDateTime,
  Uuid,
} from "./common"

export interface DocumentRequestCreate {
  document_type: DocumentType
  note?: string | null
}

export interface DocumentRequestResponse {
  id: Uuid
  student_id: Uuid
  document_type: DocumentType
  note: string | null
  status: DocumentStatus
  admin_note: string | null
  pickup_date: IsoDate | null
  processed_by: Uuid | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface DocumentRequestApprove {
  pickup_date: IsoDate
  admin_note?: string | null
}

export interface DocumentRequestReject {
  admin_note: string
}
