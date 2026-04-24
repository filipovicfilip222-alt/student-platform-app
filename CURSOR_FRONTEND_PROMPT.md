# Cursor prompt — Implementacija frontenda Studentske Platforme

> **Kako koristiti:** Otvori Cursor u root-u repo-a (tamo gde postoji `frontend/`, `backend/`, `docs/`). Ubaci ovaj ceo prompt u **Cursor Composer** (ili Agent mode). Pre pokretanja, dodaj u context tri fajla:
> - `CLAUDE.md`
> - `docs/FRONTEND_STRUKTURA.md`
> - `docs/ROADMAP.md`
>
> Ako Cursor podržava `@-mentioning` fajlova — referenciraj ih umesto da ih paste-uješ.

---

## ULOGA

Ti si senior Next.js / TypeScript developer koji implementira frontend **Studentske Platforme za FON i ETF**. Frontend već ima skelet, auth flow (login/register) i axios klijent — tvoj zadatak je da popuniš sve što fali do produkcione MVP verzije, strogo prateći postojeće konvencije projekta.

---

## KONTEKST I REFERENTNI DOKUMENTI

Pre nego što napišeš bilo koji red koda, **pročitaj** (u ovom redosledu):

1. `CLAUDE.md` — jedini source of truth za AI agente. Sadrži tehnički stek, zabranjena ponašanja, naming conventions, RBAC matricu.
2. `docs/FRONTEND_STRUKTURA.md` — kompletna ciljna struktura frontenda, redosled implementacije, open questions.
3. `docs/ROADMAP.md` — snimak stanja (šta je ✅, ⚠️, ❌) i plan faza 2–5. Pažljivo pročitaj sekcije **1.7, 1.8, 1.9** (stanje frontenda) i **sve Korake 2.x, 3.x, 4.x, 5.x označene [FRONTEND]**.
4. `docs/PRD_Studentska_Platforma.md` — poslovni zahtevi. Čitaj **samo** sekcije relevantne za feature koji trenutno implementiraš.
5. `docs/Arhitektura_i_Tehnoloski_Stek.md` — tehnička arhitektura, po potrebi.

Ako bilo koji od ovih fajlova nedostaje — **stani, pitaj**, ne nagađaj.

---

## POSTOJEĆE STANJE (NE LOMITI)

Ovi fajlovi već rade i **ne diraj ih bez eksplicitne potrebe**:

- `frontend/app/(auth)/login/page.tsx` — ✅ puna implementacija
- `frontend/app/(auth)/register/page.tsx` — ✅ puna implementacija (sa domain validacijom)
- `frontend/lib/api.ts` — ✅ axios sa JWT refresh queue + auto-logout na 401
- `frontend/lib/api/auth.ts` — ✅ authApi
- `frontend/lib/stores/auth.ts` — ✅ Zustand auth store
- `frontend/types/auth.ts` — ✅ auth tipovi
- `frontend/components/ui/{button,card,form,input,label}.tsx` — ✅ postoje

**Ako tokom rada vidiš potrebu da izmeniš bilo koji od ovih fajlova** (npr. dodati polje u `UserResponse`, ili promeniti interceptor logiku), **objasni zašto pre nego što to uradiš** i sačekaj potvrdu.

---

## KRITIČNA PRAVILA (iz CLAUDE.md — ne krši nikad)

1. **Nema `localStorage` / `sessionStorage`** za tokene. Access token u Zustand memoriji, refresh u httpOnly cookie.
2. **App Router isključivo** (`app/`). Nema `pages/`.
3. **Server state = TanStack Query**. Nema ručnog `useEffect + fetch`.
4. **Forme = react-hook-form + zod resolver**.
5. **Naming:** TypeScript fajlovi `kebab-case.tsx`, React komponente `PascalCase`, API endpoint URL-ovi `kebab-case`.
6. **Nema Keycloak-a** — V1 je čisti JWT.
7. **Tipovi se importuju iz `@/types/*`** — nikad inline definicije po stranicama.
8. **Serbian UI labele** (latinica).
9. **`"use client"` direktiva** samo tamo gde je zaista potrebna — kalendar, forme, chat, sve sa hook-ovima. Page komponente koje samo sklapaju druge client komponente mogu ostati server components kad god je to moguće.

