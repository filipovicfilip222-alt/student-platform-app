/**
 * (admin)/layout.tsx — Route-group layout for ADMIN pages.
 *
 * ROADMAP 2.2 — layouti po roli.
 * ADMIN is the only role allowed. When an admin impersonates a regular
 * user, ProtectedPage will redirect them out of /admin/** to the target
 * user's home — that's intentional (they can't use admin tools while
 * pretending to be a student).
 */

import { AppShell } from "@/components/shared/app-shell"
import { ProtectedPage } from "@/components/shared/protected-page"

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ProtectedPage allowedRoles={["ADMIN"]}>
      <AppShell role="ADMIN">{children}</AppShell>
    </ProtectedPage>
  )
}
