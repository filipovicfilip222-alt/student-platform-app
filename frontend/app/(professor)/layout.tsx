/**
 * (professor)/layout.tsx — Route-group layout for PROFESOR / ASISTENT.
 *
 * ROADMAP 2.2 — layouti po roli.
 * Both roles share the same sidebar (see open question §7.5 in
 * FRONTEND_STRUKTURA.md). Granular asistent-only / profesor-only
 * controls inside pages are filtered via <RoleGate>.
 */

import { AppShell } from "@/components/shared/app-shell"
import { ProtectedPage } from "@/components/shared/protected-page"

export default function ProfessorLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ProtectedPage allowedRoles={["PROFESOR", "ASISTENT"]}>
      <AppShell role="PROFESOR">{children}</AppShell>
    </ProtectedPage>
  )
}