---

## RADNI TOK (STRIKTNO POŠTOVATI)

Ovaj zadatak je **veliki** — ~17 dana Filipovog posla iz ROADMAP-a. **Ne implementiraj sve odjednom.** Radi po fazama ispod. **Posle svake faze — stani, izlistaj šta je urađeno, šta si izmenio, i čekaj da ti potvrdim da idemo dalje.**

Za svaki fajl koji dodaješ ili menjaš:
- Poštuj kompletnu stazu iz `FRONTEND_STRUKTURA.md` (§ 2).
- Dodaj kratak docblock komentar na vrhu koji kaže šta fajl radi i odgovara li na neki ROADMAP korak.
- Ne dodaji unused imports, ne ostavljaj `console.log`.

---

## FAZA 0 — Priprema i sanity check (PRE KODA)

Pre bilo kakve izmene, uradi:

1. `ls frontend/components/ui/` — izlistaj šta shadcn komponente već postoje.
2. `cat frontend/package.json` — proveri šta je instalirano. Posebno: `@tanstack/react-query`, `zustand`, `react-hook-form`, `zod`, `@hookform/resolvers`, `@fullcalendar/react`, `socket.io-client`, `react-dropzone`, `lucide-react`, `next-pwa`, `date-fns`, `axios`, `class-variance-authority`, `clsx`, `tailwind-merge`.
3. `cat frontend/tsconfig.json` — potvrdi da postoji path alias `@/*`.
4. `cat frontend/components.json` — potvrdi shadcn config.
5. Proveri da li postoji `frontend/app/providers.tsx` i šta je trenutno u `frontend/app/layout.tsx`.
6. Proveri da li postoji `frontend/middleware.ts`.

**Izlaz Faze 0:** kratak izveštaj (max 20 linija):
- Šta nedostaje od paketa (i šta ćeš instalirati kroz `npm install ...`).
- Šta nedostaje od shadcn komponenti (i koje ćeš `npx shadcn add ...` komande pokrenuti).
- Da li path aliasi i providers.tsx postoje.
- Da li ti je bilo šta nejasno pre početka.

**STANI OVDE. Sačekaj potvrdu da krećeš u Fazu 1.**

---

## FAZA 1 — Foundation: UI primitivi + tipovi + API moduli + hooks

Ovo je **najvažnija faza.** Nema smisla praviti stranice dok ne postoji ovaj sloj — svaka stranica bi onda duplirala kod. Prati `FRONTEND_STRUKTURA.md` § 2 (struktura foldera) i § 5 (checklist Faze 2).

### 1.1 Shadcn UI komponente

Generiši sve shadcn komponente iz `FRONTEND_STRUKTURA.md` § 2 (`components/ui/` sekcija). Koristi `npx shadcn@latest add <komponenta>`. Ne menjaj ih posle generisanja.

### 1.2 Utility fajlovi (`lib/utils/`, `lib/constants/`)

Kreiraj sledeće fajlove sa konkretnim sadržajem (ne stubove):

- `lib/utils/cn.ts` — clsx + tailwind-merge helper (ako već ne postoji iz shadcn init-a).
- `lib/utils/date.ts` — `formatDateTime`, `formatDate`, `formatRelative` helperi nad `date-fns` sa sr locale-om.
- `lib/utils/file-size.ts` — bytes → "2.4 MB" format.
- `lib/utils/file-validation.ts` — MIME + max size 5MB check.
- `lib/utils/email-domain.ts` — `isStudentEmail`, `isStaffEmail`, `validateEmailDomain` (mirror logike iz backenda — `CLAUDE.md` § 4).
- `lib/utils/jwt.ts` — `decodeJwtPayload(token)` (samo dekodira base64, bez verifikacije — za UX čitanje `imp` claim-a).
- `lib/utils/errors.ts` — `toastApiError(err)` centralizovani handler. Implementacija iz `FRONTEND_STRUKTURA.md` § 6.4.
- `lib/constants/roles.ts` — Role enum + srpske labele.
- `lib/constants/topic-categories.ts` — 5 vrednosti iz PRD-a (`SEMINARSKI`, `PREDAVANJA`, `ISPIT`, `PROJEKAT`, `OSTALO`) + labele.
- `lib/constants/document-types.ts` — 6 tipova iz PRD §2.4 + labele.
- `lib/constants/nav-items.ts` — mape rute → ikona/label po roli (struktura iz `FRONTEND_STRUKTURA.md` § 3.3).
- `lib/constants/accepted-mime-types.ts` — iz `FRONTEND_STRUKTURA.md` § 3.8.
- `lib/constants/routes.ts` — centralizovane rute kao konstante.

