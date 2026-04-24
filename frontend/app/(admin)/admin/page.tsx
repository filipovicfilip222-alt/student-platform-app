/**
 * (admin)/admin/page.tsx — ADMIN dashboard landing.
 *
 * ROADMAP 4.7 — platform overview. Displays headline metrics at the top
 * (AdminDashboardMetrics — reads /admin/overview, degrades gracefully
 * when the endpoint is not yet live) plus quick-link tiles into the
 * subsections that actually exist in the current admin shell.
 */

import Link from "next/link"
import {
  ClipboardList,
  FileClock,
  Megaphone,
  ShieldAlert,
  Users,
} from "lucide-react"

import { AdminDashboardMetrics } from "@/components/admin/admin-dashboard-metrics"
import { PageHeader } from "@/components/shared/page-header"
import { ROUTES } from "@/lib/constants/routes"

const QUICK_LINKS = [
  {
    href: ROUTES.adminUsers,
    title: "Korisnici",
    description: "CRUD, bulk import, impersonacija.",
    icon: Users,
  },
  {
    href: ROUTES.adminDocumentRequests,
    title: "Zahtevi za dokumente",
    description: "Odobrenje ili odbijanje potvrda.",
    icon: FileClock,
  },
  {
    href: ROUTES.adminStrikes,
    title: "Strike registar",
    description: "Pregled aktivnih blokada i odblokiranje.",
    icon: ShieldAlert,
  },
  {
    href: ROUTES.adminBroadcast,
    title: "Obaveštenja",
    description: "Slanje poruka svim korisnicima ili po roli.",
    icon: Megaphone,
  },
  {
    href: ROUTES.adminAuditLog,
    title: "Audit log",
    description: "Trag svih administrativnih akcija.",
    icon: ClipboardList,
  },
] as const

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Admin dashboard"
        description="Platformski overview — ključne metrike i brzi pristup."
      />

      <AdminDashboardMetrics />

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Brzi pristup
        </h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {QUICK_LINKS.map((item) => {
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className="group flex items-start gap-3 rounded-lg border border-border bg-background p-4 transition hover:border-primary/60 hover:bg-muted/40"
              >
                <div className="mt-0.5 flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Icon className="size-5" aria-hidden />
                </div>
                <div>
                  <div className="font-semibold group-hover:text-primary">
                    {item.title}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {item.description}
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </section>
    </div>
  )
}
