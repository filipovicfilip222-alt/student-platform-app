/**
 * (student)/dashboard/page.tsx — Student landing posle login-a.
 *
 * KORAK 3 (Faza 3.2 polish):
 *   - GreetingHeader (vremenski-zavisan pozdrav + datum)
 *   - NextAppointmentHero (countdown + akcije, ako postoji predstojeći termin)
 *   - QuickActionsGrid (4 ikon-CTA: Pretraga, Termini, Dokumenti, Profil)
 *   - 2-col grid: RecentNotificationsCard + StrikeStatusCard
 *   - Lista preostalih sledećih termina (od drugog naviše)
 *
 * Notifikacije i strike-points još uvek koriste isti hook stack — strike
 * data i dalje hard-kodirana na 0 dok backend `/auth/me` ne doda
 * `total_strike_points` (FRONTEND_STRUKTURA.md § 7.3).
 */

"use client"

import Link from "next/link"
import {
  ArrowRight,
  CalendarPlus,
  CalendarRange,
  FileClock,
  Search,
  UserCog,
} from "lucide-react"

import { AppointmentCard } from "@/components/appointments/appointment-card"
import { GreetingHeader } from "@/components/dashboard/greeting-header"
import { NextAppointmentHero } from "@/components/dashboard/next-appointment-hero"
import {
  QuickActionsGrid,
  type QuickAction,
} from "@/components/dashboard/quick-actions-grid"
import { RecentNotificationsCard } from "@/components/dashboard/recent-notifications-card"
import { StrikeStatusCard } from "@/components/dashboard/strike-status-card"
import { EmptyState } from "@/components/shared/empty-state"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useMyAppointments } from "@/lib/hooks/use-appointments"
import { ROUTES } from "@/lib/constants/routes"
import { useAuthStore } from "@/lib/stores/auth"

const QUICK_ACTIONS: QuickAction[] = [
  {
    href: ROUTES.search,
    title: "Pretraga profesora",
    description: "Pronađi profesora i slobodan termin.",
    icon: Search,
    tone: "primary",
  },
  {
    href: ROUTES.myAppointments,
    title: "Moji termini",
    description: "Lista predstojećih i prošlih konsultacija.",
    icon: CalendarRange,
    tone: "info",
  },
  {
    href: ROUTES.documentRequests,
    title: "Dokumenti",
    description: "Zahtevi za potvrde i transkripte.",
    icon: FileClock,
    tone: "accent",
  },
  {
    href: ROUTES.search,
    title: "Brzo zakazivanje",
    description: "Najpopularniji slobodni termini ove nedelje.",
    icon: CalendarPlus,
    tone: "success",
  },
]

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const appointmentsQuery = useMyAppointments("upcoming")

  const appointments = appointmentsQuery.data ?? []
  const [next, ...rest] = appointments
  const remaining = rest.slice(0, 2)

  return (
    <div className="space-y-8">
      <GreetingHeader
        firstName={user?.first_name}
        fallbackName="studente"
        actions={
          <Button asChild>
            <Link href={ROUTES.search}>
              <CalendarPlus aria-hidden />
              Zakaži konsultacije
            </Link>
          </Button>
        }
      />

      {/* HERO row: next appointment ili friendly empty state */}
      <section aria-labelledby="next-appointment-heading">
        <h2 id="next-appointment-heading" className="sr-only">
          Sledeći termin
        </h2>

        {appointmentsQuery.isLoading ? (
          <Skeleton className="h-[180px] w-full rounded-2xl" />
        ) : next ? (
          <NextAppointmentHero appointment={next} />
        ) : (
          <EmptyState
            icon={CalendarRange}
            title="Nemate zakazane termine"
            description="Pronađite profesora i rezervišite prvi slot kroz pretragu."
            action={
              <Button asChild>
                <Link href={ROUTES.search}>Otvori pretragu</Link>
              </Button>
            }
          />
        )}
      </section>

      {/* Quick actions */}
      <section aria-labelledby="quick-actions-heading" className="space-y-3">
        <h2
          id="quick-actions-heading"
          className="text-sm font-semibold uppercase tracking-wide text-muted-foreground"
        >
          Brzi pristup
        </h2>
        <QuickActionsGrid actions={QUICK_ACTIONS} />
      </section>

      {/* 2-col: Notifs + Strike */}
      <section className="grid gap-4 lg:grid-cols-2">
        <RecentNotificationsCard limit={5} />
        {/* TODO: wire to /auth/me.total_strike_points + .blocked_until once
            backend UserResponse exposes the fields (FRONTEND_STRUKTURA § 7.3). */}
        <StrikeStatusCard points={0} blockedUntil={null} />
      </section>

      {/* Remaining upcoming appointments — sve preko prvog */}
      {remaining.length > 0 && (
        <section aria-labelledby="more-upcoming-heading" className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2
                id="more-upcoming-heading"
                className="text-lg font-semibold tracking-tight"
              >
                Još predstojećih termina
              </h2>
              <p className="text-sm text-muted-foreground">
                Otvorite stavku za detalje ili otkazivanje.
              </p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link href={ROUTES.myAppointments}>
                Svi termini
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          </div>
          <div className="space-y-2">
            {remaining.map((appt) => (
              <AppointmentCard key={appt.id} appointment={appt} />
            ))}
          </div>
        </section>
      )}

      {/* Profile link footer */}
      <div className="flex items-center justify-end">
        <Button asChild variant="ghost" size="sm">
          <Link href="#" aria-disabled>
            <UserCog aria-hidden />
            Podešavanja profila (uskoro)
          </Link>
        </Button>
      </div>
    </div>
  )
}
