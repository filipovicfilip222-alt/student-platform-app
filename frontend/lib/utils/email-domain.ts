/**
 * email-domain.ts — Email domain validation.
 *
 * Mirrors backend logic from `backend/app/core/security.py` (see CLAUDE.md §4).
 * Must stay in sync with `ALLOWED_STUDENT_DOMAINS` / `ALLOWED_STAFF_DOMAINS`.
 */

export const ALLOWED_STUDENT_DOMAINS = [
  "student.fon.bg.ac.rs",
  "student.etf.bg.ac.rs",
] as const

export const ALLOWED_STAFF_DOMAINS = [
  "fon.bg.ac.rs",
  "etf.bg.ac.rs",
] as const

export type StudentDomain = (typeof ALLOWED_STUDENT_DOMAINS)[number]
export type StaffDomain = (typeof ALLOWED_STAFF_DOMAINS)[number]

function getDomain(email: string): string {
  const at = email.lastIndexOf("@")
  if (at === -1) return ""
  return email.slice(at + 1).toLowerCase().trim()
}

export function isStudentEmail(email: string): boolean {
  const domain = getDomain(email)
  return (ALLOWED_STUDENT_DOMAINS as readonly string[]).includes(domain)
}

export function isStaffEmail(email: string): boolean {
  const domain = getDomain(email)
  return (ALLOWED_STAFF_DOMAINS as readonly string[]).includes(domain)
}

export function isAllowedEmail(email: string): boolean {
  return isStudentEmail(email) || isStaffEmail(email)
}

/**
 * Throws a user-facing Error if the email's domain is not whitelisted.
 * Used by zod refinements in registration / admin user-create forms.
 */
export function validateEmailDomain(email: string): void {
  if (!isAllowedEmail(email)) {
    const domain = getDomain(email) || "(nepoznat)"
    throw new Error(`Email domen '${domain}' nije dozvoljen.`)
  }
}
