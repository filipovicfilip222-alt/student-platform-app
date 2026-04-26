# Frontend struktura — Studentska Platforma (FON/ETF)

**Verzija:** 1.1 (sesija 2026-04-26 — vidi § 8 za changelog)
**Referentni dokumenti:** `docs/PRD_Studentska_Platforma.md`, `docs/Arhitektura_i_Tehnoloski_Stek.md`, `docs/ROADMAP.md`, `docs/copilot_plan_prompt.md`
**Stack:** Next.js 14 (App Router) · TypeScript · **Tailwind CSS v4** · Shadcn/ui · TanStack Query · Zustand · React Hook Form + Zod · Axios · FullCalendar · socket.io-client · next-pwa

Ovaj dokument opisuje **kompletnu ciljnu strukturu** `frontend/` direktorijuma — šta postoji, šta fali i kako treba organizovati. Sinhronizovan sa stanjem iz `ROADMAP.md`. Svaki novi fajl u frontendu treba da se uklapa u jednu od kategorija ispod.

---

## 1. Osnovna filozofija

1. **Jedan source of truth po sloju:** tipovi u `types/`, API pozivi u `lib/api/`, server state u `lib/hooks/`, client state u `lib/stores/`, UI u `components/`. Stranice u `app/` su tanke — čitaju hook-ove i renderuju komponente.
2. **Route groupe po roli:** `(auth)`, `(student)`, `(professor)`, `(admin)`. Svaka grupa ima svoj `layout.tsx` koji omotava `<AppShell role="...">`.
3. **RBAC na klijentu je UX filter, ne bezbednost.** Pravi RBAC je backend. Middleware + layout samo preusmeravaju korisnika.
4. **Access token u memoriji (Zustand), refresh token u httpOnly cookie-ju.** Nikad `localStorage` — zbog XSS-a i zato što arhitektura to eksplicitno zabranjuje.
5. **Forme:** `react-hook-form` + `zod` resolver. Svaka forma ima svoju zod šemu pored komponente.
6. **Server state:** isključivo TanStack Query (`useQuery`/`useMutation`). Nikad ručno `useEffect + fetch` po stranicama.
7. **Stil:** Tailwind utility klase. Shadcn komponente u `components/ui/` su jedine izuzetak — tamo je cva/clsx pattern.

---

## 2. Kompletna struktura foldera

