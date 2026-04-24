/**
 * top-bar.tsx — Logged-in top navigation bar.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * Contents (L→R):
 *  - Mobile hamburger slot (provided by AppShell via children so the
 *    shell can wire it up to its <Sheet> state).
 *  - NotificationCenter bell (placeholder until Phase 5).
 *  - UserMenu (avatar + dropdown with logout).
 *
 * A global search box is planned for the top bar in Phase 6 (Google PSE
 * integration — ROADMAP 5.1). For now the middle of the bar is empty.
 */

"use client"

import type { ReactNode } from "react"

import { NotificationCenter } from "@/components/notifications/notification-center"
import { cn } from "@/lib/utils"

import { UserMenu } from "./user-menu"

export interface TopBarProps {
  /** Optional slot rendered at the very start of the bar (mobile menu). */
  leading?: ReactNode
  className?: string
}

export function TopBar({ leading, className }: TopBarProps) {
  return (
    <header
      className={cn(
        "flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border bg-background px-4",
        className
      )}
    >
      <div className="flex min-w-0 items-center gap-2">{leading}</div>

      <div className="flex items-center gap-1">
        <NotificationCenter />
        <UserMenu />
      </div>
    </header>
  )
}
