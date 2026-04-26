/**
 * (admin)/admin/page.tsx — ADMIN dashboard landing.
 *
 * KORAK 3 polish:
 *   - GreetingHeader (vremenski-zavisan)
 *   - AdminDashboardMetrics (postojeća komponenta — header chrome se ne dira)
 *   - 2-col grid: Brzi pristup (5 sekcija) + Recent notifications
 *
 * AdminDashboardMetrics već gracefulno hendluje 404 na `/admin/overview`
 * dok ROADMAP 4.7 ne zatvori taj endpoint.
 */

"use client"

import Link from "next/link"
import {
  ClipboardList,
  FileClock,
  Megaphone,
  ShieldAlert,
  Users,
} from "lucide-react"

import { AdminDashboardMetrics } from "@/components/admin/admin-dashboard-metrics"
import { GreetingHeader } from "@/components/dashboard/greeting-header"
import { RecentNotificationsCard } from "@/components/dashboard/recent-notifications-card"
import { ROUTES } from "@/lib/constants/routes"
import { useAuthStore } from "@/lib/stores/auth"

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
  const user = useAuthStore((s) => s.user)

  return (
    <div className="space-y-8 p-6">
      <GreetingHeader
        firstName={user?.first_name}
        fallbackName="administratore"
        subtitle="Platformski overview — ključne metrike i brzi pristup."
      />

      <AdminDashboardMetrics />

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
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
                  className="group flex items-start gap-3 rounded-xl border border-border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-[0_4px_16px_-4px_hsl(var(--primary)/0.18)]"
                >
                  <div className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-transform group-hover:scale-110">
                    <Icon className="size-5" aria-hidden />
                  </div>
                  <div className="space-y-0.5">
                    <div className="text-sm font-semibold group-hover:text-primary">
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
        </div>

        <RecentNotificationsCard limit={4} className="lg:col-span-1" />
      </section>
    </div>
  )
}
