/**
 * routes.ts — Centralised route constants.
 *
 * Use these everywhere instead of inline string literals so renames stay cheap.
 * Functions are for dynamic segments (e.g. professor detail).
 */

export const ROUTES = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  login: "/login",
  register: "/register",
  forgotPassword: "/forgot-password",
  resetPassword: "/reset-password",

  // ── Student ───────────────────────────────────────────────────────────────
  dashboard: "/dashboard",
  search: "/search",
  professor: (id: string) => `/professor/${id}`,
  myAppointments: "/my-appointments",
  appointment: (id: string) => `/appointments/${id}`,
  documentRequests: "/document-requests",

  // ── Professor / Asistent ─────────────────────────────────────────────────
  professorDashboard: "/professor/dashboard",
  professorSettings: "/professor/settings",

  // ── Admin ─────────────────────────────────────────────────────────────────
  admin: "/admin",
  adminUsers: "/admin/users",
  adminDocumentRequests: "/admin/document-requests",
  adminStrikes: "/admin/strikes",
  adminBroadcast: "/admin/broadcast",
  adminAuditLog: "/admin/audit-log",
} as const