### 1.3 TypeScript tipovi (`types/`)

Kreiraj sve fajlove iz `FRONTEND_STRUKTURA.md` § 2 (`types/` sekcija). **Kritično:** svaki tip mora 1:1 odgovarati Pydantic šemi u `backend/app/schemas/`. Pre nego što napišeš `types/professor.ts`, **otvori i pročitaj** `backend/app/schemas/professor.py` i uskladi polje po polje. Isto za sve ostale.

Ako backend šema za nešto ne postoji (jer je označena ❌ u ROADMAP 1.5 — `schemas/appointment.py`, `schemas/admin.py`, `schemas/document_request.py`, `schemas/notification.py`), **označi taj tip komentarom `// TODO: sync with backend when schema is implemented`** i koristi najbolju pretpostavku iz ROADMAP koraka 3.2, 3.3, 4.2, 4.3. Izlistaj u izlaznom izveštaju koje si šeme morao da pretpostaviš — to će posle ići na sync sa Stefanom.

Obavezni `types/common.ts` sadržaj je u `FRONTEND_STRUKTURA.md` § 3.9.

### 1.4 API moduli (`lib/api/`)

Kreiraj tanke wrapere (jedan fajl po feature-u iz § 2):
- `lib/api/students.ts`
- `lib/api/professors.ts`
- `lib/api/appointments.ts`
- `lib/api/document-requests.ts`
- `lib/api/admin.ts`
- `lib/api/notifications.ts`

Svaki `*Api` objekt ima metode koje vraćaju `Promise<T>` gde je `T` iz `@/types/*`. Pattern (primer):

```typescript
// lib/api/students.ts
import { api } from '@/lib/api';
import type { ProfessorSearchResponse, Paginated, AvailableSlotResponse } from '@/types';

export const studentsApi = {
  searchProfessors: (params: { q?: string; faculty?: Faculty; /* ... */ }) =>
    api.get<Paginated<ProfessorSearchResponse>>('/students/professors', { params }).then(r => r.data),
  // ...
};
```

**URL-ovi** moraju se poklapati sa backend rutama iz ROADMAP 1.1 i 1.6. Ako URL još ne postoji u bekendu (npr. `/admin/*` ruter je ❌), označi metodu komentarom `// TODO: backend endpoint not yet implemented (ROADMAP 4.3)` i **ostavi je — pozvati će se kad backend bude spreman**.

### 1.5 TanStack Query hooks (`lib/hooks/`)

Kreiraj sve hook fajlove iz `FRONTEND_STRUKTURA.md` § 2 (`lib/hooks/` sekcija). Pattern:

```typescript
// lib/hooks/use-appointments.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studentsApi } from '@/lib/api/students';
// ...

export function useMyAppointments(view: 'upcoming' | 'history' = 'upcoming') {
  return useQuery({
    queryKey: ['my-appointments', view],
    queryFn: () => studentsApi.listMyAppointments({ view }),
  });
}

export function useCreateAppointment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: studentsApi.createAppointment,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-appointments'] }),
  });
}
```

`queryKey` konvencija: `[feature, sub-resource, ...filters]` — npr. `['professors', 'search', q, faculty]`, `['appointments', id]`, `['notifications']`.

### 1.6 Zustand stores (`lib/stores/`)

Auth store već postoji. Dodati:
- `lib/stores/impersonation.ts` — state: `isImpersonating`, `adminId`, `originalUser`. Akcije: `setImpersonating`, `clearImpersonation`. Bez persistence — reset na refresh je OK (token ionako validira backend).
- `lib/stores/ui.ts` — (opciono) `sidebarOpen` za mobile. Može i kasnije.

