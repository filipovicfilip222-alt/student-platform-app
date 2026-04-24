/**
 * sidebar.tsx — Role-aware left navigation column.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * Reads `NAV_ITEMS[role]` from `lib/constants/nav-items.ts`. Renders the
 * app logo on top and a footer role label (helps QA spot which sidebar
 * variant is showing during role switching).
 *
 * The desktop sidebar is rendered as a permanent column; the mobile
 * variant (Sheet) calls the same component inside `<AppShell>`'s mobile
 * drawer. Both share this layout, only the wrapper differs.
 */

"use client"

import { GraduationCap, LogOut } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { NAV_ITEMS } from "@/lib/constants/nav-items"
import { roleLabel } from "@/lib/constants/roles"
import { ROUTES } from "@/lib/constants/routes"
import { useLogout } from "@/lib/hooks/use-auth"
import { useAuthStore } from "@/lib/stores/auth"
import { cn } from "@/lib/utils"
import { toastApiError } from "@/lib/utils/errors"
import type { Role } from "@/types/common"

import { SidebarNavItem } from "./sidebar-nav-item"

export interface SidebarProps {
  role: Role
  /** Destination of the logo click (defaults to role home). */
  homeHref?: string
  /** Called after any nav item click; used by mobile drawer to close itself. */
  onNavigate?: () => void
  className?: string
}

const ROLE_HOME: Record<Role, string> = {
  STUDENT: ROUTES.dashboard,
  PROFESOR: ROUTES.professorDashboard,
  ASISTENT: ROUTES.professorDashboard,
  ADMIN: ROUTES.admin,
}

export function Sidebar({
  role,
  homeHref,
  onNavigate,
  className,
}: SidebarProps) {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()
  const items = NAV_ITEMS[role]
  const href = homeHref ?? ROLE_HOME[role]

  async function handleLogout() {
    try {
      await logout.mutateAsync()
    } catch (err) {
      toastApiError(err, "Odjava nije potvrđena sa serverom")
    } finally {
      onNavigate?.()
      router.replace(ROUTES.login)
    }
  }

  return (
    <aside
      className={cn(
        "flex h-full w-60 shrink-0 flex-col border-r border-border bg-background",
        className
      )}
      aria-label="Glavna navigacija"
    >
      <Link
        href={href}
        onClick={onNavigate}
        className="flex h-14 items-center gap-2 border-b border-border px-4 font-semibold tracking-tight"
      >
        <GraduationCap className="size-5 text-primary" aria-hidden />
        <span className="truncate">Konsultacije</span>
      </Link>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {items.map((item) => (
          <SidebarNavItem
            key={item.href}
            item={item}
            onNavigate={onNavigate}
          />
        ))}
      </nav>

      <div className="space-y-2 border-t border-border px-3 py-3">
        {user && (
          <div className="px-1 pb-1 text-xs leading-tight">
            <div className="truncate font-medium text-foreground">
              {`${user.first_name} ${user.last_name}`.trim()}
            </div>
            <div className="truncate text-muted-foreground">{user.email}</div>
          </div>
        )}

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          disabled={logout.isPending}
          className="w-full justify-start gap-2 text-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <LogOut aria-hidden />
          {logout.isPending ? "Odjavljivanje…" : "Odjavi se"}
        </Button>

        <div className="px-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {roleLabel(role)}
        </div>
      </div>
    </aside>
  )
}
