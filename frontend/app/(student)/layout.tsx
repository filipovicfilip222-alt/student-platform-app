/**
 * (student)/layout.tsx — Route-group layout for STUDENT pages.
 *
 * ROADMAP 2.2 — layouti po roli.
 * Wraps the group in <ProtectedPage> (auth + role guard with redirect)
 * and <AppShell role="STUDENT"> (sidebar + top bar + impersonation
 * banner). Pages inside just focus on content.
 */

import { AppShell } from "@/components/shared/app-shell"
import { ProtectedPage } from "@/components/shared/protected-page"

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ProtectedPage allowedRoles={["STUDENT"]}>
      <AppShell role="STUDENT">{children}</AppShell>
    </ProtectedPage>
  )
}
