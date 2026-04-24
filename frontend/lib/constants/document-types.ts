/**
 * document-types.ts — DocumentType + DocumentStatus constants.
 *
 * Source of truth: backend/app/models/enums.py::DocumentType / DocumentStatus.
 * NB: backend enum values are POTVRDA_STATUSA / POTVRDA_SKOLARINE / PREPIS_OCENA
 * (Serbian spelling), NOT the shorter forms mentioned in FRONTEND_STRUKTURA.md §3.9.
 */

import type { DocumentType, DocumentStatus } from "@/types/common"

export const DOCUMENT_TYPES: readonly DocumentType[] = [
  "POTVRDA_STATUSA",
  "UVERENJE_ISPITI",
  "UVERENJE_PROSEK",
  "PREPIS_OCENA",
  "POTVRDA_SKOLARINE",
  "OSTALO",
] as const

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  POTVRDA_STATUSA: "Potvrda o statusu studenta",
  UVERENJE_ISPITI: "Uverenje o položenim ispitima",
  UVERENJE_PROSEK: "Uverenje o proseku",
  PREPIS_OCENA: "Prepis ocena (transcript)",
  POTVRDA_SKOLARINE: "Potvrda o školarini",
  OSTALO: "Ostalo",
}

export function documentTypeLabel(value: DocumentType): string {
  return DOCUMENT_TYPE_LABELS[value]
}

export const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  PENDING: "Na čekanju",
  APPROVED: "Odobreno",
  REJECTED: "Odbijeno",
  COMPLETED: "Preuzeto",
}

export function documentStatusLabel(value: DocumentStatus): string {
  return DOCUMENT_STATUS_LABELS[value]
}