### 1.7 Providers + Root layout

- `app/providers.tsx` — QueryClientProvider (staleTime: 30s default, refetchOnWindowFocus: false), Toaster, `<NotificationStream />` placeholder (komponenta nek postoji kao prazan client component — stvarna WS logika u Fazi 4).
- `app/layout.tsx` — omotava `<Providers>` oko `{children}`, html lang="sr", body klase iz Tailwind-a.

### 1.8 Middleware

Kreiraj `frontend/middleware.ts` — implementacija iz `FRONTEND_STRUKTURA.md` § 3.2.

### 1.9 Izlaz Faze 1

Kratak izveštaj:
- Lista dodatih fajlova (grupisana po folderu).
- Lista backend šema za koje si morao da pretpostaviš (ide Stefanu na sync).
- Da li TypeScript build prolazi (`cd frontend && npx tsc --noEmit`).

**STANI. Čekaj potvrdu.**

---

## FAZA 2 — AppShell i layouti po roli (ROADMAP 2.2)

### 2.1 Shell komponente (`components/shared/`)

Kreiraj sve iz `FRONTEND_STRUKTURA.md` § 2 (`components/shared/` sekcija). Fokus:

- `app-shell.tsx` — prima `role: Role` prop. Struktura iz § 3.3.
- `sidebar.tsx` — čita `NAV_ITEMS[role]` iz `lib/constants/nav-items.ts`. Aktivna ruta highlight-ovana.
- `sidebar-nav-item.tsx` — jedna stavka, koristi `usePathname()` za active state.
- `top-bar.tsx` — prostor za logo, `<NotificationCenter />` (može za sada biti prazna shell komponenta — bell ikona bez funkcionalnosti, to dolazi u Fazi 4), `<UserMenu />`.
- `user-menu.tsx` — avatar dropdown, stavke: "Profil" (disabled za sada), "Odjavi se" (poziva `authApi.logout()` + `clearAuth()` + router.push('/login')).
- `impersonation-banner.tsx` — conditional render (sakrivena po default-u). Čita `useImpersonationStore`. Kad je aktivna → crveni fiksni banner na vrhu preko čitavog ekrana sa tekstom "ADMIN MODE — Impersonirate [Ime]" + dugme "Izađi".
- `page-header.tsx` — `<h1>` + opis + optional slot za dugme desno.
- `empty-state.tsx` — ikonica + poruka + opciono dugme.
- `faculty-badge.tsx` — `FON`/`ETF` badge sa bojama.
- `role-gate.tsx` — `<RoleGate allowedRoles={['ADMIN']}>{children}</RoleGate>` helper.
- `protected-page.tsx` — wrapper koji čita auth store + redirektuje ako rola ne odgovara.

### 2.2 Layouti po roli

Izmeni:
- `frontend/app/(student)/layout.tsx` — `<AppShell role="STUDENT">{children}</AppShell>`
- `frontend/app/(professor)/layout.tsx` — isti pattern za PROFESOR/ASISTENT (može biti dva sidebar-a ili jedan — vidi open pitanja ispod).
- `frontend/app/(admin)/layout.tsx` — ADMIN.

### 2.3 Auth `(auth)/layout.tsx`

Centrirani container, bez shell-a. Može ostati jednostavan — jedino dodaj eventualno logo gore.

### 2.4 Acceptance kriterijumi

- Login kao student → /dashboard pokazuje AppShell sa STUDENT sidebar-om.
- Login kao admin → /admin sa ADMIN sidebar-om.
- Logout iz UserMenu-a stvarno loguje korisnika van.
- ImpersonationBanner se renderuje kad se ručno postavi store (testirati dev tool-om ako ADMIN flow nije još gotov).

### 2.5 Izlaz Faze 2

Kratak izveštaj + screenshoti ako si u stanju da pokreneš dev server (ako ne, samo opiši šta si dodao).

**STANI. Čekaj potvrdu.**

---

## FAZA 3 — Student core journey (ROADMAP 3.4 + 3.5 + 3.6)

**Ovo je primary user journey — najveći pojedinačni komad.** Uradi redosledom ispod.