```
frontend/
├── app/                                    # Next.js App Router
│   ├── layout.tsx                          # Root layout (html/body, <Providers>)
│   ├── providers.tsx                       # QueryClient, Toaster, NotificationStream wrapper
│   ├── globals.css                         # Tailwind + CSS varijable shadcn teme
│   ├── middleware.ts                       # (fajl je u `frontend/middleware.ts`, ne `app/`)
│   ├── not-found.tsx                       # 404
│   ├── error.tsx                           # global error boundary
│   │
│   ├── (auth)/                             # PUBLIC rute, bez AppShell-a
│   │   ├── layout.tsx                      # centriran container, logo gore
│   │   ├── login/page.tsx                  # ✅ već postoji
│   │   ├── register/page.tsx               # ✅ već postoji
│   │   ├── forgot-password/page.tsx        # ⚠️ STUB — dopuniti (Korak 3.4)
│   │   └── reset-password/page.tsx         # ❌ nedostaje (email link vodi ovde sa ?token=...)
│   │
│   ├── (student)/                          # rola STUDENT
│   │   ├── layout.tsx                      # <AppShell role="STUDENT">
│   │   ├── dashboard/page.tsx              # kartice: sledeći termini, notifikacije, strike status
│   │   ├── search/page.tsx                 # pretraga profesora + filter
│   │   ├── professor/[id]/page.tsx         # profil + FAQ + BookingCalendar
│   │   ├── my-appointments/page.tsx        # tabs Upcoming/History
│   │   └── document-requests/page.tsx      # forma + lista mojih zahteva
│   │
│   ├── (appointment)/                      # SHARED — STUDENT/PROFESOR/ASISTENT (vidi § 3.1)
│   │   ├── layout.tsx                      # client component, čita rolu iz Zustand-a
│   │   │                                   # i prosleđuje je <AppShell role="..."> dinamički
│   │   └── appointments/[id]/page.tsx      # detalj + chat + fajlovi + (uslovni) Otkaži flow
│   │                                       # student → AppointmentCancelDialog (strike < 12h)
│   │                                       # profesor/asistent → reuse RequestRejectDialog (razlog)
│   │
│   ├── (professor)/                        # role PROFESOR + ASISTENT
│   │   ├── layout.tsx                      # <AppShell role="PROFESOR">
│   │   └── professor/
│   │       ├── dashboard/page.tsx          # Tabs: Inbox zahteva | Moj kalendar
│   │       └── settings/page.tsx           # Tabs: Profil | FAQ | Canned | Blackout
│   │
│   └── (admin)/                            # rola ADMIN
│       ├── layout.tsx                      # <AppShell role="ADMIN">
│       └── admin/
│           ├── page.tsx                    # overview dashboard (metrics)
│           ├── users/page.tsx              # CRUD + Bulk Import dugme
│           ├── document-requests/page.tsx  # Tabs PENDING/APPROVED/REJECTED/COMPLETED
│           ├── strikes/page.tsx            # tabela studenata sa poenima
│           ├── broadcast/page.tsx          # forma + history
│           └── audit-log/page.tsx          # tabela sa filterima
│
├── components/
│   ├── ui/                                 # Shadcn/ui — jedino mesto gde se generisu primitive
│   │   ├── button.tsx                      # ✅
│   │   ├── card.tsx                        # ✅
│   │   ├── form.tsx                        # ✅
│   │   ├── input.tsx                       # ✅
│   │   ├── label.tsx                       # ✅
│   │   ├── dialog.tsx                      # ❌ `npx shadcn add dialog`
│   │   ├── sheet.tsx                       # ❌ (mobilni sidebar)
│   │   ├── dropdown-menu.tsx               # ❌
│   │   ├── avatar.tsx                      # ❌
│   │   ├── separator.tsx                   # ❌
│   │   ├── select.tsx                      # ❌
│   │   ├── tabs.tsx                        # ❌
│   │   ├── badge.tsx                       # ❌
│   │   ├── toast.tsx + toaster.tsx + use-toast.ts   # ❌
│   │   ├── accordion.tsx                   # ❌ (FAQ)
│   │   ├── textarea.tsx                    # ❌
│   │   ├── checkbox.tsx                    # ❌
│   │   ├── switch.tsx                      # ❌ (auto_approve u settings)
│   │   ├── scroll-area.tsx                 # ❌ (chat, notifikacije)
│   │   ├── skeleton.tsx                    # ❌ (loading states)
│   │   ├── alert.tsx                       # ❌ (formne greške)
│   │   ├── alert-dialog.tsx                # ❌ (potvrda brisanja, otkazivanja)
│   │   ├── table.tsx                       # ❌ (admin tabele)
│   │   ├── popover.tsx                     # ❌ (date picker, tag picker)
│   │   ├── calendar.tsx                    # ❌ (shadcn kalendar za blackout date picker)
│   │   ├── tooltip.tsx                     # ❌
│   │   ├── command.tsx                     # ❌ (combobox, npr. asistent select)
│   │   ├── progress.tsx                    # ❌ (upload)
│   │   └── radio-group.tsx                 # ❌
│   │
│   ├── shared/                             # globalne komponente deljene između rola
│   │   ├── app-shell.tsx                   # sidebar + top-bar + content; prima `role` prop
│   │   ├── sidebar.tsx                     # navigacija po roli (lucide ikone)
│   │   ├── sidebar-nav-item.tsx            # pojedinačna stavka sa active state
│   │   ├── top-bar.tsx                     # logo, search, <NotificationCenter />, <UserMenu />
│   │   ├── user-menu.tsx                   # avatar + dropdown (profil, logout)
│   │   ├── impersonation-banner.tsx        # crveni top-bar u ADMIN MODE
│   │   ├── strike-display.tsx              # prikaz broja poena + datum isteka blokade
│   │   ├── waitlist-button.tsx             # toggle join/leave za waitlist
│   │   ├── empty-state.tsx                 # "Nema podataka" stanje sa ikonom i porukom
│   │   ├── page-header.tsx                 # h1 + opis + akcija (dugme desno)
│   │   ├── protected-page.tsx              # wrapper koji proverava rolu + redirektuje
│   │   ├── faculty-badge.tsx               # FON/ETF badge
│   │   ├── role-gate.tsx                   # conditional render po roli
│   │   └── global-search-box.tsx           # top-bar search (Google PSE u Fazi 5)
│   │
│   ├── auth/                               # komponente samo za (auth) rute
│   │   ├── login-form.tsx                  # ekstraktovano iz page.tsx radi čistoće
│   │   ├── register-form.tsx               # uključuje email domain validaciju
│   │   ├── forgot-password-form.tsx
│   │   └── reset-password-form.tsx
│   │
│   ├── calendar/                           # FullCalendar wrapperi
│   │   ├── booking-calendar.tsx            # STUDENT: read-only slotovi, onSelectSlot callback
│   │   ├── availability-calendar.tsx       # PROFESOR: drag-drop kreiranje/izmena slotova
│   │   ├── recurring-rule-modal.tsx        # modal za weekly/monthly + date range kad prof drag-a
│   │   ├── slot-popover.tsx                # hover/klik tooltip za pojedinačni slot
│   │   └── calendar-legend.tsx             # boje: slobodno/pun/blokirano/moj termin
│   │
│   ├── appointments/
│   │   ├── appointment-card.tsx            # kartica termina (list view) sa status badge
│   │   ├── appointment-status-badge.tsx    # PENDING/APPROVED/REJECTED/CANCELLED/COMPLETED
│   │   ├── appointment-request-form.tsx    # topic, description, subject_id, file upload
│   │   ├── appointment-cancel-dialog.tsx   # potvrda + upozorenje o <24h striku
│   │   ├── appointment-detail-header.tsx   # status, datetime, type, profesor
│   │   ├── participant-list.tsx            # grupne konsultacije: lista sa confirm/decline
│   │   ├── participant-row.tsx             # jedan participant sa akcijama
│   │   ├── file-upload-zone.tsx            # react-dropzone wrapper (5MB, MIME validacija)
│   │   └── file-list.tsx                   # lista fajlova sa presigned download linkom
│   │
│   ├── chat/
│   │   ├── ticket-chat.tsx                 # socket.io-client; max 20 poruka, 24h auto-close
│   │   ├── chat-message.tsx                # jedan mehur poruke (sender/receiver varijante)
│   │   ├── chat-input.tsx                  # textarea + submit + counter
│   │   ├── chat-closed-notice.tsx          # banner kad je chat zatvoren (posle 24h)
│   │   └── chat-message-counter.tsx        # indikator "X od 20 poruka"
│   │
│   ├── professor/                          # komponente samo za (professor) rute
│   │   ├── requests-inbox.tsx              # tabela PENDING zahteva sa akcijama
│   │   ├── request-inbox-row.tsx           # jedan red; dropdown Approve/Reject/Delegate
│   │   ├── request-approve-dialog.tsx      # potvrda
│   │   ├── request-reject-dialog.tsx       # textarea za razlog + canned responses dropdown
│   │   ├── request-delegate-dialog.tsx     # select asistenta (iz predmeta)
│   │   ├── profile-form.tsx                # settings → Profil tab
│   │   ├── areas-of-interest-input.tsx     # tag input za areas_of_interest (TEXT[])
│   │   ├── faq-list.tsx                    # lista FAQ stavki sa drag-reorder
│   │   ├── faq-item-row.tsx                # jedan FAQ red + edit/delete
│   │   ├── faq-form-dialog.tsx             # create/edit FAQ modal
│   │   ├── canned-response-list.tsx
│   │   ├── canned-response-form-dialog.tsx
│   │   ├── blackout-manager.tsx            # kalendarski picker + lista aktivnih perioda
│   │   ├── crm-notes-panel.tsx             # prikazuje se na appointment detail (sidebar)
│   │   └── crm-note-form.tsx
│   │
│   ├── student/
│   │   ├── professor-search-card.tsx       # rezultat pretrage
│   │   ├── professor-profile-header.tsx    # header profila profesora
│   │   ├── professor-faq-accordion.tsx     # FAQ akordeon (iznad kalendara!)
│   │   └── professor-subjects-list.tsx
│   │
│   ├── document-requests/
│   │   ├── document-request-form.tsx       # STUDENT: document_type Select + note Textarea
│   │   ├── document-request-card.tsx       # STUDENT: kartica sa status badge
│   │   ├── document-request-status-badge.tsx
│   │   ├── document-request-admin-row.tsx  # ADMIN: red u tabeli sa Approve/Reject/Complete
│   │   ├── document-request-approve-dialog.tsx   # pickup_date + admin_note
│   │   └── document-request-reject-dialog.tsx    # obavezan admin_note
│   │
│   ├── admin/
│   │   ├── users-table.tsx
│   │   ├── user-form-modal.tsx             # create/edit user
│   │   ├── bulk-import-modal.tsx           # CSV dropzone → preview → Confirm
│   │   ├── bulk-import-preview-table.tsx   # ispod dropzone-a sa greškama/duplikatima
│   │   ├── audit-log-table.tsx             # filter panel + tabela
│   │   ├── audit-log-filters.tsx
│   │   ├── strike-row.tsx                  # jedan student sa poenima + Unblock dugme
│   │   ├── unblock-dialog.tsx              # obavezno obrazloženje
│   │   ├── broadcast-form.tsx              # title, body, target, channels
│   │   ├── broadcast-history.tsx           # istorija poslatih broadcastova
│   │   └── admin-dashboard-metrics.tsx     # kartice sa statistikama (za admin/page.tsx)
│   │
│   └── notifications/
│       ├── notification-center.tsx         # bell ikonica + dropdown poslednjih 10
│       ├── notification-item.tsx           # jedna notifikacija (read/unread state)
│       ├── notification-list.tsx           # full lista ("vidi sve" stranica ako bude)
│       └── notification-stream.tsx         # nevidljiv WS klijent; pokreće se u providers.tsx
│
├── lib/
│   ├── api.ts                              # ✅ axios instance + JWT refresh interceptor
│   │
│   ├── api/                                # API moduli — tanki wrapperi nad `api`
│   │   ├── auth.ts                         # ✅ login, register, refresh, logout, forgot, reset, me
│   │   ├── students.ts                     # search, profile, slots, book, cancel, myAppointments, waitlist
│   │   ├── professors.ts                   # profile, slots, blackout, requests, canned, crm, faq
│   │   ├── appointments.ts                 # detail, messages, files, participants
│   │   ├── document-requests.ts            # student create/list + admin se oslanja na adminApi
│   │   ├── admin.ts                        # users, bulkImport, impersonate, strikes, broadcast, audit, docReqs
│   │   ├── notifications.ts                # list, markRead, markAllRead
│   │   └── search.ts                       # Google PSE proxy (Faza 5)
│   │
│   ├── hooks/                              # TanStack Query hooks — jedini sloj koji ih koristi
│   │   ├── use-auth.ts                     # useMe, useLogin (mutation), useRegister (mutation)
│   │   ├── use-professors.ts               # useProfessorSearch, useProfessor, useProfessorSlots
│   │   ├── use-appointments.ts             # useMyAppointments, useAppointment, useCreate, useCancel
│   │   ├── use-availability.ts             # useMySlots, useCreateSlot, useDeleteSlot, useBlackouts
│   │   ├── use-requests-inbox.ts           # useRequestsInbox, useApprove, useReject, useDelegate
│   │   ├── use-canned-responses.ts
│   │   ├── use-faq.ts
│   │   ├── use-crm.ts
│   │   ├── use-chat.ts                     # socket.io connect + useMutation(sendMessage)
│   │   ├── use-files.ts                    # upload, list, delete
│   │   ├── use-participants.ts             # confirm/decline (grupne)
│   │   ├── use-waitlist.ts                 # join/leave, pozicija
│   │   ├── use-document-requests.ts        # useMyDocReqs, useCreate, useAdminDocReqs, useApprove, useReject, useComplete
│   │   ├── use-notifications.ts            # useNotifications, useMarkRead, useUnreadCount
│   │   ├── use-admin-users.ts              # CRUD + bulk import
│   │   ├── use-impersonation.ts            # start/end (poziva adminApi + osvežava auth store)
│   │   ├── use-strikes.ts                  # list + unblock
│   │   ├── use-broadcast.ts                # send + history
│   │   ├── use-audit-log.ts
│   │   └── use-pse-search.ts               # Google PSE (Faza 5)
│   │
│   ├── stores/                             # Zustand — samo client state koji NIJE server state
│   │   ├── auth.ts                         # ✅ user, accessToken, setAuth, clearAuth
│   │   ├── impersonation.ts                # isImpersonating, adminId, originalUser — za banner
│   │   └── ui.ts                           # sidebarOpen (mobile), teme itd. (opciono)
│   │
│   ├── validation/                         # Zod šeme za forme (opciono izdvojeno — može i u komponenti)
│   │   ├── auth.schema.ts                  # login, register, reset-password
│   │   ├── appointment.schema.ts           # request form validacija (desc 20-500 char itd.)
│   │   ├── professor.schema.ts             # profile, faq, canned-response
│   │   ├── document-request.schema.ts
│   │   └── admin.schema.ts                 # user create, broadcast
│   │
│   ├── constants/
│   │   ├── roles.ts                        # Role enum + labele
│   │   ├── topic-categories.ts             # 5 vrednosti iz PRD-a + serbian labele
│   │   ├── document-types.ts               # 6 tipova dokumenata sa labelama
│   │   ├── nav-items.ts                    # mape rute → ikona/label po roli
│   │   ├── accepted-mime-types.ts          # dozvoljeni upload formati (PDF, DOCX, XLSX, PNG...)
│   │   └── routes.ts                       # centralizovana lista URL-ova kao konstante
│   │
│   ├── utils/
│   │   ├── cn.ts                           # clsx + tailwind-merge (shadcn standard)
│   │   ├── date.ts                         # format helper (date-fns wrapper, sr-Latn)
│   │   ├── file-size.ts                    # bytes → human readable
│   │   ├── email-domain.ts                 # validacija fakultetskog domena (mirror bekenda)
│   │   ├── jwt.ts                          # decode (bez verifikacije — samo za UX)
│   │   ├── errors.ts                       # mapiranje API error response-a u toast poruku
│   │   └── file-validation.ts              # MIME + size check pre uploada
│   │
│   └── ws/
│       ├── chat-socket.ts                  # socket.io klijent instance za chat (per-appointment)
│       └── notification-socket.ts          # WebSocket klijent za /notifications/stream
│
├── types/                                  # TypeScript tipovi — mora da se poklapa sa Pydantic šemama
│   ├── auth.ts                             # ✅ UserResponse, LoginRequest, LoginResponse, itd.
│   ├── common.ts                           # Paginated<T>, Faculty, Role, ConsultationType, TopicCategory, AppointmentStatus
│   ├── professor.ts                        # ProfessorSearchResponse, ProfessorProfileResponse, FaqResponse, SlotResponse, BlackoutResponse, CannedResponse, CrmNote
│   ├── appointment.ts                      # AppointmentResponse, AppointmentCreateRequest, AppointmentDetailResponse, AvailableSlotResponse, ParticipantResponse, ChatMessageResponse, FileResponse
│   ├── document-request.ts                 # DocumentRequestResponse, DocumentRequestCreate, ApproveRequest, RejectRequest, DocumentType
│   ├── admin.ts                            # AdminUserResponse, BulkImportPreview, StrikeRow, AuditLogRow, BroadcastRequest
│   ├── notification.ts                     # NotificationResponse, NotificationType
│   └── ws.ts                               # ChatSocketMessage, NotificationSocketMessage (ugovori za WS)
│
├── public/
│   ├── manifest.json                       # PWA (Faza 5)
│   ├── icons/                              # 192, 512, maskable (Faza 5)
│   ├── sw.js                               # service worker (generisan od next-pwa)
│   └── logos/                              # FON, ETF logo, app logo
│
├── middleware.ts                           # Next.js middleware — redirect za nelogovane + rbac guard
├── next.config.mjs                         # next-pwa config (Faza 5) + env eksponovanje
├── postcss.config.mjs                      # Tailwind v4 plugin: { "@tailwindcss/postcss": {} }
├── tsconfig.json                           # path aliasi `@/*` → `./`
├── components.json                         # shadcn/ui config (config: "" — v4 nema tailwind.config.ts)
├── package.json                            # tailwindcss ^4 + @tailwindcss/postcss ^4
└── .env.example                            # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL, itd.
```

> **Tailwind v4 (od 2026-04-26):** `tailwind.config.ts` više **ne postoji** — sva
> tema je deklarisana u `app/globals.css` kroz `@theme inline { --color-*: var(--*) }`
> i `@custom-variant dark (&:where(.dark, .dark *))`. Migracija je urađena
> jer su `shadcn/ui` komponente generisale v4 sintaksu (`w-(--var)`,
> `data-state:` selektori, `outline-hidden` itd.) koju v3 PostCSS plugin nije
> kompajlirao — rezultat je bio nevidljiv dropdown content. Detalji u § 8.

---

## 3. Ključne arhitekturalne odluke

### 3.1 Route groupe i layouti

Next.js 14 App Router route groupe `(auth)`, `(student)`, `(appointment)`, `(professor)`, `(admin)` **ne utiču na URL**, samo na to koji layout se primenjuje. Svaka grupa ima svoj `layout.tsx`:

- `(auth)/layout.tsx` — centrirana kartica, bez sidebar-a. Eksportuje `ReactNode` direktno.
- `(student|professor|admin)/layout.tsx` — server component, `ProtectedPage allowedRoles={[…]}` + `<AppShell role="…">` (rola fiksna, mapirana na grupu).
- **`(appointment)/layout.tsx`** — `"use client"`, čita `useAuthStore((s) => s.user?.role)` i prosleđuje rolu `<AppShell>`-u dinamički. `ProtectedPage` dozvoljava STUDENT, PROFESOR i ASISTENT.

**Appointment detail** (`/appointments/[id]`) je shared stranica koja prikazuje status, fajlove, chat, učesnike (grupne konsultacije). Tri različita auditorijuma — student koji je rezervisao slot, profesor čiji je slot, asistent kome je delegiran zahtev — koriste **istu** komponentu jer im je view 95% isti; razlikuje se samo Otkaži flow (vidi § 8.3 i § 8.6):

- **Student** → `AppointmentCancelDialog` (potvrda bez razloga, bekend dodaje strike ako je < 12h do termina).
- **Profesor / asistent** → `RequestRejectDialog` reuse-ovan sa custom title/description (obavezan razlog koji se snima u `rejection_reason` i šalje studentu kroz `send_appointment_rejected` Celery task).

URL-ovi se ne preklapaju (route grupe su tu samo za layout) — `(appointment)/appointments/[id]` rezerviše URL `/appointments/[id]`, pa **ne sme** istovremeno postojati `(student)/appointments/[id]/page.tsx` (kompajler bi izbacio "duplicate route" grešku).

### 3.2 Middleware + zaštita ruta

`frontend/middleware.ts` (Next.js konvencija — mora biti root, ne u `app/`):

```typescript
export function middleware(request: NextRequest) {
  const refreshToken = request.cookies.get('refresh_token');
  const { pathname } = request.nextUrl;

  const isAuthRoute = pathname.startsWith('/login') || pathname.startsWith('/register')
                   || pathname.startsWith('/forgot-password') || pathname.startsWith('/reset-password');

  if (!refreshToken && !isAuthRoute) return NextResponse.redirect(new URL('/login', request.url));
  if (refreshToken && isAuthRoute) return NextResponse.redirect(new URL('/dashboard', request.url));
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next|api|favicon.ico|manifest.json|icons).*)'],
};
```

**Važno:** middleware ne zna rolu (nema dostup do payload-a bez verifikacije), zato RBAC redirektovanje radi klijentski `<ProtectedPage requiredRole="ADMIN">` komponenta ili provera u `AppShell`-u. Backend svakako vraća 403.

### 3.3 AppShell — jedinstveni frame

`components/shared/app-shell.tsx` je jedina komponenta koja određuje izgled unutar logovanog stanja:

```tsx
<AppShell role={user.role}>
  <ImpersonationBanner />                    {/* crveni banner ako se impersonira */}
  <div className="flex h-screen">
    <Sidebar role={role} />
    <div className="flex flex-col flex-1">
      <TopBar>
        <GlobalSearchBox />
        <NotificationCenter />
        <UserMenu />
      </TopBar>
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  </div>
</AppShell>
```

Sidebar mapa po rolama je u `lib/constants/nav-items.ts`:

```typescript
export const NAV_ITEMS: Record<Role, NavItem[]> = {
  STUDENT: [
    { href: '/dashboard', label: 'Početna', icon: Home },
    { href: '/search', label: 'Pretraga profesora', icon: Search },
    { href: '/my-appointments', label: 'Moji termini', icon: Calendar },
    { href: '/document-requests', label: 'Zahtevi za dokumente', icon: FileText },
  ],
  PROFESOR: [
    { href: '/professor/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/professor/settings', label: 'Podešavanja', icon: Settings },
  ],
  ASISTENT: [ /* isto kao PROFESOR */ ],
  ADMIN: [
    { href: '/admin', label: 'Pregled', icon: LayoutDashboard },
    { href: '/admin/users', label: 'Korisnici', icon: Users },
    { href: '/admin/document-requests', label: 'Zahtevi', icon: FileText },
    { href: '/admin/strikes', label: 'Strike-ovi', icon: AlertTriangle },
    { href: '/admin/broadcast', label: 'Broadcast', icon: Megaphone },
    { href: '/admin/audit-log', label: 'Audit log', icon: History },
  ],
};
```

### 3.4 Data flow — jedno pravilo po tipu podatka

| Tip podatka | Gde živi | Kako se čita u stranici |
|-------------|----------|--------------------------|
| Server state (API podaci) | TanStack Query cache | `useProfessorSearch(q)` |
| Access token | Zustand `useAuthStore` | `const { user } = useAuthStore()` |
| Form state | react-hook-form | `useForm({ resolver: zodResolver(schema) })` |
| WebSocket poruke | TanStack Query invalidation + local state | vidi § 3.5 |
| Modal open/close | Lokalno `useState` | per-komponenta |

**Ne mešati.** Ako korisnički podatak dolazi sa bekenda — ide kroz TanStack Query (`useMe`), ne u Zustand. Zustand čuva samo access token (jer ga axios interceptor mora čitati sinhronski).

### 3.5 Real-time — WebSocket integracija sa TanStack Query

Dva WS kanala:
1. **Chat** (per-appointment, `socket.io`): `ws/chat-socket.ts` instancira klijent; `use-chat.ts` hook spaja connect/disconnect na lifecycle komponente `<TicketChat>`.
2. **Notifikacije** (per-user stream, native WebSocket): `NotificationStream` komponenta se montira u `providers.tsx`, otvara WS kad `user` postoji, zatvara na logout. Na svaku poruku → `queryClient.invalidateQueries({ queryKey: ['notifications'] })` + toast.

```tsx
// app/providers.tsx (skica)
export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <NotificationStream />       {/* nevidljiva — samo WS konekcija */}
      <Toaster />
    </QueryClientProvider>
  );
}
```

### 3.6 Impersonation — kritičan security flow

1. Admin klikne "Impersonate" na users tabeli → `adminApi.impersonateStart(userId)` → backend vraća novi access token sa `imp: admin_id` claim-om.
2. `useImpersonationStore.setImpersonating({ adminId, originalUser })` — frontend zapamti ko je originalni admin.
3. `useAuthStore.setAuth({ user: impersonatedUser, accessToken })` — korisnik se menja.
4. `<ImpersonationBanner>` postaje vidljiv **preko čitavog ekrana** (crveni banner gore) sa "Izađi iz ADMIN MODE" dugmetom.
5. Klik na "Izađi" → `adminApi.impersonateEnd()` → vrati originalni admin token → `clearImpersonation()`.

**Zašto nije samo state, nego dva store-a?** Zato što access token MORA biti sinhrono čitljiv iz axios interceptora. Ako se meša sa impersonation metapodacima, svaki interceptor bi morao da ih raspetljava.

### 3.7 Forme + validacija

Konvencija po formama (uzor `login-form.tsx`):

```tsx
const schema = z.object({
  description: z.string().min(20, 'Min 20 karaktera').max(500, 'Max 500'),
  topic_category: z.enum(['SEMINARSKI', 'PREDAVANJA', 'ISPIT', 'PROJEKAT', 'OSTALO']),
  subject_id: z.string().uuid().optional(),
});

