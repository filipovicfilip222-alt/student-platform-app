/**
 * role-gate.tsx — Conditional render based on the current user's role.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * Unlike `<ProtectedPage>`, RoleGate does NOT redirect. It simply hides
 * its children when the user's role isn't allowed — useful for toolbar
 * buttons, sidebar items, or individual sections of a shared page.
 *
 * This is a UX filter, not a security boundary — backend enforces RBAC.
 */

"use client"

import type { ReactNode } from "react"

import { useAuthStore } from "@/lib/stores/auth"
import type { Role } from "@/types/common"

export interface RoleGateProps {
  allowedRoles: Role[]
  /** Rendered when the user's role is NOT in allowedRoles. Defaults to null. */
  fallback?: ReactNode
  children: ReactNode
}

export function RoleGate({
  allowedRoles,
  fallback = null,
  children,
}: RoleGateProps) {
  const role = useAuthStore((s) => s.user?.role ?? null)
  if (!role || !allowedRoles.includes(role)) return <>{fallback}</>
  return <>{children}</>
}
