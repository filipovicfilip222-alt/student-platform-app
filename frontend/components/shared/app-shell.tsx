/**
 * app-shell.tsx — Single frame for every authenticated page.
 *
 * ROADMAP 2.2 — shared shell primitives.
 * Mirrors the structure from docs/FRONTEND_STRUKTURA.md §3.3:
 *
 *   <ImpersonationBanner />            (fixed, only when impersonating)
 *   <div flex h-screen>
 *     <Sidebar role />                 (hidden on mobile; shown in Sheet)
 *     <main column>
 *       <TopBar />
 *       <main scroll>{children}</main>
 *     </main>
 *   </div>
 *
 * The `role` prop drives which sidebar is rendered. For the (professor)
 * route group we pass role="PROFESOR" regardless of whether the user is
 * a PROFESOR or ASISTENT — both share the same nav items in the current
 * design (open question §7.5 in FRONTEND_STRUKTURA.md).
 */

"use client"

import { Menu } from "lucide-react"
import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { useImpersonationStore } from "@/lib/stores/impersonation"
import { cn } from "@/lib/utils"
import type { Role } from "@/types/common"

import { ImpersonationBanner } from "./impersonation-banner"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"

export interface AppShellProps {
  /** Which role's sidebar to render (matches the route group). */
  role: Role
  children: ReactNode
}

export function AppShell({ role, children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const isImpersonating = useImpersonationStore((s) => s.isImpersonating)

  return (
    <div
      className={cn(
        "flex h-dvh flex-col bg-muted/30",
        // Make room for the fixed impersonation banner.
        isImpersonating && "pt-10"
      )}
    >
      <ImpersonationBanner />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Desktop sidebar ─────────────────────────────────────────── */}
        <div className="hidden md:block">
          <Sidebar role={role} />
        </div>

        {/* ── Mobile sidebar (Sheet drawer) ───────────────────────────── */}
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-60 p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>Navigacija</SheetTitle>
              <SheetDescription>
                Glavni meni aplikacije
              </SheetDescription>
            </SheetHeader>
            <Sidebar
              role={role}
              onNavigate={() => setMobileOpen(false)}
              className="w-full border-r-0"
            />
          </SheetContent>

          {/* ── Main column ─────────────────────────────────────────── */}
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar
              leading={
                <SheetTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Otvori navigaciju"
                    className="md:hidden"
                  >
                    <Menu aria-hidden />
                  </Button>
                </SheetTrigger>
              }
            />

            <main className="flex-1 overflow-y-auto bg-muted/30 p-4 sm:p-6">
              {children}
            </main>
          </div>
        </Sheet>
      </div>
    </div>
  )
}
