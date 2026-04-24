/**
 * impersonation-banner.tsx — Sticky red banner shown while an ADMIN is
 * viewing the app as another user.
 *
 * ROADMAP 2.2 / §3.6 Impersonation flow.
 *
 * Logic:
 *  - Reads `useImpersonationStore` for the active impersonation session.
 *  - When `isImpersonating === true`, renders a fixed banner on top of
 *    the entire viewport with the impersonated user's name + an "Izađi"
 *    action that calls `useEndImpersonation`.
 *  - `AppShell` adds `pt-10` to the layout when the banner is visible so
 *    content doesn't hide behind it.
 */

"use client"

import { ShieldAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useEndImpersonation } from "@/lib/hooks/use-impersonation"
import { useAuthStore } from "@/lib/stores/auth"
import { useImpersonationStore } from "@/lib/stores/impersonation"
import { toastApiError } from "@/lib/utils/errors"

export function ImpersonationBanner() {
  const isImpersonating = useImpersonationStore((s) => s.isImpersonating)
  const originalUser = useImpersonationStore((s) => s.originalUser)
  const currentUser = useAuthStore((s) => s.user)
  const endImpersonation = useEndImpersonation()

  if (!isImpersonating) return null

  const impersonatedName = currentUser
    ? `${currentUser.first_name} ${currentUser.last_name}`.trim()
    : "—"
  const adminName = originalUser
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
            (prijavljeni kao {adminName})
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