### 3.1 Forgot + reset password (ROADMAP 3.4)

- `app/(auth)/forgot-password/page.tsx` — trenutno STUB, dopuni. Forma: email + submit → `authApi.forgotPassword`. Success message.
- `app/(auth)/reset-password/page.tsx` — kreirati. Čita `?token=...` iz URL-a. Forma: new password + confirm → `authApi.resetPassword`. Redirekt na /login.

### 3.2 Student dashboard (ROADMAP 3.4)

`app/(student)/dashboard/page.tsx` — trenutno STUB. Kartice (koristi `<Card>` iz shadcn):
- **Sledeći termini** — koristi `useMyAppointments({ view: 'upcoming', limit: 3 })`. Renderuje `<AppointmentCard />`.
- **Nepročitane notifikacije** — broj iz `useUnreadCount()` (hook može za sada da vrati 0 ako backend nije gotov, to je OK).
- **Strike status** — `<StrikeDisplay />`. Ako `/auth/me` ne vraća `total_strike_points` još (vidi open pitanje u `FRONTEND_STRUKTURA.md` § 7.3), hard-code-uj 0 sa TODO komentarom.

### 3.3 My appointments (ROADMAP 3.4)

`app/(student)/my-appointments/page.tsx` — Tabs iz shadcn: Upcoming / History. Tabela/kartice sa `<AppointmentCard />`. Otkazivanje kroz `<AppointmentCancelDialog />`.

Komponente:
- `components/appointments/appointment-card.tsx`
- `components/appointments/appointment-status-badge.tsx` — boja po statusu.
- `components/appointments/appointment-cancel-dialog.tsx` — potvrda + upozorenje za <24h sa strike warningom.
- `components/shared/strike-display.tsx`

### 3.4 Search (ROADMAP 3.5)

`app/(student)/search/page.tsx` — input za `q`, select za `faculty`, select za `consultation_type`, input za `subject`. Debounced search (koristi `useDebouncedValue` hook — kreiraj ga u `lib/hooks/use-debounced-value.ts` ako ne postoji). Grid `<ProfessorSearchCard />`.

Komponente:
- `components/student/professor-search-card.tsx` — klik vodi na `/professor/[id]`.

### 3.5 Professor profile (ROADMAP 3.5)

`app/(student)/professor/[id]/page.tsx`. **PRD UX pravilo: FAQ MORA biti iznad kalendara.** Struktura:
1. `<ProfessorProfileHeader />` (slika, ime, titula, departman, kancelarija, `<FacultyBadge />`).
2. Sekcija "Oblasti interesovanja" — tag chips.
3. `<ProfessorSubjectsList />`.
4. `<ProfessorFaqAccordion />` — shadcn Accordion.
5. `<BookingCalendar professorId={id} onSelectSlot={...} />`.
6. Klik na slot → `<Dialog>` sa `<AppointmentRequestForm />`.

Komponente:
- `components/student/professor-profile-header.tsx`
- `components/student/professor-subjects-list.tsx`
- `components/student/professor-faq-accordion.tsx`
- `components/calendar/booking-calendar.tsx` — FullCalendar (timegrid + daygrid + interaction), fetchuje kroz `useProfessorSlots`.
- `components/calendar/calendar-legend.tsx` — boje: slobodno / pun / moj termin.
- `components/calendar/slot-popover.tsx` — hover detalj.
- `components/appointments/appointment-request-form.tsx` — RHF + zod. Validacija: `topic_category` (enum), `description` (min 20, max 500), optional `subject_id`, optional file upload.
- `components/appointments/file-upload-zone.tsx` — react-dropzone wrapper. Validacija kroz `lib/utils/file-validation.ts`.
- `components/shared/waitlist-button.tsx` — toggle join/leave. Prikazuje se samo kad je slot pun.

### 3.6 Appointment detail + chat + files (ROADMAP 3.6)

`app/(student)/appointments/[id]/page.tsx` — deljena sa profesorom (vidi open pitanja ispod). Struktura:
1. `<AppointmentDetailHeader />` (status, datetime, tip, profesor).
2. Sekcija "Detalji" — topic_category + description.
3. `<TicketChat appointmentId={id} />`.
4. Sekcija "Fajlovi" — `<FileUploadZone />` + `<FileList />`.
5. Ako grupni — `<ParticipantList />` sa confirm/decline dugmadima.

