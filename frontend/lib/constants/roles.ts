/**
 * roles.ts — UserRole enum + Serbian Latin labels.
 *
 * Source of truth: backend/app/models/enums.py::UserRole.
 */

import type { Role } from "@/types/common"

export const ROLES: readonly Role[] = [
  "STUDENT",
  "ASISTENT",
  "PROFESOR",
  "ADMIN",
] as const

export const ROLE_LABELS: Record<Role, string> = {
  STUDENT: "Student",
  ASISTENT: "Asistent",
  PROFESOR: "Profesor",
  ADMIN: "Administrator",
}

export function roleLabel(role: Role): string {
  return ROLE_LABELS[role]
}
