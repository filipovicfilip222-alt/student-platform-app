/**
 * (appointment)/layout.tsx — Shared layout for /appointments/[id].
 *
 * The detail view (status + chat + files + participants) is the same UX for
 * the student who booked the slot, the professor who owns it, and the
 * asistent who was delegated to it. Putting the route in its own group
 * (instead of (student) only) means a single page handles all of those
 * audiences without duplication.
 *
 * The sidebar still has to differ per role — students see the student nav,
 * professors / asistenti see the professor nav — so we read the role from
 * the auth store and forward it to <AppShell>. <ProtectedPage> guards
 * against ADMIN (or unauthenticated) users landing here directly.
 */

"use client"

import type { ReactNode } from "react"

import { AppShell } from "@/components/shared/app-shell"
import { ProtectedPage } from "@/components/shared/protected-page"
import { useAuthStore } from "@/lib/stores/auth"
import type { Role } from "@/types/common"

const APPOINTMENT_ROLES: Role[] = ["STUDENT", "PROFESOR", "ASISTENT"]

export default function AppointmentLayout({
  children,
}: {
  children: ReactNode
}) {
  const role = useAuthStore((s) => s.user?.role) ?? "STUDENT"
  // Professor and asistent share the same sidebar (see open question §7.5
  // in FRONTEND_STRUKTURA.md), so we collapse both onto the PROFESOR shell.
  const shellRole: Role = role === "STUDENT" ? "STUDENT" : "PROFESOR"

  return (
    <ProtectedPage allowedRoles={APPOINTMENT_ROLES}>
      <AppShell role={shellRole}>{children}</AppShell>
    </ProtectedPage>
  )
}