Komponente:
- `components/appointments/appointment-detail-header.tsx`
- `components/appointments/participant-list.tsx` + `participant-row.tsx`
- `components/appointments/file-list.tsx` — prikaz + download (presigned URL iz API-ja) + delete.
- `components/chat/ticket-chat.tsx` — **za sada fallback na polling** kroz `GET /{id}/messages` svakih 2s (ROADMAP 3.6 to eksplicitno dozvoljava dok WS nije gotov). WebSocket integracija dolazi u Fazi 5.
- `components/chat/chat-message.tsx`
- `components/chat/chat-input.tsx` — counter "X/20 poruka", disable kad je max dostignut.
- `components/chat/chat-message-counter.tsx`
- `components/chat/chat-closed-notice.tsx` — banner kad je `slot_datetime + 24h <= now`.

### 3.7 Izlaz Faze 3

Šta je urađeno, koji stubovi su popunjeni (15 STUB-ova iz ROADMAP 1.7 — proveri koliko ti je ostalo), TypeScript build prolazi li, ima li runtime grešaka kad klikneš kroz flow.

**STANI. Čekaj potvrdu.**

---

## FAZA 4 — Professor portal (ROADMAP 3.7)

`app/(professor)/professor/dashboard/page.tsx` — Tabs: "Inbox zahteva" | "Moj kalendar".

`app/(professor)/professor/settings/page.tsx` — Tabs: "Profil" | "FAQ" | "Canned responses" | "Blackout periodi".

Komponente iz `FRONTEND_STRUKTURA.md` § 2 (`components/professor/`):
- `requests-inbox.tsx` + `request-inbox-row.tsx` + tri dialog-a (approve/reject/delegate).
- `profile-form.tsx` + `areas-of-interest-input.tsx` (tag input).
- `faq-list.tsx` + `faq-item-row.tsx` + `faq-form-dialog.tsx`.
- `canned-response-list.tsx` + `canned-response-form-dialog.tsx`.
- `blackout-manager.tsx`.
- `components/calendar/availability-calendar.tsx` — FullCalendar sa editable eventima (drag-drop). Na drop → `useCreateSlot`.
- `components/calendar/recurring-rule-modal.tsx` — weekly/monthly + date range.

ASISTENT ima identičan sidebar kao PROFESOR, ali u settings-u sakrij kartice koje su profesor-only (npr. kreiranje slota — asistenti ne upravljaju kalendarom). Koristi `<RoleGate>` za granularnu kontrolu.

**STANI. Čekaj potvrdu.**

---

## FAZA 5 — Admin panel + Document requests + Notifications + Chat WS (ROADMAP 4.7 + 4.8 + 4.1 WS integracija)

### 5.1 Admin stranice (6 stranica)

- `app/(admin)/admin/page.tsx` — overview metrics kartice.
- `app/(admin)/admin/users/page.tsx` — tabela + "Bulk import" dugme + per-row Edit/Deactivate/Impersonate.
- `app/(admin)/admin/document-requests/page.tsx` — Tabs po statusima + per-row actions.
- `app/(admin)/admin/strikes/page.tsx` — tabela + Unblock.
- `app/(admin)/admin/broadcast/page.tsx` — forma + history.
- `app/(admin)/admin/audit-log/page.tsx` — tabela sa filterima.

Komponente iz `components/admin/` sekcije FRONTEND_STRUKTURA.md.

**Impersonation flow** kritičan — prati `FRONTEND_STRUKTURA.md` § 3.6 korak po korak.

### 5.2 Document requests (student)

`app/(student)/document-requests/page.tsx` — `<DocumentRequestForm />` + lista `<DocumentRequestCard />`.

### 5.3 Notifications center

- `components/notifications/notification-center.tsx` — bell u top-bar-u, dropdown sa poslednjih 10 + counter.
- `components/notifications/notification-item.tsx`
- `components/notifications/notification-stream.tsx` — WebSocket klijent (native WS, ne socket.io — notifikacije ne idu kroz socket.io) za `/api/v1/notifications/stream`. Subskribuje → invalidate query → toast za kritične tipove.

