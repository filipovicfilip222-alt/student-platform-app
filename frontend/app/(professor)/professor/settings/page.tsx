/**
 * page.tsx — Professor settings (ROADMAP 3.7, Faza 4 frontend).
 *
 * Four tabs:
 *   - Profil          — editable self-profile + auto-approve toggles.
 *   - FAQ             — public Q&A on the student-facing professor profile.
 *   - Canned          — reply templates used in rejection dialog + chat.
 *   - Blackout        — date-range periods during which slots are hidden.
 *
 * Route group (professor) layout lets both PROFESOR and ASISTENT in,
 * but Settings is PROFESOR-only conceptually — we hard-enforce this via
 * a nested ProtectedPage so ASISTENT gets redirected to their dashboard.
 */

"use client"

import {
  CalendarOff,
  HelpCircle,
  MessageSquareQuote,
  UserCog,
} from "lucide-react"

import { PageHeader } from "@/components/shared/page-header"
import { ProtectedPage } from "@/components/shared/protected-page"
import { BlackoutManager } from "@/components/professor/blackout-manager"
import { CannedResponseList } from "@/components/professor/canned-response-list"
import { FaqList } from "@/components/professor/faq-list"
import { ProfileForm } from "@/components/professor/profile-form"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function ProfessorSettingsPage() {
  return (
    <ProtectedPage allowedRoles={["PROFESOR"]}>
      <main className="mx-auto w-full max-w-5xl space-y-6 p-6 sm:p-8">
        <PageHeader
          title="Podešavanja"
          description="Profil, FAQ, šabloni odgovora i blackout periodi."
        />

        <Tabs defaultValue="profile" className="space-y-4">
          <TabsList>
            <TabsTrigger value="profile">
              <UserCog aria-hidden />
              Profil
            </TabsTrigger>
            <TabsTrigger value="faq">
              <HelpCircle aria-hidden />
              FAQ
            </TabsTrigger>
            <TabsTrigger value="canned">
              <MessageSquareQuote aria-hidden />
              Šabloni
            </TabsTrigger>
            <TabsTrigger value="blackout">
              <CalendarOff aria-hidden />
              Blackout
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profile">
            <ProfileForm />
          </TabsContent>
          <TabsContent value="faq">
            <FaqList />
          </TabsContent>
          <TabsContent value="canned">
            <CannedResponseList />
          </TabsContent>
          <TabsContent value="blackout">
            <BlackoutManager />
          </TabsContent>
        </Tabs>
      </main>
    </ProtectedPage>
  )
}