export function AppointmentRequestForm({ slotId, onSuccess }: Props) {
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const mutation = useCreateAppointment();
  // ...
}
```

Zod šeme mogu biti inline u komponenti (manje forme) ili u `lib/validation/` (ako se koriste na više mesta, npr. login/register dele deo validacije).

### 3.8 File upload

`AcceptedMimeTypes` konstanta mora se poklapati sa bekendom:

```typescript
// lib/constants/accepted-mime-types.ts
export const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'application/zip': ['.zip'],
  'text/x-python': ['.py'],
  'text/x-java-source': ['.java'],
  'text/x-c++src': ['.cpp'],
};
export const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
```

`FileUploadZone` koristi `react-dropzone` sa ovom konfiguracijom + prikazuje progress bar. Upload ide na backend, backend generiše presigned URL-ove za download.

### 3.9 TypeScript tipovi — ugovor sa bekendom

**Zlatno pravilo:** svaki `types/*.ts` mora imati 1:1 mapping sa odgovarajućom Pydantic šemom. Zajednički enum-ovi u `types/common.ts`:

```typescript
export type Role = 'STUDENT' | 'ASISTENT' | 'PROFESOR' | 'ADMIN';
export type Faculty = 'FON' | 'ETF';
export type ConsultationType = 'UZIVO' | 'ONLINE';
export type AppointmentStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED' | 'COMPLETED';
export type TopicCategory = 'SEMINARSKI' | 'PREDAVANJA' | 'ISPIT' | 'PROJEKAT' | 'OSTALO';
export type DocumentType = 'POTVRDA_STATUS' | 'UVERENJE_ISPITI' | 'UVERENJE_PROSEK'
                         | 'TRANSCRIPT' | 'POTVRDA_SKOLARINA' | 'OSTALO';
export type DocumentRequestStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'COMPLETED';

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
```

Ovi nizovi string-literala MORAJU biti sinhronizovani sa Pydantic enum-ovima (ROADMAP.md u sekciji "Pre Faze 3" eksplicitno traži dogovor kontrakta). Preporuka: generisati tipove iz OpenAPI šeme FastAPI-ja (`openapi-typescript` CLI). Alternativno, održavati ručno ali sa code review-om svakog backend enum-a.

---

## 4. Redosled implementacije (prati ROADMAP)

| # | Šta se pravi | ROADMAP korak | Procena |
|---|--------------|---------------|---------|
| 1 | `components/ui/*` shadcn generisanje | pre 2.2 | 0.25d |
| 2 | `components/shared/app-shell` + layouti | 2.2 | 1.5d |
| 3 | `lib/api/*` + `lib/hooks/*` + `types/*` | 2.3 | 1d |
| 4 | `(auth)` dopuna: forgot-password, reset-password | 3.4 | 0.5d |
| 5 | Student dashboard + my-appointments + `StrikeDisplay` | 3.4 | 1d |
| 6 | Search + professor profile + BookingCalendar + RequestForm | 3.5 | 3-4d |
| 7 | Appointment detail + TicketChat + Files + Participants | 3.6 | 2d |
| 8 | Professor dashboard + settings + AvailabilityCalendar | 3.7 | 3d |
| 9 | Admin panel — svih 6 stranica | 4.7 | 3.5d |
| 10 | Document requests (student) + NotificationCenter | 4.8 | 1.5d |
| 11 | Google PSE UI + PWA + produkcijska infra | 5.1–5.3 | 3.25d |

**Ukupno:** ~17-19 dana solo frontend rada (prati Filipov deo iz ROADMAP-a).

---

## 5. Checklist pre početka Faze 3

Pre nego što se krene sa stranicama, ove infrastrukturne stvari moraju biti gotove (FAZA 2):

- [ ] `npx shadcn add` za sve komponente iz § 2 (`ui/` folder).
- [ ] `AppShell` + Sidebar + TopBar + UserMenu + ImpersonationBanner renderuju se za sve 3 role.
- [ ] `lib/api/*` moduli napisani (prazne metode sa signature-om — body može biti jednostavan `api.get`).
- [ ] `types/*` fajlovi kompletni i usklađeni sa backend Pydantic šemama (peer review sa Stefanom).
- [ ] TanStack Query hooks u `lib/hooks/*` — barem skeleton po jedan fajl.
- [ ] Middleware + auth redirekcije testirane.
- [ ] Logout iz `UserMenu` radi (čisti Zustand + poziva `/auth/logout`).

Tek kada je ovih 7 tačaka ✅, smisleno je krenuti sa konkretnim stranicama — inače svaka stranica pravi svoj ad-hoc pattern i posle se ne može ukloniti duplikacija.

---

## 6. Dodatne preporuke

### 6.1 ESLint + Prettier

Dodati `eslint-plugin-tailwindcss` da sortira klase i hvata neispravne utility-je. `prettier-plugin-tailwindcss` automatski sortira klase pri save-u.

### 6.2 Storybook (opciono, ali korisno)

Za `components/ui/*` i `components/shared/*` — jednom napravljeno, sve buduće izmene vidiš vizuelno bez rute u app-u. Nije must-have za MVP.

### 6.3 Testovi

- **Komponente:** Vitest + React Testing Library za `appointment-request-form`, `booking-calendar` edge case-ovi.
- **E2E:** Playwright scenariji iz ROADMAP 5.4 (student booking, professor approve, admin bulk import).

### 6.4 Error handling

Centralizovati u `lib/utils/errors.ts`:

```typescript
export function toastApiError(err: unknown) {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    toast({ variant: 'destructive', title: 'Greška', description: detail ?? err.message });
  } else {
    toast({ variant: 'destructive', title: 'Nepoznata greška' });
  }
}
```

Svaki `mutation.onError` poziva `toastApiError`, umesto da svaka stranica hendluje istu stvar.

### 6.5 Internacionalizacija (naknadno)

Trenutno je UI na srpskom. Ako ikad bude engleski (V2), preporučuje se `next-intl`. Za sada se može držati labele u `constants/` i tamo kasnije dodati i18n sloj.

---

## 7. Otvorena pitanja koja vredi razjasniti sa Stefanom

1. ~~**Appointment detail shared route** — ostaje samo u `(student)` grupi ili se pravi duplikat u `(professor)`?~~ **REŠENO 2026-04-26**: napravljen treći route group `(appointment)/` sa client layout-om koji bira `<AppShell role="...">` dinamički iz auth store-a. Vidi § 3.1 i § 8.3.
2. **ChatSocketMessage vs NotificationSocketMessage** — JSON šeme za WS moraju biti u `docs/websocket-schema.md` pre Faze 4 (ROADMAP to traži).
3. **Strike status u `/auth/me`** — ROADMAP 3.4 kaže "dodati `total_strike_points` u `UserResponse` šemu". Potvrditi sa Stefanom da se ne pravi zaseban endpoint.
4. **Impersonation token format** — frontend mora znati kako da prepozna `imp` claim. `lib/utils/jwt.ts` samo dekodira payload (bez verifikacije) radi `useImpersonationStore`-a.
5. **Role `ASISTENT` vs `PROFESOR` u UI-u** — da li asistent ima **identičan** sidebar kao profesor? PRD kaže asistent može da odobrava termine samo za dodeljene predmete — backend to već štiti, ali u UI-u vredi sakriti "kreiraj slot" dugme od asistenta.

---

## 8. Changelog — sesija 2026-04-26

Spisak svih frontend izmena urađenih u jednoj radnoj sesiji. Listano hronološki kako bi naredna sesija imala kontekst zašto je svaka izmena tu.

### 8.1 Tailwind CSS v3 → v4 migracija

**Bug:** Klik na 3 tačkice / UserMenu / bell ikonicu pravio je DOM element sa `data-state="open"`, bez konzolnih grešaka, ali sadržaj nije bio vidljiv. Computed CSS na `DropdownMenuContent` je imao `position: static` umesto `absolute`, a Radix popper wrapper je bio na `transform: translate(0px, -200%)` (offscreen).

**Uzrok:** `shadcn/ui` komponente su generisane sa Tailwind v4 sintaksom (`max-h-(--radix-dropdown-menu-content-available-height)`, `data-open:animate-in`, `outline-hidden`, `data-state:` selektori) koju v3 PostCSS plugin **nije kompajlirao** — utility klase su tiho izostavljane, pa Radix Floating UI nije mogao da pozicionira portal content.

**Fix u sledećim fajlovima:**

| Fajl | Promena |
|------|---------|
| `package.json` | `tailwindcss ^4.2.4`, `@tailwindcss/postcss ^4.2.4`; uklonjen `tailwindcss-animate` (zamenjen sa `tw-animate-css` koji je v4-compatible) |
| `postcss.config.mjs` | Plugins → `{ "@tailwindcss/postcss": {} }`. Uklonjen `autoprefixer` jer Lightning CSS u Tailwind v4 to već radi. |
| `tailwind.config.ts` | **Obrisan.** v4 ima zero-config auto-detection content-a + tema u CSS-u. |
| `app/globals.css` | Prepisan: `@import "tailwindcss"`, `@custom-variant dark`, `@theme inline { --color-*: var(--*) }`, `:root` i `.dark` blokovi sa OKLCH varijablama (mirror-uju shadcn neutral preset). |
| `components.json` | `"tailwind.config": ""` umesto putanje (config fajl ne postoji). |

**Verifikacija:** Playwright skripta je inspect-ovala DOM nakon klika — `position` je `absolute`, popper wrapper ima izračunate koordinate, dropdown je vidljiv.

### 8.2 `Button` forwardRef fix

**Bug:** Čak i posle Tailwind v4 migracije, prvi klik na `<DropdownMenuTrigger asChild><Button>` nije pozicionirao content. React je u konzoli prijavljivao `Function components cannot be given refs.`.

**Uzrok:** `frontend/components/ui/button.tsx` je bio plain function komponenta. Radix `asChild` koristi `Slot.Root` koji prosleđuje `ref` na decu — bez `React.forwardRef`-a, ref se gubio i Floating UI nije mogao da izmeri trigger.

**Fix:** `Button` umotan u `React.forwardRef<HTMLButtonElement, ButtonProps>`, ref se prosleđuje na `Slot.Root` (kad je `asChild`) ili `<button>` (default). Dodat duži komentar uz sam wrapper koji objašnjava zašto.

```tsx
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, ...props }, ref
) {
  const Comp = asChild ? Slot.Root : "button"
  return <Comp ref={ref} {...props} className={cn(buttonVariants({ variant, size, className }))} />
})
```

**Side-effect:** isti fix je rešio i pozicioniranje za `PopoverTrigger`, `TooltipTrigger`, `SheetTrigger`, `DialogTrigger`, `HoverCardTrigger` — sve Radix primitive-e koje se koriste kroz `asChild` + `<Button>`.

### 8.3 Novi `(appointment)` route group

**Bug:** `(student)/appointments/[id]/page.tsx` je bila u student-only route grupi (`ProtectedPage allowedRoles={["STUDENT"]}`). Profesor koji je odobrio termin nije mogao da uđe na stranicu — bio je redirektovan na `/professor/dashboard` pre nego što stigne do nje.

**Fix — file move + novi layout:**

| Akcija | Fajl |
|--------|------|
| Obrisano | `frontend/app/(student)/appointments/[id]/page.tsx` |
| Novo | `frontend/app/(appointment)/layout.tsx` (`"use client"`, čita rolu, AppShell prima rolu dinamički) |
| Novo | `frontend/app/(appointment)/appointments/[id]/page.tsx` |

URL `/appointments/[id]` ostaje isti — route grupe su samo layout grouping. Detalj-stranica sad razlikuje dva Otkaži flow-a:

- `useAuthStore((s) => s.user?.role)` → `STUDENT` → `AppointmentCancelDialog` + `useCancelAppointment()` (hook iz `students.ts`).
- `PROFESOR` ili `ASISTENT` → `RequestRejectDialog` reuse-ovan + `useCancelRequest()` (hook iz `use-requests-inbox.ts`, vidi § 8.6).
- Cancel se pojavljuje samo na ne-terminalnim statusima za studenta i samo na APPROVED za profesora (PENDING zahteve profesor obrađuje kroz inbox dropdown — Odobri/Odbij/Delegiraj, ne Otkaži).

### 8.4 `AppointmentCard` — chevron i actions zajedno

**Bug:** U `my-appointments` listi, kartice koje imaju Otkaži dugme (`PENDING`/`APPROVED`) nisu bile klikabilne — `interactive={!canCancel}` je isključivao `<Link>` wrapping, pa student nije mogao da otvori chat/fajlove dok god ima cancel opciju.

**Fix u `components/appointments/appointment-card.tsx`:**

```tsx
{actions || interactive ? (
  <div className="flex shrink-0 items-center gap-2">
    {actions}
    {interactive && <ChevronRight className="hidden size-5 sm:block" aria-hidden />}
  </div>
) : null}
```

Chevron se renderuje pored akcija (umesto da budu mutually exclusive). U `(student)/my-appointments/page.tsx` je `interactive={!canCancel}` zamenjeno sa `interactive` (uvek true). `CancelButton` već zaustavlja propagaciju (`e.preventDefault(); e.stopPropagation()`) pa klik na njega ne otvara detail.

### 8.5 `RequestInboxRow` — status-aware dropdown

**Bug:** Profesor je u inbox dropdown-u uvek video "Odobri / Odbij / Delegiraj asistentu" — bez obzira na status reda. Klik na "Odbij" za APPROVED termin vraćao je 409 toast "Samo PENDING zahtevi mogu biti odbijeni." Nije postojala "Otkaži" putanja.

**Fix u `components/professor/request-inbox-row.tsx`:**

| Status | Stavke u dropdown-u |
|--------|---------------------|
| `PENDING` | Otvori termin · Odobri · Odbij · *(samo PROFESOR)* Delegiraj asistentu |
| `APPROVED` | Otvori termin · **Otkaži termin** (destructive) |
| `REJECTED` / `CANCELLED` / `COMPLETED` | Otvori termin (read-only) |

"Otvori termin" je `<DropdownMenuItem asChild><Link href={ROUTES.appointment(id)}>` — direktno vodi na shared `(appointment)` stranicu (vidi § 8.3). Komponenta sad prima i `onCancel` callback propa pored postojećih `onApprove/onReject/onDelegate`.

### 8.6 Cancel flow za profesora — frontend wiring

**Backend:** dodat endpoint `POST /api/v1/professors/requests/{id}/cancel` (`backend/app/services/professor_portal_service.py::cancel_request`, šema `RequestCancelRequest{ reason }`). Validira da je status `APPROVED`, postavlja na `CANCELLED`, snima razlog u `rejection_reason`, reuse-uje `send_appointment_rejected` Celery task.

**Frontend dodatci:**

| Fajl | Promena |
|------|---------|
| `lib/api/professors.ts` | `cancelRequest(appointmentId, { reason })` (POST na novi endpoint) |
| `lib/hooks/use-requests-inbox.ts` | `useCancelRequest()` — invalidira **i** `INBOX_KEY` **i** `["my-appointments"]` **i** `["appointment"]` (jer student takođe gleda isti termin) |
| `components/professor/request-reject-dialog.tsx` | Dodate opcione props: `title`, `description`, `confirmLabel`, `reasonLabel`. Default vrednosti zadržavaju postojeći "Odbij zahtev" UX, override-i omogućavaju reuse za "Otkaži odobreni termin". |
| `components/professor/requests-inbox.tsx` | Dodato `toCancel` state + `useCancelRequest()` mutation + drugi `<RequestRejectDialog>` instance sa `title="Otkaži odobreni termin"` / `confirmLabel="Otkaži termin"`. |
| `app/(appointment)/appointments/[id]/page.tsx` | Isti reuse — kad profesor klikne "Otkaži termin" gore desno, otvara se reject dialog sa cancel copy-jem. |

### 8.7 Sumarna lista promenjenih frontend fajlova

```
A  frontend/app/(appointment)/layout.tsx
A  frontend/app/(appointment)/appointments/[id]/page.tsx
D  frontend/app/(student)/appointments/[id]/page.tsx
M  frontend/app/(student)/my-appointments/page.tsx
M  frontend/components/appointments/appointment-card.tsx
M  frontend/components/professor/request-inbox-row.tsx
M  frontend/components/professor/request-reject-dialog.tsx
M  frontend/components/professor/requests-inbox.tsx
M  frontend/components/ui/button.tsx
M  frontend/lib/api/professors.ts
M  frontend/lib/hooks/use-requests-inbox.ts
M  frontend/app/globals.css
M  frontend/postcss.config.mjs
M  frontend/components.json
M  frontend/package.json
D  frontend/tailwind.config.ts
```

(A = added, M = modified, D = deleted)

---

*Dokument živi u `docs/FRONTEND_STRUKTURA.md`. Ažurirati kad god se doda nova route grupa, veća komponenta ili novi ključni lib modul. Changelog sekcija (§ 8) raste po sesijama — ne brisati istorijske zapise, dodavati nove ispod.*