### 5.4 Chat WebSocket migracija

Zameniti polling u `<TicketChat>` sa socket.io konekcijom. `lib/ws/chat-socket.ts` + `use-chat.ts` hook.

**STANI. Čekaj potvrdu.**

---

## FAZA 6 — Polish, PWA (ROADMAP 5.1, 5.2)

- Google PSE search box u top-bar-u ili na dashboard-u.
- `public/manifest.json` + `public/icons/*`.
- `next-pwa` konfiguracija u `next.config.mjs`.
- Offline cache strategija za `/my-appointments` i `/notifications`.
- (Opciono) Web Push subscription UI.

---

## OTVORENA PITANJA — PITAJ ME PRE NEGO ŠTO PROCENIŠ

Ne nagađaj na ovima. Kada stigneš do mesta gde je neophodno — stani i pitaj:

1. **Appointment detail shared route:** Da li pravimo jedan `/appointments/[id]` u `(student)` grupi i koristimo ga i za profesora, ili duplicat u `(professor)` grupi? (`FRONTEND_STRUKTURA.md` § 7.1)
2. **WebSocket JSON šeme:** Pre Faze 5 (chat WS, notification WS) treba dogovor sa Stefanom. Postoji li `docs/websocket-schema.md`? Ako ne — zastani, traži šemu.
3. **`total_strike_points` u `/auth/me`:** Hoće li biti dodato u backend `UserResponse` (ROADMAP 3.4 to traži) ili pravimo zaseban endpoint `/students/me/strikes`?
4. **Impersonation JWT format:** Kako tačno izgleda `imp` claim koji backend postavlja? Frontend mora znati da bi prikazao banner.
5. **ASISTENT sidebar vs PROFESOR:** Da li su identični ili asistent ima reducirani set? Moje podrazumevano: identični sa `<RoleGate>` filterom po stranici.
6. **Backend endpoint ne postoji još (ROADMAP ❌):** Kad neki `lib/api/*` metod poziva ne-postojeći backend ruter — samo ostavi metod implementiran, ali page koji je koristi stavi pod `<EmptyState>` sa porukom "Nije dostupno — backend in progress" dok backend ne bude gotov. Ne pravi mock podatke osim ako ti eksplicitno kažem.

---

## ZAVRŠNI CHECKLIST PRE SVAKOG COMMIT-A

Pre nego što predložiš commit (i pre nego što pređeš u sledeću fazu), proveri:

- [ ] `cd frontend && npx tsc --noEmit` prolazi bez grešaka.
- [ ] Nema `localStorage`/`sessionStorage` poziva.
- [ ] Nema `console.log`, `any` tipova (osim opravdanih sa `// TODO: tip sinhronizovati`), unused imports.
- [ ] Nema inline-ovanih tipova — sve iz `@/types/*`.
- [ ] Svi `useEffect + fetch` pattern-i su zamenjeni TanStack Query.
- [ ] Forme koriste RHF + zod.
- [ ] Naming conventions poštovane (fajlovi kebab-case, komponente PascalCase).
- [ ] Commit poruka formata `feat:`, `fix:`, `chore:`, `docs:` (kako traži ROADMAP).

---

## KOMUNIKACIJA SA MENOM

- **Ne piši duge eseje o arhitekturi** — ona je već definisana. Ako imaš ideju za odstupanje, predloži u 2-3 rečenice i čekaj odgovor.
- **Ako si u dilemi između dva pristupa** — opiši oba ukratko i pitaj.
- **Ako backend ne vraća podatak koji ti treba** — ne mock-uj, ne izmišljaj endpoint, samo reci "potreban mi je endpoint X — da li ga tražim od Stefana ili postoji već?".
- **Na kraju svake faze** — kratak izveštaj (šta si dodao / izmenio / šta fali) + "OK da krenem u Fazu N+1?".

---

## POČNI

Krenimo od **Faze 0**. Pročitaj sva 3 referentna dokumenta (+ PRD i Arhitekturu po potrebi), uradi sanity check iz Faze 0, i vrati izveštaj.
