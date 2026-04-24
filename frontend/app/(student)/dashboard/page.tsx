/**
 * (student)/dashboard/page.tsx — Student landing after login.
 *
 * ROADMAP 3.2 / Faza 3.2.
 *
 * Three cards per PRD §2.1:
 *   1. "Sledeći termini" — top 3 upcoming appointments (TanStack Query).
 *   2. "Nepročitane notifikacije" — unread counter.
 *   3. "Strike status" — points + block indicator.
 *
 * The notifications query is expected to fail until ROADMAP 4.2 ships
 * the backend stream — `useUnreadCount` returns null on error, and we
 * render a placeholder. Strike data is hard-coded to 0 pending the
 * `/auth/me` schema extension (see FRONTEND_STRUKTURA.md § 7.3).
 */

"use client"

import Link from "next/link"
import {
  ArrowRight,
  BellDot,
  CalendarPlus,
  CalendarRange,
} from "lucide-react"

import { AppointmentCard } from "@/components/appointments/appointment-card"
import { EmptyState } from "@/components/shared/empty-state"
import { PageHeader } from "@/components/shared/page-header"
import { StrikeDisplay } from "@/components/shared/strike-display"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useMyAppointments } from "@/lib/hooks/use-appointments"
import { useUnreadCount } from "@/lib/hooks/use-notifications"
import { ROUTES } from "@/lib/constants/routes"
import { useAuthStore } from "@/lib/stores/auth"

const UPCOMING_LIMIT = 3

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const appointmentsQuery = useMyAppointments("upcoming")
  const unreadQuery = useUnreadCount()

  const greetingName = user?.first_name ?? "studente"
  const appointments = appointmentsQuery.data ?? []
  const upcoming = appointments.slice(0, UPCOMING_LIMIT)

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Dobrodošli, ${greetingName}`}
        description="Brz pregled predstojećih termina i obaveštenja."
      >
        <Button asChild>
          <Link href={ROUTES.search}>
            <CalendarPlus aria-hidden />
            Zakaži nove konsultacije
          </Link>
        </Button>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-3">
        <NotificationsCard
          unread={unreadQuery.data ?? null}
          isLoading={unreadQuery.isLoading}
          isError={unreadQuery.isError}
        />
        <StrikeCard />
        <UpcomingCountCard
          count={appointments.length}
          isLoading={appointmentsQuery.isLoading}
        />
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">
              Sledeći termini
            </h2>
            <p className="text-sm text-muted-foreground">
              Prva tri predstojeća termina. Kliknite za detalje ili otvorite
              celu listu.
            </p>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href={ROUTES.myAppointments}>
              Svi termini
              <ArrowRight aria-hidden />
            </Link>
          </Button>
        </div>

        {appointmentsQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-[88px] w-full rounded-lg" />
            <Skeleton className="h-[88px] w-full rounded-lg" />
            <Skeleton className="h-[88px] w-full rounded-lg" />
          </div>
        ) : appointmentsQuery.isError ? (
          <EmptyState
            icon={CalendarRange}
            title="Greška pri učitavanju termina"
            description="Osvežite stranicu ili pokušajte ponovo za par sekundi."
          />
        ) : upcoming.length === 0 ? (
          <EmptyState
            icon={CalendarRange}
            title="Nemate zakazane termine"
            description="Pronađite profesora i rezervišite prvi slot kroz pretragu."
            action={
              <Button asChild size="sm">
                <Link href={ROUTES.search}>Otvori pretragu</Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-2">
            {upcoming.map((appt) => (
              <AppointmentCard key={appt.id} appointment={appt} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

// ── Summary cards ───────────────────────────────────────────────────────────

function NotificationsCard({
  unread,
  isLoading,
  isError,
}: {
  unread: number | null
  isLoading: boolean
  isError: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">
          Nepročitane notifikacije
        </CardTitle>
        <BellDot className="size-4 text-muted-foreground" aria-hidden />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-12" />
        ) : isError || unread === null ? (
          <>
            <div className="text-2xl font-bold">—</div>
            <CardDescription className="mt-1">
              Dostupno kada backend stream bude aktivan.
            </CardDescription>
          </>
        ) : (
          <>
            <div className="text-2xl font-bold">{unread}</div>
            <CardDescription className="mt-1">
              {unread === 0 ? "Sve je pregledano." : "Otvorite zvonce u gornjem meniju."}
            </CardDescription>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function StrikeCard() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Strike status</CardTitle>
      </CardHeader>
      <CardContent>
        {/* TODO: wire to `/auth/me.total_strike_points` once backend
            UserResponse exposes it (FRONTEND_STRUKTURA.md § 7.3). */}
        <StrikeDisplay points={0} blockedUntil={null} />
      </CardContent>
    </Card>
  )
}

function UpcomingCountCard({
  count,
  isLoading,
}: {
  count: number
  isLoading: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">
          Predstojećih termina
        </CardTitle>
        <CalendarRange className="size-4 text-muted-foreground" aria-hidden />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-12" />
        ) : (
          <>
            <div className="text-2xl font-bold">{count}</div>
            <CardDescription className="mt-1">
              Aktivni i odobreni zakazani termini.
            </CardDescription>
          </>
        )}
      </CardContent>
    </Card>
  )
}
