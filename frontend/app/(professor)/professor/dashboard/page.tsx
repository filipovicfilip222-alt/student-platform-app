/**
 * (professor)/professor/dashboard/page.tsx — Professor / Asistent landing.
 *
 * KORAK 3 polish:
 *   - GreetingHeader (vremenski-zavisan + Inter font hijerarhija)
 *   - 3-card metrics row: pending requests count + nedeljni overview slot
 *     + RecentNotificationsCard (deli isti hook stack kao student dashboard)
 *   - Tabovi (Inbox + Calendar) ostaju ispod — funkcionalnost se ne dira,
 *     vizuelno se samo polish-uje wrapper.
 *
 * Layout je guarded od strane (professor)/layout.tsx koji zahteva PROFESOR
 * ili ASISTENT. RBAC se re-applay-uje unutar RequestsInbox /
 * AvailabilityCalendar kroz RoleGate za action-level affordances.
 */

"use client"

import { CalendarRange, Inbox, MailWarning } from "lucide-react"

import { AvailabilityCalendar } from "@/components/calendar/availability-calendar"
import { GreetingHeader } from "@/components/dashboard/greeting-header"
import { RecentNotificationsCard } from "@/components/dashboard/recent-notifications-card"
import { RequestsInbox } from "@/components/professor/requests-inbox"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useRequestsInbox } from "@/lib/hooks/use-requests-inbox"
import { useAuthStore } from "@/lib/stores/auth"

export default function ProfessorDashboardPage() {
  const user = useAuthStore((s) => s.user)
  const inboxQuery = useRequestsInbox("PENDING")

  const pendingCount = inboxQuery.data?.length ?? 0
  const isLoading = inboxQuery.isLoading

  return (
    <div className="space-y-8">
      <GreetingHeader
        firstName={user?.first_name}
        fallbackName={user?.role === "ASISTENT" ? "asistente" : "profesore"}
      />

      <section className="grid gap-4 md:grid-cols-3">
        <PendingRequestsCard count={pendingCount} isLoading={isLoading} />
        <UpcomingWeekCard />
        <RecentNotificationsCard limit={4} className="row-span-1" />
      </section>

      <Tabs defaultValue="inbox" className="space-y-4">
        <TabsList>
          <TabsTrigger value="inbox">
            <Inbox aria-hidden />
            Inbox zahteva
            {pendingCount > 0 && (
              <span className="ml-1.5 inline-flex size-5 items-center justify-center rounded-full bg-accent/30 text-[10px] font-semibold text-accent-foreground dark:text-accent">
                {pendingCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="calendar">
            <CalendarRange aria-hidden />
            Moj kalendar
          </TabsTrigger>
        </TabsList>

        <TabsContent value="inbox" className="space-y-4">
          <RequestsInbox />
        </TabsContent>

        <TabsContent value="calendar" className="space-y-4">
          <AvailabilityCalendar />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ── Metric cards ─────────────────────────────────────────────────────────────

function PendingRequestsCard({
  count,
  isLoading,
}: {
  count: number
  isLoading: boolean
}) {
  const isEmpty = !isLoading && count === 0
  return (
    <Card className="relative overflow-hidden">
      {/* Amber accent stripe na vrhu kartice. */}
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-1 bg-accent"
      />
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 pt-5">
        <CardTitle className="text-sm font-medium">
          Zahtevi na čekanju
        </CardTitle>
        <MailWarning className="size-4 text-accent" aria-hidden />
      </CardHeader>
      <CardContent className="space-y-1.5">
        {isLoading ? (
          <Skeleton className="h-8 w-12" />
        ) : (
          <p className="text-3xl font-bold tracking-tight">{count}</p>
        )}
        <p className="text-xs text-muted-foreground">
          {isEmpty
            ? "Nema novih zahteva. Ažurirano u realnom vremenu."
            : "Otvorite Inbox dole za odobrenje, odbijanje ili delegaciju."}
        </p>
      </CardContent>
    </Card>
  )
}

function UpcomingWeekCard() {
  // Phase 6 polish: real "ova nedelja" count iz availability+booking-a.
  // Trenutno renderujemo placeholder sa CTA da otvori kalendar.
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">Ova nedelja</CardTitle>
        <CalendarRange className="size-4 text-primary" aria-hidden />
      </CardHeader>
      <CardContent className="space-y-1.5">
        <p className="text-3xl font-bold tracking-tight text-foreground">—</p>
        <p className="text-xs text-muted-foreground">
          Pregled termina i blokova u tabu „Moj kalendar".
        </p>
      </CardContent>
    </Card>
  )
}
