/**
 * sidebar-nav-item.tsx — Individual sidebar link with active state.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * The active check matches on the literal href for "leaf" routes and on
 * prefix for nested pages (e.g. "/admin/users/abc" still highlights the
 * "/admin/users" sidebar entry). Root "/admin" matches exactly to avoid
 * lighting up on every admin sub-page.
 */

"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import type { NavItem } from "@/lib/constants/nav-items"
import { cn } from "@/lib/utils"

export interface SidebarNavItemProps {
  item: NavItem
  onNavigate?: () => void
}

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/"
  if (pathname === href) return true
  return pathname.startsWith(href + "/")
}

export function SidebarNavItem({ item, onNavigate }: SidebarNavItemProps) {
  const pathname = usePathname()
  const active = isActive(pathname, item.href)
  const Icon = item.icon

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-primary text-primary-foreground shadow-sm"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      <Icon
        className={cn(
          "size-4 shrink-0",
          active
            ? "text-primary-foreground"
            : "text-muted-foreground group-hover:text-foreground"
        )}
        aria-hidden
      />
      <span className="truncate">{item.label}</span>
    </Link>
  )
}
