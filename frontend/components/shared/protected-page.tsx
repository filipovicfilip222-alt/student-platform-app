/**
 * protected-page.tsx — Auth + role gate for logged-in routes.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * Behaviour:
 *  1. While the Zustand auth store is still restoring the session
 *     (`isLoading`), render a lightweight loading frame so we don't
 *     flash the page or redirect prematurely.
 *  2. If no user after loading → middleware should have caught it, but
 *     as a defence-in-depth we redirect to /login here too.
 *  3. If the user's role is not in `allowedRoles` → redirect them to
 *     the default dashboard for THEIR role (avoids infinite loop on
 *     a role they don't have).
 *
 * The real RBAC is on the backend; this component is UX polish.
 */

"use client"

import { Loader2 } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect, type ReactNode } from "react"

import { ROUTES } from "@/lib/constants/routes"
import { useAuthStore } from "@/lib/stores/auth"
import type { Role } from "@/types/common"

/** Where each role should land when it accesses a foreign route group. */
const ROLE_HOME: Record<Role, string> = {
  STUDENT: ROUTES.dashboard,
  PROFESOR: ROUTES.professorDashboard,
  ASISTENT: ROUTES.professorDashboard,
  ADMIN: ROUTES.admin,
}

export interface ProtectedPageProps {
  allowedRoles: Role[]
  children: ReactNode
}

export function ProtectedPage({ allowedRoles, children }: ProtectedPageProps) {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const isLoading = useAuthStore((s) => s.isLoading)

  const role = user?.role ?? null
  const allowed = role !== null && allowedRoles.includes(role)

  useEffect(() => {
    if (isLoading) return
    if (!user) {
      router.replace(ROUTES.login)
      return
    }
    if (!allowed && role) {
      router.replace(ROLE_HOME[role])
    }
  }, [isLoading, user, allowed, role, router])

  if (isLoading || !user || !allowed) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-background text-muted-foreground"
        aria-busy="true"
      >
        <div className="flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Učitavanje…
        </div>
      </div>
    )
  }

  return <>{children}</>
}
