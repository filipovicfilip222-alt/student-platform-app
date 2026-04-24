/**
 * page.tsx — Professor dashboard (ROADMAP 3.7, Faza 4 frontend).
 *
 * Two tabs:
 *   - "Inbox zahteva" — incoming appointment requests + approve/reject/delegate.
 *   - "Moj kalendar"  — editable availability calendar.
 *
 * Layout is guarded by the (professor) layout.tsx which requires
 * PROFESOR or ASISTENT. RBAC is re-applied inside RequestsInbox /
 * AvailabilityCalendar via RoleGate for action-level affordances.
 */

"use client"

import { CalendarRange, Inbox } from "lucide-react"

import { PageHeader } from "@/components/shared/page-header"
import { AvailabilityCalendar } from "@/components/calendar/availability-calendar"
import { RequestsInbox } from "@/components/professor/requests-inbox"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function ProfessorDashboardPage() {
  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 p-6 sm:p-8">
      <PageHeader
        title="Dashboard"
        description="Upravljajte zahtevima studenata i vašom dostupnošću."
      />

      <Tabs defaultValue="inbox" className="space-y-4">
        <TabsList>
          <TabsTrigger value="inbox">
            <Inbox aria-hidden />
            Inbox zahteva
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
    </main>
  )
}
