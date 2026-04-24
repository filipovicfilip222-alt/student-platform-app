/**
 * impersonation-banner.tsx — Sticky red banner shown while an ADMIN is
 * viewing the app as another user.
 *
 * ROADMAP 2.2 / 4.4 + docs/FRONTEND_STRUKTURA.md §3.6 +
 * docs/websocket-schema.md §6.
 *
 * Logic:
 *  - Reads `useImpersonationStore` for the active impersonation session.
 *    Admin email + name come from the `imp_email` / `imp_name` claims on
 *    the impersonation JWT (stored there by `useStartImpersonation`).
 *  - Renders a fixed banner on top of the entire viewport with the
 *    impersonated user's name + an "Izađi" action that calls
 *    `useEndImpersonation` (which POSTs /admin/impersonate/end).
 *  - AppShell adds `pt-10` to the layout when the banner is visible so
 *    content does not hide behind it.
 *
 * Self-healing: if the access token in the auth store silently loses
 * its `imp` claim (e.g. impersonation token expired → axios interceptor
 * refreshed us back to a plain admin token), we clear the impersonation
 * store so the banner stops showing. Backend stays authoritative — the
 * banner only reflects what the current token claims.
 */

"use client"

import { useEffect } from "react"
import { ShieldAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useEndImpersonation } from "@/lib/hooks/use-impersonation"
import { useAuthStore } from "@/lib/stores/auth"
import { useImpersonationStore } from "@/lib/stores/impersonation"
import { toastApiError } from "@/lib/utils/errors"
import { isImpersonationToken } from "@/lib/utils/jwt"

export function ImpersonationBanner() {
  const isImpersonating = useImpersonationStore((s) => s.isImpersonating)
  const storedAdminName = useImpersonationStore((s) => s.adminName)
  const originalUser = useImpersonationStore((s) => s.originalUser)
  const clearImpersonation = useImpersonationStore((s) => s.clearImpersonation)

  const currentUser = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)

  const endImpersonation = useEndImpersonation()

  // Self-heal: if the active token no longer carries the `imp` claim
  // (e.g. impersonation expired → /auth/refresh gave us the admin token
  // back), clear the banner state. Keeps UI in sync with the backend
  // authoritative RBAC.
  useEffect(() => {
    if (!isImpersonating) return
    if (!accessToken) return
    if (!isImpersonationToken(accessToken)) {
      clearImpersonation()
    }
  }, [isImpersonating, accessToken, clearImpersonation])

  if (!isImpersonating) return null

  const impersonatedName = currentUser
    ? `${currentUser.first_name} ${currentUser.last_name}`.trim()
    : "—"
  // Prefer the `imp_name` claim stored in the impersonation store (§6.2);
  // fall back to the pre-swap admin UserResponse if the claim was missing.
  const adminName =
    storedAdminName && storedAdminName.length > 0
      ? storedAdminName
      : originalUser
        ? `${originalUser.first_name} ${originalUser.last_name}`.trim()
        : "Admin"

  async function handleExit() {
    try {
      await endImpersonation.mutateAsync()
    } catch (err) {
      toastApiError(err, "Neuspelo vraćanje iz ADMIN MODE")
    }
  }

  return (
    <div
      role="alert"
      className="fixed inset-x-0 top-0 z-50 flex h-10 items-center justify-between gap-4 border-b border-red-700/40 bg-red-600 px-4 text-sm font-medium text-white shadow-sm"
    >
      <div className="flex min-w-0 items-center gap-2">
        <ShieldAlert className="size-4 shrink-0" aria-hidden />
        <span className="truncate">
          ADMIN MODE — Impersonirate <strong>{impersonatedName}</strong>
          <span className="ml-1 hidden text-red-100 sm:inline">
            • Admin: {adminName}
          </span>
        </span>
      </div>

      <Button
        size="sm"
        variant="secondary"
        className="bg-white text-red-700 hover:bg-red-50"
        onClick={() => void handleExit()}
        disabled={endImpersonation.isPending}
      >
        {endImpersonation.isPending ? "Izlazim…" : "Izađi"}
      </Button>
    </div>
  )
}
