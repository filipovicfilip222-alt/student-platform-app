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

import { GraduationCap } from "lucide-react"
import Link from "next/link"

import { NAV_ITEMS } from "@/lib/constants/nav-items"
import { roleLabel } from "@/lib/constants/roles"
import { ROUTES } from "@/lib/constants/routes"
import { cn } from "@/lib/utils"
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
  const items = NAV_ITEMS[role]
  const href = homeHref ?? ROLE_HOME[role]

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

      <div className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
        <span className="font-medium uppercase tracking-wide">
          {roleLabel(role)}
        </span>
      </div>
    </aside>
  )
}
