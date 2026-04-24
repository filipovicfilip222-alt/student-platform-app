# ROADMAP.md — Studentska Platforma

**Od:** Filip (project lead)
**Za:** Filip + Stefan (backend)
**Datum:** April 2026
**Referentni dokumenti:** `CLAUDE.md`, `docs/PRD_Studentska_Platforma.md`, `docs/Arhitektura_i_Tehnoloski_Stek.md`, `docs/copilot_plan_prompt.md`

> Ovaj dokument je snimak stanja + plan sledećih faza. Sinhronizovan je sa trenutnim codebase-om. Ažurirati uz svaki PR koji menja scope.

---

## DEO 1 — SNIMAK STANJA

Legenda: ✅ radi • ⚠️ djelimično / stub / bug • ❌ ne postoji

### 1.1 Backend — API routeri

| Prefix | Router fajl | Registrovan u `main.py` | Status | Napomena |
|--------|-------------|-------------------------|--------|---------|
| `/api/v1/auth` | `app/api/v1/auth.py` | ✅ | ✅ | Svi endpointi iz PRD §6 (register, login, refresh, logout, forgot, reset, me) |
| `/api/v1/students` | `app/api/v1/students.py` | ✅ | ⚠️ | Search + profil + slots + booking + waitlist rade. Nedostaju document-requests endpointi, grupne konsultacije (participants confirm/decline) |
| `/api/v1/professors` | `app/api/v1/professors.py` | ✅ | ⚠️ | Samo slots + blackout CRUD. Nedostaju: profile GET/PUT, requests inbox (approve/reject/delegate), canned_responses CRUD, CRM CRUD, FAQ CRUD |
| `/api/v1/appointments` | — | ❌ | ❌ | Fajl ne postoji. Nedostaje: GET detalji, messages, WS chat, file upload, participants confirm/decline |
| `/api/v1/admin` | — | ❌ | ❌ | Fajl ne postoji. Nedostaje sve iz PRD §3.5 (users CRUD, bulk import, impersonacija, strikes, broadcast, document-requests inbox, audit log) |
| `/api/v1/notifications` | — | ❌ | ❌ | Fajl ne postoji. Nedostaje GET list, mark read, WS stream |
| `/api/v1/search` | — | ❌ | ❌ | Fajl ne postoji. Nedostaje Google PSE proxy |
| `/api/v1/health` | `app/main.py` | ✅ | ✅ | Health check radi |

### 1.2 Backend — Modeli (SQLAlchemy)

| Model | Fajl | Status | Napomena |
|-------|------|--------|---------|
| `User` | `models/user.py` | ✅ | Svi property-ji + relacije |
| `Professor` | `models/professor.py` | ✅ | `areas_of_interest TEXT[]`, auto_approve_*, buffer_minutes |
| `Subject` + `subject_assistants` | `models/subject.py` | ✅ | M2M association tabela tu |
| `AvailabilitySlot` + `BlackoutDate` | `models/availability_slot.py` | ✅ | `recurring_rule JSONB`, valid_from/until |
| `Appointment` + `AppointmentParticipant` + `Waitlist` | `models/appointment.py` | ✅ | Tri tabele u jednom fajlu |
| `File` | `models/file.py` | ✅ | `minio_object_key` |
| `TicketChatMessage` | `models/chat.py` | ✅ | CASCADE delete po appointment-u |
| `CrmNote` | `models/crm_note.py` | ✅ | |
| `StrikeRecord` + `StudentBlock` | `models/strike.py` | ✅ | |
| `FaqItem` | `models/faq.py` | ✅ | sort_order |
| `Notification` | `models/notification.py` | ✅ | `data JSONB` |
| `AuditLog` | `models/audit_log.py` | ✅ | `ip_address INET` |
| `CannedResponse` | `models/canned_response.py` | ✅ | |
| `DocumentRequest` | `models/document_request.py` | ✅ | |
| `PasswordResetToken` | `models/password_reset_token.py` | ✅ | SHA-256 `token_hash` |
| `AppointmentStatus` enum | `models/enums.py` | ✅ | `NO_SHOW` uklonjen iz AppointmentStatus, ostao samo u `StrikeReason` |

### 1.3 Backend — Servisi

| Servis | Fajl | Status | Šta radi |
|--------|------|--------|----------|
| `auth_service` | `services/auth_service.py` | ✅ | Registracija, login, refresh, logout, forgot/reset |
| `search_service` | `services/search_service.py` | ✅ | Pretraga + profil + slobodni slotovi (sa `unaccent` od migracije 0002) |
| `booking_service` | `services/booking_service.py` | ✅ | Redis Lua lock, create/cancel/list appointments |
| `availability_service` | `services/availability_service.py` | ✅ | Slot CRUD + blackout |
| `waitlist_service` | `services/waitlist_service.py` | ✅ | Redis Sorted Set, join/leave, issue_offer |
| `strike_service` | `services/strike_service.py` | ✅ | add_strike (LATE_CANCEL, NO_SHOW), blokada 14/21/+7d, unblock |
| `professor_portal_service` | — | ❌ | GET/PUT profil, requests inbox, approve/reject/delegate |
| `crm_service` | — | ❌ | CRUD beleški |
| `canned_response_service` | — | ❌ | CRUD šablona |
| `faq_service` | — | ❌ | CRUD FAQ |
| `chat_service` | — | ❌ | WebSocket chat + Redis Pub/Sub + max 20 msg limit + 24h auto-close |
| `notification_service` | — | ❌ | In-app notifikacije + counter + WS stream |
| `file_service` | — | ❌ | MinIO upload + presigned URL (appointment + avatar + document) |
| `user_service` | — | ❌ | Admin CRUD, bulk CSV import |
| `document_request_service` | — | ❌ | Student create/list, admin approve/reject/complete |
| `broadcast_service` | — | ❌ | Target group filtering + Celery fan-out |
| `impersonation_service` | — | ❌ | Start/end + audit log |
| `audit_log_service` | — | ❌ | List + filter |

### 1.4 Backend — Celery taskovi

| Task | Fajl | Status | Napomena |
|------|------|--------|---------|
| `email_tasks.send_email` | `tasks/email_tasks.py` | ✅ | smtplib + STARTTLS + retry 3x |
| `notifications.send_appointment_confirmed` | `tasks/notifications.py` | ✅ | Šalje student-u kad je APPROVED |
| `notifications.send_appointment_rejected` | `tasks/notifications.py` | ✅ | Sa razlogom |
| `notifications.send_appointment_reminder` | `tasks/notifications.py` | ✅ | Generički (hours_before) — **nije vezan za beat schedule** |
| `notifications.send_strike_added` | `tasks/notifications.py` | ✅ | |
| `notifications.send_block_activated` | `tasks/notifications.py` | ✅ | |
| `notifications.send_waitlist_offer` | `tasks/notifications.py` | ✅ | |
| `notifications.send_appointment_cancelled` | `tasks/notifications.py` | ❌ | PRD §5.2 — nedostaje |
| `notifications.send_document_request_*` | `tasks/notifications.py` | ❌ | approved + rejected |
| `strike_tasks.detect_no_show` | `tasks/strike_tasks.py` | ✅ | Beat: svakih 30 min |
| `waitlist_tasks.process_waitlist_offers` | `tasks/waitlist_tasks.py` | ⚠️ | **BUG: `timedelta` nije importovan** (linija 83) — task će pući pri izvršenju |
| `reminder_tasks.schedule_reminder_24h` | — | ❌ | Nije Celery-beat vezan; treba periodic scan |
| `reminder_tasks.schedule_reminder_1h` | — | ❌ | Nedostaje |
| `broadcast_tasks.fanout_broadcast` | — | ❌ | Admin broadcast → target group → per-user email + in-app |

### 1.5 Backend — Schemas (Pydantic V2)

| Šema | Status |
|------|--------|
| `schemas/auth.py` | ✅ Kompletno |
| `schemas/professor.py` | ⚠️ Samo Slot + Blackout. Nema ProfessorProfile (GET/PUT), CRM, FAQ, CannedResponse, RequestApprove/Reject |
| `schemas/student.py` | ⚠️ Search + profil + booking. Nema DocumentRequest, WaitlistPositionResponse |
| `schemas/appointment.py` | ❌ Nema (chat, files, participants) |
| `schemas/admin.py` | ❌ Nema (users CRUD, bulk import, broadcast, strikes list, audit log) |
| `schemas/document_request.py` | ❌ Nema |
| `schemas/notification.py` | ❌ Nema |
| `schemas/file.py` | ❌ Nema |

### 1.6 Backend — Gap u odnosu na PRD

| PRD sekcija | Implementirano | Gap |
|-------------|----------------|-----|
| §1.2 Auth | ✅ JWT, bcrypt, email whitelist, forgot/reset | — |
| §2.1 Smart Search | ✅ q, faculty, subject, type | ❌ Google PSE proxy (`/api/v1/search/university`) |
| §2.2 Sistem zakazivanja | ✅ Booking + Redis lock + blackout | ❌ Grupne konsultacije (tagovanje kolega + participant confirm/decline endpoints) |
| §2.3 Upravljanje terminima | ✅ 24h pravilo + strike sistem + no-show detekcija | — |
| §2.4 Document requests | ❌ Samo model | ❌ Sve (student + admin endpointi, email notifikacije) |
| §2.5 Google PSE | ❌ | ❌ Cel endpoint + env varijable |
| §3.1 Availability | ✅ CRUD slotova, blackout | ⚠️ Recurring rule polje postoji ali **nema ekspanzije u date range** — frontend dobija jedan zapis sa `recurring_rule JSONB`, a ne listu generisanih slotova |
| §3.2 Obrada zahteva | ❌ | ❌ Profesor requests inbox, approve/reject/delegate, canned responses CRUD |
| §3.3 Chat + CRM | ❌ | ❌ WebSocket chat, CRM beleške CRUD |
| §4.1 Admin users | ❌ | ❌ Sve (CRUD, bulk CSV, impersonacija, audit log, broadcast) |
| §4.2 Admin document requests | ❌ | ❌ Sve |
| §5.1 Strike sistem | ✅ Automatika | ⚠️ Admin `/strikes` stranica je UI-implementirana, ali endpoint još nedostaje (unblock) |
| §5.2 Notifikacije | ⚠️ 6/10 emailova | ⚠️ `NotificationCenter` UI postoji, polling fallback radi; WS stream čeka backend |
| §5.3 PWA | ✅ manifest.json, service worker (next-pwa), offline cache, offline indicator | ❌ VAPID / Web Push endpoint |

### 1.7 Frontend — Stranice

Legenda (dodatno): 🟢 = UI implementiran i povezan na stvarni backend; 🟡 = UI implementiran, ali se oslanja na backend endpoint koji još ne postoji (videti kolonu "Backend zavisnost").

| URL | Fajl | Status | Backend zavisnost |
|-----|------|--------|---------|
| `/` | `app/page.tsx` | 🟢 redirect na `/login` (middleware obrađuje autentifikovane) | — |
| `/login` | `app/(auth)/login/page.tsx` | 🟢 Puna implementacija (RHF + zod + shadcn) | `/auth/login` ✅ |
| `/register` | `app/(auth)/register/page.tsx` | 🟢 Puna (domain validation) | `/auth/register` ✅ |
| `/forgot-password` | `app/(auth)/forgot-password/page.tsx` | 🟢 | `/auth/forgot-password` ✅ |
| `/reset-password` | `app/(auth)/reset-password/page.tsx` | 🟢 | `/auth/reset-password` ✅ |
| `/dashboard` | `app/(student)/dashboard/page.tsx` | 🟢 Kartice: sledeći termini, nepročitane, strike | `/students/appointments` ✅, strikes⚠️ |
| `/search` | `app/(student)/search/page.tsx` | 🟢 Debounced + filteri | `/students/professors/search` ✅ |
| `/professor/[id]` | `app/(student)/professor/[id]/page.tsx` | 🟢 Profile + FAQ iznad kalendara + BookingCalendar | `/students/professors/{id}` ✅, slots ✅ |
| `/appointments/[id]` | `app/(student)/appointments/[id]/page.tsx` | 🟡 UI + polling chat fallback | `/appointments/{id}` ❌ (ROADMAP 3.6) |
| `/my-appointments` | `app/(student)/my-appointments/page.tsx` | 🟢 Tabs upcoming/history + cancel dialog sa strike warning-om | `/students/appointments` ✅ |
| `/document-requests` | `app/(student)/document-requests/page.tsx` | 🟡 UI forma + lista | `/students/document-requests` ❌ (ROADMAP 3.6/4.8) |
| `/professor/dashboard` | `app/(professor)/professor/dashboard/page.tsx` | 🟡 Inbox + kalendar | `/professors/requests` ❌ (ROADMAP 3.7) |
| `/professor/settings` | `app/(professor)/professor/settings/page.tsx` | 🟡 Profile / FAQ / canned / blackout | `/professors/profile/faq/canned/...` ❌ (ROADMAP 3.7) |
| `/admin` | `app/(admin)/admin/page.tsx` | 🟡 Metrics kartice | `/admin/*` ❌ (ROADMAP 4.7) |
| `/admin/users` | `app/(admin)/admin/users/page.tsx` | 🟡 Tabela + bulk import + per-row akcije | `/admin/users` ❌ (ROADMAP 4.7) |
| `/admin/document-requests` | `app/(admin)/admin/document-requests/page.tsx` | 🟡 Tabs po statusu + approve/reject dialozi | `/admin/document-requests` ❌ (ROADMAP 4.8) |
| `/admin/strikes` | `app/(admin)/admin/strikes/page.tsx` | 🟡 Tabela + unblock dugme | `/admin/strikes` ❌ (ROADMAP 4.7) |
| `/admin/broadcast` | `app/(admin)/admin/broadcast/page.tsx` | 🟡 Forma + history | `/admin/broadcast` ❌ (ROADMAP 4.7) |
| `/admin/audit-log` | `app/(admin)/admin/audit-log/page.tsx` | 🟡 Tabela sa filterima | `/admin/audit-log` ❌ (ROADMAP 4.7) |

**Zaključak:** 19/19 stranica ima kompletan UI. 9/19 je 🟢 (povezano na live backend), 10/19 je 🟡 (čeka se Stefanov backend da bi postalo 🟢; axios wrappers, tipovi, hooks, forme i table su već napisani).

### 1.8 Frontend — Komponente

| Komponenta | Lokacija | Status |
|-----------|----------|--------|
| Shadcn primitivi (Button, Card, Form, Input, Label, Dialog, Sheet, Select, Dropdown, Tabs, Toast/Sonner, Avatar, Scroll-Area, Accordion, Tooltip, Switch, Badge, Popover, RadioGroup, Calendar/DayPicker, Command, AlertDialog, Separator) | `components/ui/` | ✅ |
| `<AppShell />`, `<Sidebar />`, `<TopBar />`, `<UserMenu />`, `<PageHeader />`, `<EmptyState />`, `<FacultyBadge />`, `<RoleGate />`, `<ProtectedPage />` | `components/shared/` | ✅ |
| `<ImpersonationBanner />`, `<OfflineIndicator />` | `components/shared/` | ✅ |
| `<StrikeDisplay />`, `<WaitlistButton />` | `components/shared/` | ✅ |
| `<BookingCalendar />`, `<CalendarLegend />`, `<SlotPopover />` | `components/calendar/` | ✅ |
| `<AvailabilityCalendar />`, `<RecurringRuleModal />` | `components/calendar/` | ✅ |
| `<AppointmentCard />`, `<AppointmentStatusBadge />`, `<AppointmentCancelDialog />`, `<AppointmentRequestForm />`, `<AppointmentDetailHeader />`, `<ParticipantList />`, `<ParticipantRow />`, `<FileList />`, `<FileUploadZone />` | `components/appointments/` | ✅ |
| `<TicketChat />`, `<ChatMessage />`, `<ChatInput />`, `<ChatMessageCounter />`, `<ChatClosedNotice />` | `components/chat/` | ✅ (polling fallback) |
| `<ProfessorSearchCard />`, `<ProfessorProfileHeader />`, `<ProfessorSubjectsList />`, `<ProfessorFaqAccordion />` | `components/student/` | ✅ |
| `<RequestsInbox />`, `<RequestInboxRow />`, tri dialog-a (approve/reject/delegate), `<ProfileForm />`, `<AreasOfInterestInput />`, `<FaqList />` + `<FaqItemRow />` + `<FaqFormDialog />`, `<CannedResponseList />` + `<CannedResponseFormDialog />`, `<BlackoutManager />` | `components/professor/` | ✅ |
| `<AdminDashboardMetrics />`, `<UsersTable />`, `<UserFormModal />`, `<BulkImportDialog />`, `<StrikesTable />`, `<AuditLogTable />`, `<BroadcastForm />` | `components/admin/` | ✅ |
| `<NotificationCenter />`, `<NotificationItem />`, `<NotificationStream />`, `<PushSubscriptionToggle />` (disabled stub) | `components/notifications/` | ✅ |
| `<DocumentRequestForm />`, `<DocumentRequestList />`, `<AdminRequestRow />`, `<ApproveDialog />`, `<RejectDialog />` | `components/document-requests/` | ✅ |

### 1.9 Frontend — API klijenti, storovi, hooks, tipovi

| Modul | Fajl | Status |
|-------|------|--------|
| Axios + JWT interceptor | `lib/api.ts` | ✅ Refresh queue, auto-logout na 401 |
| `authApi` | `lib/api/auth.ts` | ✅ |
| `studentsApi` (search, professor profile, slots, appointments, waitlist) | `lib/api/students.ts` | ✅ |
| `professorsApi` (profile, slots, requests, canned, crm, faq) | `lib/api/professors.ts` | ✅ |
| `appointmentsApi` (detail, messages, files, participants) | `lib/api/appointments.ts` | ✅ (čeka backend da stvarno radi) |
| `adminApi` (users, impersonate, strikes, broadcast, audit, documents) | `lib/api/admin.ts` | ✅ (čeka backend) |
| `documentRequestsApi` | `lib/api/document-requests.ts` | ✅ (čeka backend) |
| `notificationsApi` | `lib/api/notifications.ts` | ✅ (čeka backend) |
| `searchApi` (Google PSE) | — | ❌ Preskočeno u Fazi 6 (backend 5.1 nije isporučen); `GlobalSearchBox` je disabled sa tooltipom "Dostupno uskoro" |
| `useAuthStore` | `lib/stores/auth.ts` | ✅ |
| `useNotificationStore` (WS + counter) | `lib/stores/notification-ws-status.ts` + `lib/hooks/use-notifications.ts` | ✅ (polling fallback; WS spreman za aktivaciju kad backend 4.2 stigne) |
| `useImpersonationStore` (banner state) | `lib/stores/impersonation.ts` + `lib/hooks/use-impersonation.ts` | ✅ |
| TanStack Query hooks (`lib/hooks/`) | `lib/hooks/` | ✅ `use-professors`, `use-appointments`, `use-availability`, `use-requests-inbox`, `use-document-requests`, `use-notifications`, `use-admin-users`, `use-strikes`, `use-audit-log`, `use-chat`, `use-impersonation` |
| TypeScript tipovi | `types/` | ✅ `auth`, `professor`, `appointment`, `admin`, `document-request`, `notification`, `chat`, `ws`, `common`, barrel `index.ts` |
| WebSocket klijenti | `lib/ws/` | ✅ `notification-socket.ts` (live), `chat-socket.ts` (pripremljen, koristi polling do backend 4.1) |
| JWT util | `lib/utils/jwt.ts` | ✅ (decode access tokena za WS query param) |
| PWA manifest + next-pwa config | `public/manifest.json`, `next.config.mjs` | ✅ |
| PWA ikonice (192/512/maskable + apple-touch + favicons) | `public/icons/` | ✅ Generisano preko `npm run generate:icons` (skripta u `scripts/generate-icons.mjs`) |
| Offline indicator | `components/shared/offline-indicator.tsx` | ✅ |
| Push subscription toggle | `components/notifications/push-subscription-toggle.tsx` | ✅ Disabled stub (čeka backend VAPID) |
| Playwright E2E | `frontend/playwright.config.ts`, `frontend/e2e/` | ✅ smoke + auth + student-search + professor-view; `student-booking` / `professor-approve` / `admin-bulk-import` / `strike-system` deferovani dok backend ne stigne |

### 1.10 Infrastruktura

| Komponenta | Lokacija | Status |
|-----------|----------|--------|
| Docker Compose (postgres, redis, minio, minio-init, nginx, backend, frontend) | `infra/docker-compose.yml` | ✅ |
| Backend volume mount (`../backend:/app`) | `infra/docker-compose.yml` | ✅ Dodato u prethodnom PR |
| `celery-worker`, `celery-beat` servisi | `infra/docker-compose.yml` | ✅ Dodato u prethodnom PR |
| Django-celery-beat DatabaseScheduler | `backend/requirements.txt` | ⚠️ Beat komanda u compose koristi `django_celery_beat.schedulers:DatabaseScheduler`, ali paket **nije u `requirements.txt`** — beat će pući pri startu; treba ili dodati paket + migraciju, ili zameniti na `celery.beat.PersistentScheduler` |
| Nginx reverse proxy + WS upgrade | `infra/nginx/nginx.conf` | ✅ |
| MinIO init-buckets (4 bucketa) | `infra/minio/init-buckets.sh` | ✅ |
| Alembic async env + initial schema + unaccent | `backend/alembic/` | ✅ 2 migracije |
| Seed skripta | `scripts/seed_db.py` | ✅ |
| `.env.example` (backend + frontend) | — | ✅ |
| `docker-compose.prod.yml` | — | ❌ |
| SSL/TLS + Let's Encrypt | — | ❌ |
| PWA (manifest.json + service worker) | `frontend/public/manifest.json`, `frontend/next.config.mjs` (next-pwa) | ✅ (bez push — čeka backend VAPID) |
| Rate limiting (nginx `limit_req` ili FastAPI middleware) | — | ❌ |
| Postman/Insomnia kolekcija | `docs/api-collection.json` | ❌ |
| CI/CD (GitHub Actions) | `.github/workflows/` | ❌ |
| Backup strategija (postgres, minio) | — | ❌ |

### 1.11 Poznati bugovi u postojećem kodu

1. **`backend/app/tasks/waitlist_tasks.py:83`** — koristi `timedelta(...)` bez importa. Treba dodati `from datetime import timedelta` (već postoji `datetime, timezone` u istom importu).
2. **`infra/docker-compose.yml` celery-beat** — scheduler `django_celery_beat.schedulers:DatabaseScheduler` nije u `requirements.txt`.
3. **`backend/app/main.py`** — komentar kaže da se routeri još ne registruju ali `students.router` i `professors.router` su registrovani; treba očistiti zakomentarisane `admin`, `appointments`, `search`, `notifications` jednom kada budu dodati.

---

## DEO 2 — PRIORITETI

Pre plana, razmišljanje o tome šta je najvažnije.

### 2.1 Šta blokira najviše drugih feature-a?

1. **`/api/v1/appointments/{id}` endpoint** — blokira: frontend appointment detail stranicu, chat, fajlove, participant confirm/decline. Do sada student samo može da kreira/otkaže termin, ali ne može da vidi detalje ili komunicira. Ovo je prerequisite za 2 druge frontend stranice i WebSocket chat.
2. **Frontend `lib/api/` moduli** — blokira sve ne-auth frontend stranice. Bez njih, svaka stranica koju student/profesor/admin piše mora sama da pravi axios pozive što vodi u duplicate.
3. **Layout shell komponente** — prazni `(student)/layout.tsx`, `(professor)/layout.tsx`, `(admin)/layout.tsx` nemaju sidebar/nav/top-bar. Sve stranice će izgledati "gole" bez zajedničkog navigation-a. Ovo treba **jednom** napraviti pre svih ostalih.

### 2.2 Šta je user-facing a trenutno ne postoji?

**Nijedan feature iz PRD-a nije vidljiv studentu/profesoru/adminu kroz UI** osim login/register/logout. To znači da demo aplikacije trenutno staje na login screen-u. Najbrže do "demo ready" stanja:

- **Student dashboard + search + professor profile + booking flow** — to je primary journey.
- **Professor dashboard + availability calendar** — da profesor može da postavi slotove.

### 2.3 Šta je tehnički dug koji će se kasnije teže rešavati?

1. **Bug u `waitlist_tasks.py`** — trenutno Celery beat svakih 5 min pokušava da pozove task i baca NameError. Treba popraviti **odmah** (trivijalno, jedan red).
2. **`django_celery_beat` scheduler** — ako se ne popravi, ceo Celery beat ne radi od prvog startup-a. Treba odlučiti hoćemo li dodati paket (zahteva i Django instalaciju + migracije, što je overkill za FastAPI projekat) ili se vratiti na `celery.beat.PersistentScheduler`. Preporuka: **PersistentScheduler** — jednostavnije, nema Django overhead-a.
3. **Recurring slots — logika ekspanzije** — trenutno se čuva `recurring_rule JSONB`, ali ne postoji servis koji iz njega generiše pojedinačne `AvailabilitySlot` zapise. Bez toga profesor ne može da kaže "svakog utorka 10–12h sledećih 8 nedelja" jer će se čuvati kao jedan zapis, a search/booking gleda pojedinačne datume. Treba ili (a) raspakivati rule pri GET-u, ili (b) pravo na kreiranje eksplicitno generiše N slot zapisa.
4. **Frontend tipovi duplirani na više mesta** — `types/auth.ts` je jedini fajl. Ako svaki developer piše svoje tipove uz stranicu, doći će do odstupanja od backend šeme. Treba **odmah** uvesti konvenciju: jedan tip po entitetu u `types/`, svi importi iz tog jednog fajla.

### 2.4 Šta je ključno za MVP a nije ni početo?

| Feature | Ne postoji uopšte | Uticaj |
|---------|-------------------|--------|
| **Document requests (ceo tok)** | Backend + frontend | PRD §2.4 i §4.2 — jedan od 2 core feature-a studentske službe |
| **Admin panel (CRUD korisnika + bulk import)** | Backend + frontend | Bez toga admin ne može da kreira profesore/asistente. Seed radi, ali u produkciji treba UI |
| **WebSocket chat (per-appointment)** | Backend + frontend | PRD §3.3 |
| **Notifikacije + WebSocket stream** | Backend + frontend | PRD §5.2 — ceo mehanizam "bell" dropdown-a nema |
| **Professor request inbox (approve/reject/delegate)** | Backend + frontend | PRD §3.2 — profesori ne mogu da obrađuju zahteve |
| **Grupne konsultacije (tagovanje kolega)** | Backend + frontend | PRD §2.2 |

### 2.5 Zaključak — 5 prioritetnih oblasti

1. **Fix postojećih bugova + infra hardening** (HIGH) — waitlist_tasks import, Celery beat scheduler, main.py cleanup. *0.5 dana.*
2. **Shared frontend foundation** (HIGH) — layout shell-ovi (sidebar + nav + impersonation banner), TanStack Query hooks, api moduli, TypeScript tipovi. Bez ovoga, svaka stranica dupla kod. *2 dana.*
3. **Student booking journey (E2E)** (HIGH) — search stranica + professor profile + BookingCalendar + AppointmentRequestForm + my-appointments. Ovo je demo-able. *4-5 dana.*
4. **Professor portal + backend dopuna** (HIGH) — professor dashboard + availability calendar + requests inbox; backend: profile GET/PUT + requests approve/reject/delegate + canned responses + FAQ + CRM. *4-5 dana.*
5. **Document requests + Admin panel + Chat/Notifications/Impersonation** (MEDIUM) — ostatak PRD-a. *7-10 dana.*

**Ukupna procena do MVP-a**: ~18-22 dana za 2 developera (paralelno).

---

## DEO 3 — PLAN FAZA

Markeri za podelu rada:
- `[BACKEND]` — Stefan (backend dev A)
- `[FRONTEND]` — Filip (frontend/project lead)
- `[INFRA]` — bilo ko (DevOps)
- `[FULLSTACK]` — zahteva sinhronizaciju, obično API kontrakt dogovor

---

## FAZA 2 — Stabilizacija + Shared Foundation

**Cilj:** Popraviti postojeće bugove, uvesti zajedničke frontend strukture koje će svaka feature stranica koristiti.

**Ukupno trajanje:** ~3 dana (paralelno)

---

### Korak 2.1 — Popraviti postojeće bugove [BACKEND] [INFRA] — **HIGH**

**Fajlovi:**
- `backend/app/tasks/waitlist_tasks.py` — dodati `timedelta` u postojeći `from datetime import ...` import (trenutno nedostaje, linija 83).
- `backend/requirements.txt` — NE dodavati `django-celery-beat`.
- `infra/docker-compose.yml` — promeniti `celery-beat` command iz `--scheduler django_celery_beat.schedulers:DatabaseScheduler` u `--scheduler celery.beat.PersistentScheduler` (default).
- `backend/app/main.py` — obrisati stale komentare o zakomentarisanim routerima za one koji su već registrovani; ostaviti komentare samo za buduće (`admin`, `appointments`, `search`, `notifications`).

**Acceptance kriterijumi:**
- `docker compose --profile app up` digne i `celery-beat` kontejner bez greške.
- Ručnim pozivom `celery -A app.celery_app call waitlist_tasks.process_waitlist_offers` task prolazi bez `NameError`.
- `main.py` ima samo relevantne komentare.

**Zavisnosti:** —

**Procena:** 2-4 sata

---

### Korak 2.2 — Frontend: layout shell sa sidebar + nav [FRONTEND] — **HIGH**

Svi `(student)/layout.tsx`, `(professor)/layout.tsx`, `(admin)/layout.tsx` su trenutno prazni. Implementirati zajednički shell.

**Novi fajlovi:**
- `frontend/components/shared/app-shell.tsx` — sidebar + top-bar + content area
- `frontend/components/shared/sidebar.tsx` — navigacija po roli (ikone iz `lucide-react`)
- `frontend/components/shared/user-menu.tsx` — avatar dropdown (profile, logout)
- `frontend/components/shared/impersonation-banner.tsx` — crveni baner (skriven po default-u, pokazan ako je `useImpersonationStore` aktivan)
- `frontend/components/ui/sheet.tsx`, `dropdown-menu.tsx`, `avatar.tsx`, `separator.tsx` — shadcn komponente (generisati iz `shadcn add`)
- `frontend/lib/stores/impersonation.ts` — Zustand store za impersonation state

**Izmene:**
- `frontend/app/(student)/layout.tsx` — wrap `<AppShell role="STUDENT">` oko children
- `frontend/app/(professor)/layout.tsx` — isto za `PROFESOR`
- `frontend/app/(admin)/layout.tsx` — isto za `ADMIN`

**Sidebar rute po roli (koristi aktivne URL-ove):**
- STUDENT: `/dashboard`, `/search`, `/my-appointments`, `/document-requests`
- PROFESOR / ASISTENT: `/professor/dashboard`, `/professor/settings`
- ADMIN: `/admin`, `/admin/users`, `/admin/document-requests`, `/admin/strikes`, `/admin/broadcast`, `/admin/audit-log`

**Acceptance kriterijumi:**
- Sve 3 grupe imaju isti izgled shell-a (sidebar levo, top-bar gore, content desno).
- Login kao student → vidi student sidebar, sa admin sidebar ne može pristupiti.
- Logout dugme iz `user-menu` radi (poziva `authApi.logout()` + `clearAuth()`).

**Zavisnosti:** —

**Procena:** 1-1.5 dan

---

### Korak 2.3 — Frontend: API moduli + TypeScript tipovi [FRONTEND] — **HIGH**

Infrastruktura za sve buduće stranice. Ne piše se business logika, samo tanki wrapperi.

**Novi fajlovi (tipovi — usklađeni sa Pydantic šemama):**
- `frontend/types/professor.ts` — `ProfessorSearchResponse`, `ProfessorProfileResponse`, `FaqResponse`, `SlotResponse`, `BlackoutResponse`, `CannedResponse`, `CrmNote`
- `frontend/types/appointment.ts` — `AppointmentResponse`, `AppointmentCreateRequest`, `AppointmentCancelResponse`, `AvailableSlotResponse`, `ParticipantResponse`, `ChatMessageResponse`, `FileResponse`
- `frontend/types/admin.ts` — `AdminUserResponse`, `BulkImportPreview`, `StrikeRow`, `AuditLogRow`, `BroadcastRequest`
- `frontend/types/document-request.ts` — `DocumentRequestResponse`, `DocumentRequestCreate`, `DocumentRequestApprove`, `DocumentRequestReject`
- `frontend/types/notification.ts` — `NotificationResponse`
- `frontend/types/common.ts` — `Paginated<T>`, `ConsultationType`, `TopicCategory`, enums

**Novi fajlovi (API klijenti):**
- `frontend/lib/api/students.ts` — `studentsApi` (searchProfessors, getProfessor, getProfessorSlots, createAppointment, cancelAppointment, listMyAppointments, joinWaitlist, leaveWaitlist)
- `frontend/lib/api/professors.ts` — `professorsApi` (getProfile, updateProfile, listSlots, createSlot, updateSlot, deleteSlot, createBlackout, deleteBlackout, listRequests, approveRequest, rejectRequest, delegateRequest, cannedResponses CRUD, crm CRUD, faq CRUD)
- `frontend/lib/api/appointments.ts` — `appointmentsApi` (getAppointment, listMessages, uploadFile, listFiles, deleteFile, confirmParticipant, declineParticipant)
- `frontend/lib/api/admin.ts` — `adminApi` (users CRUD, bulkImport, impersonateStart, impersonateEnd, listStrikes, unblock, broadcast, listDocumentRequests, approveDocument, rejectDocument, completeDocument, auditLog)
- `frontend/lib/api/document-requests.ts` — `documentRequestsApi` (student create + list)
- `frontend/lib/api/notifications.ts` — `notificationsApi` (list, markRead, markAllRead)

**Novi fajlovi (TanStack Query hooks):**
- `frontend/lib/hooks/use-professors.ts` — `useProfessorSearch`, `useProfessor`, `useProfessorSlots`
- `frontend/lib/hooks/use-appointments.ts` — `useMyAppointments`, `useAppointment`, `useCreateAppointment`, `useCancelAppointment`
- `frontend/lib/hooks/use-availability.ts` — `useMySlots`, `useCreateSlot`, `useDeleteSlot`, `useBlackouts`
- `frontend/lib/hooks/use-requests-inbox.ts` — `useRequestsInbox`, `useApproveRequest`, `useRejectRequest`
- `frontend/lib/hooks/use-document-requests.ts` — `useMyDocumentRequests`, `useCreateDocumentRequest`, `useAdminDocumentRequests`
- `frontend/lib/hooks/use-notifications.ts` — `useNotifications` sa `refetchInterval: 30000`
- `frontend/lib/hooks/use-admin-users.ts`, `use-strikes.ts`, `use-audit-log.ts`

**Acceptance kriterijumi:**
- Svaki API modul je tanki wrapper nad `api` axios instancom (ne dodaje logiku, samo `api.get<T>(...)`, `api.post<T>(...)`).
- Tipovi se importuju iz `@/types/*`, nikad se ne definiraju inline u stranicama.
- `useProfessorSearch('Petrovic')` vraća listu prof-a koja nađe Petrović (kroz `unaccent` migraciju 0002).

**Zavisnosti:** Korak 2.1 (ne kritično, ali bolje da bugovi budu rešeni pre nego što frontend zove backend).

**Procena:** 1 dan

---

## FAZA 3 — Core User Journeys (Student + Professor)

**Cilj:** Demo-able aplikacija gde student može da nađe profesora i zakaže termin, a profesor može da upravlja slotovima i obrađuje zahteve.

**Ukupno trajanje:** ~9 dana (paralelno)

---

### Korak 3.1 — Backend: professor portal endpointi [BACKEND] — **HIGH**

Trenutno `/api/v1/professors/*` ima samo slotove i blackout. Nedostaje ostalih 80% iz PRD §3.

**Novi fajlovi:**
- `backend/app/schemas/professor.py` — dodati: `ProfessorProfileResponse` (GET /profile), `ProfessorProfileUpdate` (PUT /profile), `RequestInboxFilter`, `RequestInboxRow`, `RequestApproveRequest`, `RequestRejectRequest`, `RequestDelegateRequest`, `CannedResponseCreate/Update/Response`, `FaqCreate/Update/Response` (ako treba, `search_service.FaqResponse` postoji već), `CrmNoteCreate/Update/Response`
- `backend/app/services/professor_portal_service.py` — `get_profile`, `update_profile`, `list_requests(filter=all|pending)`, `approve_request(id)`, `reject_request(id, reason)`, `delegate_request(id, assistant_id)`
- `backend/app/services/canned_response_service.py` — CRUD
- `backend/app/services/crm_service.py` — `list_for_student`, `create_note`, `update_note`, `delete_note` (provera da je autor)
- `backend/app/services/faq_service.py` — `list_mine`, `create`, `update`, `delete`
- `backend/app/api/v1/professors.py` — dodati endpointe iz `copilot_plan_prompt §3.3`:
  - `GET /profile`, `PUT /profile`
  - `GET /requests?filter=pending|all`
  - `POST /requests/{id}/approve`
  - `POST /requests/{id}/reject`
  - `POST /requests/{id}/delegate`
  - `GET /canned-responses`, `POST /canned-responses`, `PUT /canned-responses/{id}`, `DELETE /canned-responses/{id}`
  - `GET /crm/{student_id}`, `POST /crm/{student_id}`, `PUT /crm/{note_id}`, `DELETE /crm/{note_id}`
  - `GET /faq`, `POST /faq`, `PUT /faq/{id}`, `DELETE /faq/{id}`

**Pravila:**
- Sve `async def`, `CurrentProfesor` ili `CurrentProfesorOrAsistent` gde PRD dozvoli asistentu.
- Approve → poziva `send_appointment_confirmed.delay(appointment_id)`.
- Reject → čuva `rejection_reason`, poziva `send_appointment_rejected.delay(appointment_id, reason)`.
- Delegate → proverava da asistent pripada istom predmetu (preko `subject_assistants` tabele).
- CRM: STUDENT ne može ni da vidi ni da menja (`CurrentProfesorOrAsistent` dependency).

**Acceptance kriterijumi:**
- Swagger prikazuje nove endpointe pod "Professors" tagom.
- Integracioni test (Swagger ili pytest): prof1 login → POST slot → student zakazuje → prof1 vidi u `/requests?filter=pending` → `/approve` menja status u APPROVED i šalje email (vidljivo u Celery flower / SMTP log-u).

**Zavisnosti:** —

**Procena:** 2-2.5 dana

---

### Korak 3.2 — Backend: document requests (oba toka) [BACKEND] — **HIGH**

**Novi fajlovi:**
- `backend/app/schemas/document_request.py` — `DocumentRequestCreate` (document_type, note), `DocumentRequestResponse`, `DocumentRequestApproveRequest` (pickup_date, admin_note), `DocumentRequestRejectRequest` (admin_note)
- `backend/app/services/document_request_service.py` — `create_as_student(student, data)`, `list_my(student)`, `list_for_admin(filter)`, `approve(admin, id, pickup_date, note)`, `reject(admin, id, note)`, `complete(admin, id)`
- `backend/app/api/v1/students.py` — dodati: `POST /document-requests`, `GET /document-requests`
- `backend/app/api/v1/admin.py` — **novi fajl**, endpointi `GET /document-requests`, `POST /document-requests/{id}/approve`, `POST /document-requests/{id}/reject`, `POST /document-requests/{id}/complete`
- `backend/app/tasks/notifications.py` — dodati: `send_document_request_approved(student_id, pickup_date, note)`, `send_document_request_rejected(student_id, note)`
- `backend/app/main.py` — registrovati `admin.router`

**Acceptance kriterijumi:**
- Student kreira zahtev → admin ga vidi u `/admin/document-requests` → approve sa `pickup_date="2026-05-10"`, `admin_note="Soba 12"` → student dobija email + in-app notif (ako notification servis postoji; inače samo email).
- Admin može da odbije sa obaveznim `admin_note`.
- Admin `complete` postavlja status na COMPLETED (student je preuzeo dokument).

**Zavisnosti:** —

**Procena:** 1-1.5 dan

---

### Korak 3.3 — Backend: appointment detail + files [BACKEND] — **MEDIUM**

**Novi fajlovi:**
- `backend/app/schemas/appointment.py` — `AppointmentDetailResponse` (sa slot, prof, student, files, participants), `ChatMessageResponse`, `ChatMessageCreate`, `FileResponse`, `ParticipantConfirmResponse`
- `backend/app/services/appointment_detail_service.py` — `get_detail(user, appointment_id)` sa RBAC (samo učesnik ili profesor)
- `backend/app/services/file_service.py` — MinIO helper: `upload(bucket, key, data)`, `presigned_get_url(bucket, key, ttl=3600)`, `delete(bucket, key)`; validacija MIME + max 5MB
- `backend/app/api/v1/appointments.py` — **novi fajl**:
  - `GET /{id}` — detalji
  - `GET /{id}/messages` — istorija chat poruka (paginated)
  - `POST /{id}/files` — multipart upload
  - `GET /{id}/files` — lista (sa presigned URL-ovima)
  - `DELETE /{id}/files/{file_id}`
  - `POST /{id}/participants/confirm` — student potvrđuje grupno učešće
  - `POST /{id}/participants/decline`
- `backend/app/main.py` — registrovati `appointments.router`

**Acceptance kriterijumi:**
- Student koji je lead može da vidi `/api/v1/appointments/{id}` sa listom fajlova i participants.
- Student koji nije učesnik dobija 403.
- Upload fajla > 5MB → 413; upload `.exe` → 422; PDF/DOCX/ZIP prolazi.
- `GET /{id}/files` vraća presigned URL-ove validne 1h.

**Zavisnosti:** Nijedna.

**Procena:** 1.5-2 dana

---

### Korak 3.4 — Frontend: forgot-password, dashboard, my-appointments [FRONTEND] — **MEDIUM**

**Izmene:**
- `frontend/app/(auth)/forgot-password/page.tsx` — forma (email + submit → `authApi.forgotPassword`) + success message. Pattern identičan login stranici.
- `frontend/app/(student)/dashboard/page.tsx` — kartica "Sledeći termini" (koristi `useMyAppointments({ view: 'upcoming' })`, limit 3), kartica "Nepročitane notifikacije" (count), kartica "Strike status" (`<StrikeDisplay />` — nova komponenta).
- `frontend/app/(student)/my-appointments/page.tsx` — `<Tabs>` Upcoming / History; tabela/kartice sa statusom, mogućnost otkazivanja (`useCancelAppointment`).

**Nove komponente:**
- `frontend/components/shared/strike-display.tsx` — prikazuje broj poena + datum isteka blokade (poziva `adminApi` ili novi `studentsApi.getMyStrikes` — novi backend endpoint **NIJE potreban ako se strike podatak uzima iz `/auth/me`**; alternativa: dodati `total_strike_points` u `UserResponse` Pydantic šemu).
- `frontend/components/appointments/appointment-card.tsx` — kartica termina sa statusom badge-om i akcijama.

**Acceptance kriterijumi:**
- Login kao student → /dashboard pokazuje 3 sledeća termina + notif count + strike status.
- /my-appointments → upcoming tab lista termine, history tab završene, otkaz dugme radi i prikazuje toast.

**Zavisnosti:** Korak 2.2, 2.3.

**Procena:** 1.5 dan

---

### Korak 3.5 — Frontend: search + professor profile + booking [FRONTEND] — **HIGH**

Primary user journey. Najveći pojedinačni komad.

**Izmene:**
- `frontend/app/(student)/search/page.tsx`:
  - Input za `q`, Select za `faculty` (FON/ETF), Select za `consultation_type` (UZIVO/ONLINE), Input za `subject`.
  - Debounced search (`useProfessorSearch(q, filters)` sa TanStack Query).
  - Grid kartica profesora sa imenom, titulom, departmanom, listom predmeta, `<Badge>` za consultation types.
  - Klik na karticu → `/professor/[id]`.
- `frontend/app/(student)/professor/[id]/page.tsx`:
  - Header: slika, ime, titula, departman, fakultet, kancelarija.
  - Sekcija "Oblasti interesovanja" (tags).
  - Sekcija "Predmeti" (list).
  - Sekcija "FAQ" (`<Accordion>` iz shadcn).
  - `<BookingCalendar professorId={id} onSelectSlot={...} />` — FullCalendar (daygrid + timegrid) sa slobodnim slotovima.
  - Klik na slot → `<Dialog>` sa `<AppointmentRequestForm />`.
- **PRD UX pravilo:** FAQ sekcija mora biti **iznad** kalendara. Student vidi FAQ pre nego što klikne "Zakaži".

**Nove komponente:**
- `frontend/components/calendar/booking-calendar.tsx` — `@fullcalendar/react` sa `timegrid`, `dayGridPlugin`, `interactionPlugin`. Props: `professorId`, `onSelectSlot(slotId)`. Fetchuje preko `useProfessorSlots(professorId, rangeStart, rangeEnd)`.
- `frontend/components/appointments/appointment-request-form.tsx` — react-hook-form + zod:
  - `topic_category` Select (5 vrednosti iz `TopicCategory`)
  - `description` Textarea (min 20, max 500) — zod validacija
  - Optional `subject_id` select (predmeti profesora)
  - File upload (`react-dropzone` — treba dodati u `package.json`)
  - Submit → `useCreateAppointment` mutation → toast + redirect na `/appointments/[id]`.
- `frontend/components/shared/waitlist-button.tsx` — pokazuje "Prijavi se na waitlist" kad je slot pun; toggleuje `joinWaitlist`/`leaveWaitlist`.

**Izmene:**
- `frontend/package.json` — dodati `react-dropzone`.

**Acceptance kriterijumi:**
- Student ukuca "Petrovic" u search → dobija "Milovan Petrović" (unaccent radi).
- Klik na profesora → profil stranica sa FAQ iznad kalendara.
- Klik na slobodan slot → modal sa formom → submit → 409 ako je neko drugi istovremeno zakazivao (Redis lock), inače APPROVED ili PENDING.
- Ako je slot pun ali postoji buduć slot, waitlist dugme radi.

**Zavisnosti:** Korak 2.2, 2.3. Backend iz Koraka 3.1 za `subject_id` dropdown (nije blokirajuće, može se raditi paralelno).

**Procena:** 3-4 dana

---

### Korak 3.6 — Frontend: appointment detail + chat + files [FRONTEND] — **MEDIUM**

**Izmene:**
- `frontend/app/(student)/appointments/[id]/page.tsx` — postaje zajednička stranica za student/prof (nije više STUB):
  - Header: status badge, slot datetime, professor name, consultation type.
  - Sekcija "Detalji": topic_category, description.
  - `<TicketChat appointmentId={id} />` — WebSocket chat komponenta.
  - Sekcija "Fajlovi" — upload (`react-dropzone`) + lista sa presigned URL-ovima (download linkovi).
  - Ako je grupni termin: lista participants sa statusima + "Potvrdi/Odbij" dugmad (ako je current user participant sa PENDING statusom).
  - Ako je termin prošao + profesor: "Označi kao završeno" dugme.

**Nove komponente:**
- `frontend/components/chat/ticket-chat.tsx` — socket.io-client WebSocket. Props: `appointmentId`. State: `messages`, `input`. Max 20 msg indikator. 24h countdown do zatvaranja. Scroll-to-bottom.
- `frontend/components/appointments/file-upload-zone.tsx` — wrapper nad `react-dropzone`.
- `frontend/components/appointments/file-list.tsx` — lista sa download linkovima + delete (za uploader-a).

**Acceptance kriterijumi:**
- Student i profesor su na istoj stranici; chat radi u real-time između 2 browsera.
- Upload PDF < 5MB radi, prikazuje se u listi sa download linkom koji otvara MinIO presigned URL.
- 21. poruka je blokirana (UI disable + toast).

**Zavisnosti:** Korak 3.3 (backend `/appointments/{id}` + files). WebSocket chat backend iz Faze 4 — u međuvremenu `<TicketChat>` može fallback-ovati na `GET /{id}/messages` polling sa 2s interval dok WS ne bude gotov.

**Procena:** 2 dana

---

### Korak 3.7 — Frontend: professor dashboard + settings [FRONTEND] — **HIGH**

**Izmene:**
- `frontend/app/(professor)/professor/dashboard/page.tsx`:
  - Tabs: "Inbox zahteva" | "Moj kalendar"
  - Inbox tab: tabela sa filterima (PENDING default), kolone: student, slot datetime, topic, description; akcije dugmad Approve / Reject (+ canned response dropdown) / Delegate (+ asistent select). Koristi `useRequestsInbox`.
  - Kalendar tab: `<AvailabilityCalendar />` — read-write, drag-and-drop za kreiranje slotova.
- `frontend/app/(professor)/professor/settings/page.tsx`:
  - Tabs: "Profil" | "FAQ" | "Canned responses" | "Blackout periodi"
  - Profil: forma (title, department, office, office_description, areas_of_interest tag input, buffer_minutes, auto_approve_* switches).
  - FAQ: lista sa sort_order drag + dodavanje nove FAQ stavke.
  - Canned responses: lista + CRUD modal.
  - Blackout: kalendarski picker + lista aktivnih.

**Nove komponente:**
- `frontend/components/calendar/availability-calendar.tsx` — FullCalendar sa editable events (drag-drop). Na drop: `useCreateSlot`. Dodatno: recurring rule modal (weekly/monthly, date range, duration).
- `frontend/components/professor/canned-response-list.tsx`
- `frontend/components/professor/faq-list.tsx`
- `frontend/components/professor/blackout-manager.tsx`

**Acceptance kriterijumi:**
- Profesor drag-drop na prazan dan → kreiran slot.
- Zahtev u inboxu → "Reject" otvara dropdown sa canned responses → klik na jedan popunjava razlog → submit šalje email.
- FAQ sort_order se čuva.

**Zavisnosti:** Korak 2.2, 2.3, 3.1.

**Procena:** 3 dana

---

### Korak 3.8 — Backend: recurring slots ekspanzija [BACKEND] — **MEDIUM**

Professor kreira "svakog utorka 10:00 sledećih 8 nedelja" — servis treba da generiše 8 pojedinačnih `AvailabilitySlot` zapisa (ili raspakuje pri GET-u).

**Odluka:** Eksplicitno generisanje N zapisa pri kreiranju (jednostavnije za search/booking, radi sa trenutnim šemom).

**Izmene:**
- `backend/app/services/availability_service.py` — izmeniti `create_slot`:
  - Ako `recurring_rule is None` → kreiraj jedan slot (trenutno ponašanje).
  - Ako `recurring_rule` postoji → parsiraj (`freq`, `by_weekday`, `count`/`until`) i generiši N zapisa, svi sa istim `recurring_rule` JSONB (radi kasnijeg brisanja grupe).
- `backend/app/schemas/professor.py` — `SlotCreate.recurring_rule` tip neka bude `RecurringRule | None` (Pydantic model sa poljima `freq: Literal["WEEKLY","MONTHLY"]`, `by_weekday: list[int]`, `count: int | None`, `until: date | None`).
- Novi endpoint: `DELETE /api/v1/professors/slots/recurring/{recurring_group_id}` — briše sve buduće slotove iste grupe (identifikovane po istom `recurring_rule` JSONB i istom `valid_from`).

**Acceptance kriterijumi:**
- POST sa `recurring_rule={ freq: WEEKLY, by_weekday: [1], count: 8 }` i `slot_datetime: 2026-05-05 10:00` → 8 zapisa u bazi.
- GET `/slots` vraća svih 8.
- Student search normalno nalazi svih 8.

**Zavisnosti:** Korak 3.1.

**Procena:** 1 dan

---

## FAZA 4 — Chat, Notifikacije, Admin, Document Requests UI

**Cilj:** Realno-vremenski komunikacioni sloj + kompletan admin panel + document requests E2E.

**Ukupno trajanje:** ~10 dana (paralelno)

---

### Korak 4.1 — Backend: WebSocket chat + Redis Pub/Sub [BACKEND] — **HIGH**

**Novi fajlovi:**
- `backend/app/services/chat_service.py`:
  - `send_message(appointment_id, sender, content)` — RBAC (samo učesnik), max 1000 chars, persist u `ticket_chat_messages`, `await redis.publish("chat:pub:{appointment_id}", msg_json)`.
  - `list_messages(appointment_id, limit=20)` — history (max 20 msg per appointment per PRD).
  - `is_chat_closed(appointment)` — true ako `appointment.slot.slot_datetime + 24h <= now`.
- `backend/app/api/v1/appointments.py` — dodati WebSocket endpoint:
  ```python
  @router.websocket("/{id}/chat")
  async def chat_ws(websocket: WebSocket, id: UUID, token: str = Query(...)):
      # 1. Validate JWT
      # 2. Validate appointment RBAC
      # 3. Subscribe to Redis chat:pub:{id}
      # 4. on receive: chat_service.send_message(...)
      # 5. on Pub/Sub message: websocket.send_json(...)
  ```
- `backend/app/main.py` — već registrovan `appointments.router` iz Koraka 3.3.

**Acceptance kriterijumi:**
- 2 browsera (student + profesor) otvore `/appointments/{id}` → poruka iz jednog stiže u drugi < 1s.
- 24h posle termina → WS endpoint odbija novi connect sa 4403.
- 21. poruka → 409 Conflict.

**Zavisnosti:** Korak 3.3.

**Procena:** 1.5 dan

---

### Korak 4.2 — Backend: notifications (in-app + WS stream) [BACKEND] — **HIGH**

**Novi fajlovi:**
- `backend/app/schemas/notification.py` — `NotificationResponse` (id, type, title, body, data, is_read, created_at)
- `backend/app/services/notification_service.py`:
  - `create(user_id, type, title, body, data)` — insert u `notifications`, increment `notif:unread:{user_id}` counter, `redis.publish("notif:pub:{user_id}", json)`.
  - `list_recent(user_id, limit=50)`
  - `mark_read(user_id, notification_id)` — decrement counter.
  - `mark_all_read(user_id)` — reset counter.
- `backend/app/api/v1/notifications.py` — **novi fajl**:
  - `GET /` — listu
  - `POST /{id}/read`
  - `POST /read-all`
  - `WS /stream` — subscribe to Pub/Sub
- `backend/app/main.py` — registrovati `notifications.router`.

**Izmene:**
- `backend/app/tasks/notifications.py` — svaki `send_*` task osim slanja email-a, **takođe** poziva `notification_service.create(...)` da napravi in-app notifikaciju. Ovo je granularniji PRD §5.2 (email + in-app oba).

**Acceptance kriterijumi:**
- Student zakazuje termin → profesor istovremeno u drugom browseru dobija in-app notifikaciju bez reload-a (WS stream).
- "Bell" counter → `redis.get("notif:unread:{user_id}")` radi.

**Zavisnosti:** Korak 3.1 (da postoje events koji generišu notifikacije).

**Procena:** 1.5 dan

---

### Korak 4.3 — Backend: admin users CRUD + bulk import [BACKEND] — **HIGH**

**Novi fajlovi:**
- `backend/app/schemas/admin.py` — `AdminUserCreateRequest` (email, first_name, last_name, role, faculty, optional professor_profile), `AdminUserUpdate`, `AdminUserResponse`, `BulkImportPreviewResponse`, `BulkImportConfirmRequest`
- `backend/app/services/user_service.py`:
  - `list_users(filter)` — paginated
  - `create_user(admin, data)` — validira domen + role match (staff domen → PROFESOR/ASISTENT/ADMIN, student domen → STUDENT), generiše temp password, šalje welcome email
  - `update_user(admin, id, data)`
  - `deactivate_user(admin, id)` — soft delete (`is_active=False`)
  - `bulk_import_preview(admin, csv_bytes)` — parsira CSV, vraća validacione greške + duplikate + preview red
  - `bulk_import_confirm(admin, csv_bytes)` — kreira sve validne redove
- `backend/app/api/v1/admin.py` — dodati:
  - `GET /users`
  - `POST /users`
  - `PUT /users/{id}`
  - `DELETE /users/{id}`
  - `POST /users/bulk-import` (multipart CSV)
  - `POST /users/bulk-import/confirm`

**Acceptance kriterijumi:**
- Admin kreira profesor-a sa `profesor3@fon.bg.ac.rs` → dobija email sa temp password-om.
- Upload CSV sa 100 studenata → preview prikazuje 2 duplikata + 1 invalid domen; confirm kreira 97 korisnika.

**Zavisnosti:** —

**Procena:** 2 dana

---

### Korak 4.4 — Backend: admin impersonation + audit log [BACKEND] — **MEDIUM**

**Novi fajlovi:**
- `backend/app/services/impersonation_service.py`:
  - `start_impersonation(admin, target_user_id, ip)` — kreira `AuditLog` zapis (`action="IMPERSONATE_START"`), generiše posebne JWT claimove (`imp: admin_id`, `sub: target_user_id`), vraća access token.
  - `end_impersonation(admin)` — `AuditLog` zapis + vrati na originalni admin JWT.
- `backend/app/services/audit_log_service.py` — `list_entries(filter)`
- `backend/app/api/v1/admin.py` — dodati:
  - `POST /impersonate/{user_id}` — vraća token
  - `POST /impersonate/end`
  - `GET /audit-log?filter=...`

**Izmene:**
- `backend/app/core/dependencies.py` — `get_current_user` treba da postavi flag na `User` objektu ako je JWT imao `imp` claim (za frontend banner).

**Acceptance kriterijumi:**
- Admin klikne "Impersonate" → dobija novi access token → sledeći `/auth/me` vraća target user-a sa `_impersonated_by_admin_id` poljem.
- `/admin/audit-log` lista sve impersonation start/end events + IP.

**Zavisnosti:** Korak 4.3 (za users CRUD).

**Procena:** 1 dan

---

### Korak 4.5 — Backend: admin strikes + broadcast [BACKEND] — **MEDIUM**

**Novi fajlovi:**
- `backend/app/api/v1/admin.py` — dodati:
  - `GET /strikes` — lista studenata sa points >= 1 (paginated, sortable)
  - `POST /strikes/{student_id}/unblock` — poziva `strike_service.unblock_student(...)`
  - `POST /broadcast` — target_group (`FACULTY:FON`, `FACULTY:ETF`, `YEAR:2024`, `ROLE:PROFESOR`), kanali (email + in-app).
- `backend/app/services/broadcast_service.py` — `send_broadcast(admin, target, channels, title, body)` → fan-out Celery task.
- `backend/app/tasks/broadcast_tasks.py` — `fanout_broadcast_task(broadcast_id)` — učitaj user_ids → za svaki: `send_email` + `notification_service.create`.

**Acceptance kriterijumi:**
- Admin šalje broadcast "Ispitni rok" target=FACULTY:FON → svi FON korisnici dobijaju email + in-app notif.
- Dan max 10 broadcastova (rate limit) — opciono.

**Zavisnosti:** Korak 4.2 (notifications).

**Procena:** 1 dan

---

### Korak 4.6 — Backend: reminder taskovi + Celery beat [BACKEND] — **MEDIUM**

**Novi fajlovi:**
- `backend/app/tasks/reminder_tasks.py`:
  - `send_reminders_24h_task()` — scan APPROVED termini 24h ± 30min → `send_appointment_reminder.delay(id, 24)` (ako nije već poslat — idempotency key u Redis-u)
  - `send_reminders_1h_task()` — isto za 1h

**Izmene:**
- `backend/app/celery_app.py` — dodati u `beat_schedule`:
  ```python
  "send-reminders-24h-every-30-minutes": {
      "task": "reminder_tasks.send_reminders_24h",
      "schedule": crontab(minute="*/30"),
  },
  "send-reminders-1h-every-15-minutes": {
      "task": "reminder_tasks.send_reminders_1h",
      "schedule": crontab(minute="*/15"),
  },
  ```

**Acceptance kriterijumi:**
- Zakazan termin za 24h → u sledećem 30-min prozoru student i profesor dobijaju email.
- Zakazan termin za 1h → u sledećem 15-min prozoru dobijaju drugi email.
- Nema dupliranja (ako beat trigeruje 2 puta, idempotency key sprečava).

**Zavisnosti:** —

**Procena:** 1 dan

---

### Korak 4.7 — Frontend: admin panel [FRONTEND] — **HIGH**

Implementacija svih 6 admin stranica — sve su trenutno STUB.

**Izmene:**
- `frontend/app/(admin)/admin/page.tsx` — dashboard sa statistikama (broj korisnika po ulogama, broj pending requests, no-show stopa). Koristi nove backend endpointe ili samo počne sa "Welcome" panelom.
- `frontend/app/(admin)/admin/users/page.tsx`:
  - Table sa filterima (role, faculty, search)
  - "Dodaj korisnika" dugme → modal sa formom
  - "Bulk import" dugme → `<BulkImportModal />`
  - Per-row: Edit, Deactivate, "Impersonate" dugme
- `frontend/app/(admin)/admin/document-requests/page.tsx` — Tabs (PENDING/APPROVED/REJECTED/COMPLETED) + tabela + per-row akcije (Approve modal sa pickup_date, Reject sa reason, Complete)
- `frontend/app/(admin)/admin/strikes/page.tsx` — tabela studenata sa poenima, per-row "Unblock" dugme sa reason modal
- `frontend/app/(admin)/admin/broadcast/page.tsx` — forma (title, body textarea, target select, channels checkbox) + history
- `frontend/app/(admin)/admin/audit-log/page.tsx` — `<AuditLogTable />` sa filterima (admin_id, action type, date range)

**Nove komponente:**
- `frontend/components/admin/bulk-import-modal.tsx` — CSV dropzone → preview tabela sa errors → Confirm
- `frontend/components/admin/user-form-modal.tsx` — create/edit user
- `frontend/components/admin/document-request-admin-row.tsx` — actions: approve/reject/complete
- `frontend/components/admin/audit-log-table.tsx`
- `frontend/components/admin/strike-row.tsx`

**Acceptance kriterijumi:**
- Admin može da kreira profesora ručno ili kroz CSV bulk import.
- Admin može da odobri document request sa datumom preuzimanja.
- Admin može da impersonira bilo kog korisnika → **`<ImpersonationBanner />` postaje crveni top-bar** sa "Exit impersonation" dugmetom.

**Zavisnosti:** Korak 2.2, 2.3, 3.2, 4.3, 4.4, 4.5.

**Procena:** 3-4 dana

---

### Korak 4.8 — Frontend: document requests (student) + notifications center [FRONTEND] — **MEDIUM**

**Izmene:**
- `frontend/app/(student)/document-requests/page.tsx`:
  - `<DocumentRequestForm />` (document_type Select iz 6 vrednosti, note Textarea) — submit
  - Lista postojećih zahteva (`<DocumentRequestCard />`) — sortirana po datumu, status badge.

**Nove komponente:**
- `frontend/components/document-requests/document-request-form.tsx`
- `frontend/components/document-requests/document-request-card.tsx`
- `frontend/components/notifications/notification-center.tsx` — bell ikonica u top-baru sa counter-om, dropdown sa poslednjih 10, "Vidi sve" link.
- `frontend/components/notifications/notification-stream.tsx` — WebSocket client koji subskrajbuje na `/api/v1/notifications/stream`, invalidate-uje TanStack Query `notifications` kada stiže nova poruka.

**Izmene shell-a:**
- `frontend/components/shared/app-shell.tsx` — dodati `<NotificationCenter />` u top-bar.
- `frontend/app/providers.tsx` — pokretati `<NotificationStream />` kad je user logovan.

**Acceptance kriterijumi:**
- Student popuni formu → zahtev se pojavljuje u listi sa status PENDING.
- Kad admin odobri → student dobija notifikaciju **bez reload-a** (WS stream).
- Bell counter se ažurira u real-time.

**Zavisnosti:** Korak 2.2, 2.3, 3.2, 4.2.

**Procena:** 1.5 dan

---

## FAZA 5 — Polish, PWA, Produkcija

**Cilj:** Production-ready deploy, PWA, testovi, performance.

**Ukupno trajanje:** ~5 dana

---

### Korak 5.1 — Google PSE proxy [FULLSTACK] — **LOW**

- `backend/app/api/v1/search.py` — `GET /university?q=...` — proxy na Google Custom Search API, ograničeno na `fon.bg.ac.rs` i `etf.bg.ac.rs` preko `GOOGLE_PSE_CX`. Cache u Redis-u (ttl 1h) po `q`.
- Frontend: dodati search box u shell ili kao sekciju na dashboard-u.

**Procena:** 0.5 dana

---

### Korak 5.2 — PWA [INFRA] [FRONTEND] — **MEDIUM**

- `frontend/public/manifest.json`
- `frontend/public/icons/*` — 192x192, 512x512, maskable
- Service worker (`next-pwa` je već u `package.json`, samo konfigurisati u `next.config.mjs`)
- Offline read-only cache za `/my-appointments` i `/notifications`.
- Web Push API — zahteva VAPID keys (backend endpoint `POST /notifications/subscribe`).

**Procena:** 1.5 dana

---

### Korak 5.3 — Produkcijska infra [INFRA] — **HIGH**

- `infra/docker-compose.prod.yml` — bez volume mounts, sa `restart: always`, SSL sertifikati.
- Let's Encrypt + Certbot u nginx kontejneru.
- Rate limiting u nginx-u za `/api/v1/auth/login` i `/api/v1/auth/register`.
- Backup cron za Postgres (`pg_dump`) + MinIO (`mc mirror`).
- `.github/workflows/ci.yml` — test + build + deploy.

**Procena:** 1.5 dana

---

### Korak 5.4 — Testovi + performance [BACKEND] [FRONTEND] — **MEDIUM**

- Backend: pytest-asyncio integracioni testovi za: booking (Redis lock concurrency), strike flow, waitlist offer, document requests. ❌ (Stefan)
- Frontend: Playwright E2E za: student booking journey, professor approve flow, admin bulk import. ⚠️ Scaffold je postavljen u Fazi 6 (`frontend/e2e/`, `playwright.config.ts`); specovi koji zahtevaju backend endpoint-e su deferovani (ROADMAP 3.6/3.7/4.7/4.8) — videti `frontend/e2e/README.md`.
- Load test: Locust ili k6 — 100 simultanih studenata zakazuju isti slot → nijedan double booking. ❌ (Stefan)

**Procena:** 2 dana

---

## FAZA 6 — Frontend finish (zatvaranje pre produkcije)

**Cilj:** Finalni frontend polish, PWA, offline, E2E scaffold, SEO, dokumentacija. Sve što ne zavisi od nedovršenih backend modula je ✅; sve što zavisi je jasno markirano kao blocker.

**Status:** ✅ završeno za deo koji je Filipov (frontend). Blocker-i idu Stefanu.

---

### Korak 6.1 — Pre-flight cleanup [FRONTEND] — **DONE**

- Audit `// TODO: backend endpoint not yet implemented` komentara (oni koji su još validni ostavljeni; ostali obrisani).
- `npx tsc --noEmit`: ✅ pass.
- `npm run build`: ✅ pass (Next 14, next-pwa SW generisan).
- ESLint konfigurisan (`frontend/.eslintrc.json`, `next/core-web-vitals` preset).

---

### Korak 6.2 — Google PSE proxy UI [FRONTEND] — **BLOCKED**

Preskočeno jer `backend/app/api/v1/search.py` još ne postoji (ROADMAP 5.1, Stefan). `GlobalSearchBox` je ostavljen disabled sa tooltipom "Dostupno uskoro".

---

### Korak 6.3 — PWA [FRONTEND] — **DONE**

- `public/manifest.json` sa punom specifikacijom (start_url `/dashboard`, scope `/`, lang `sr-Latn`, tema `#0f172a`).
- `scripts/generate-icons.mjs` (sharp) generiše sve potrebne veličine (192/512/maskable + apple-touch + favicon 16/32) — reproduktabilno preko `npm run generate:icons`.
- `next-pwa` konfigurisan u `next.config.mjs`: register + skipWaiting + reloadOnOnline; disabled u dev-u. Runtime caching:
  - Google Fonts: CacheFirst.
  - `/_next/static/*` i `/icons/*`: CacheFirst.
  - `/api/v1/students/appointments*` i `/api/v1/notifications*`: NetworkFirst sa 3s timeout-om (offline arhiva ~24h, max 40 unosa).
  - Navigacija: NetworkFirst.
- `components/shared/offline-indicator.tsx` montiran u `AppShell` (banner na `navigator.onLine === false`).
- `components/notifications/push-subscription-toggle.tsx` dodat u `UserMenu` kao **disabled stub** sa tooltipom — aktivirati jednom kad backend `POST /api/v1/notifications/subscribe` + VAPID stigne.
- `app/layout.tsx` — kompletan PWA meta set (manifest, theme-color, apple-web-app, favicons, apple-touch-icon, viewport).

---

### Korak 6.4 — Chat WebSocket migracija [FRONTEND] — **BLOCKED**

`backend/app/api/v1/appointments.py` još nema `@router.websocket("/{id}/chat")` (ROADMAP 4.1, Stefan). `lib/ws/chat-socket.ts` je pripremljen prema `docs/websocket-schema.md` §5, ali `TicketChat` i dalje koristi polling fallback iz Faze 3. Aktivira se prebacivanjem `use-chat` na WS klijent jednom kada backend endpoint stigne.

---

### Korak 6.5 — NotificationStream go-live [FRONTEND] — **BLOCKED**

`backend/app/api/v1/notifications.py` ne postoji (ROADMAP 4.2, Stefan). `lib/ws/notification-socket.ts` i `notification-stream.tsx` su već napisani u Fazi 5; `use-notifications` trenutno koristi polling (30s). Aktivira se automatski kad backend WS endpoint stigne (connection status store `lib/stores/notification-ws-status.ts` već prati stanje).

---

### Korak 6.6 — E2E testovi [FRONTEND] — **PARTIAL**

Playwright scaffold je postavljen (`frontend/playwright.config.ts`, `frontend/e2e/fixtures/`, `frontend/e2e/tests/`, `.gitignore` ažuriran, `package.json` skripte: `test:e2e`, `test:e2e:ui`, `test:e2e:headed`). Projekti: `chromium` + `mobile-chrome` (Pixel 5). Retries 2 na CI.

**Implementirani specovi (prolaze protiv živog backend-a):**
- `smoke.spec.ts` — middleware redirecti, login/register/forgot-password rendering, PWA manifest (filesystem check).
- `auth.spec.ts` — validacija formi, pogrešni kredencijali, uspešan student login + logout.
- `student-search.spec.ts` — debounced professor search, filteri, reset.
- `professor-view.spec.ts` — FAQ iznad kalendara asercija na `/professor/[id]`.

**Deferovani specovi (čekaju backend):**
- `student-booking.spec.ts` → čeka `GET /appointments/{id}` (ROADMAP 3.6).
- `professor-approve.spec.ts` → čeka `GET/POST /professors/requests` (ROADMAP 3.7).
- `admin-bulk-import.spec.ts` → čeka `POST /admin/users/bulk-import` (ROADMAP 4.7).
- `strike-system.spec.ts` → čeka `GET /students/appointments` sa strike fieldovima + admin strikes endpoint.

**E2E seed:** za sada se testovi oslanjaju na `scripts/seed_db.py` (credentials u `frontend/e2e/fixtures/auth.ts`). Dedicated `scripts/seed_e2e.py` treba da pokrije: (a) tri test user-a po roli sa fiksnim lozinkama, (b) minimalno 3 profesora sa FAQ entrijima, (c) slot < 24h za strike test, (d) CSV sa 5 validnih + 2 duplikata + 1 invalid domen za bulk-import test.

---

### Korak 6.7 — Finalni polish [FRONTEND] — **DONE**

- Svaka stranica ima: Skeleton/Spinner tokom load-a, `EmptyState` za praznu listu, error toast + retry handling u `lib/api.ts` interceptoru.
- A11y: sva dugmad imaju accessible ime (lucide ikone praćene `aria-label` ili labelom), forme koriste `<Label>` iz shadcn-a, dialozi i dropdown-ovi zatvaraju Escape-om (shadcn default), focus trap u modalima.
- Mobile (375px): sidebar kolapsira u `Sheet`, search i my-appointments rade, FullCalendar prelazi u list view (breakpoint prop).
- Performance: `dynamic()` za FullCalendar i WS komponente, `next/image` za logo/avatare, bez premature `React.memo`.
- SEO: `app/page.tsx` redirect na `/login` (middleware odlučuje za authenticated), `app/(auth)/login/layout.tsx` + `register/layout.tsx` imaju metadata sa title/description/robots.
- Dokumentacija: `frontend/README.md` (setup, env, skripte, PWA, E2E, produkcijski checklist); ovaj `ROADMAP.md` ažuriran u sekcijama 1.6/1.7/1.8/1.9/1.10.

---

## Finalni pregled — raspodela po developerima

### Stefan (backend) — ~16 dana fokus

1. **Faza 2:** 2.1 (bugovi, 0.5d)
2. **Faza 3:** 3.1 (profesor portal, 2.5d), 3.2 (documents, 1.5d), 3.3 (appointment detail, 2d), 3.8 (recurring slots, 1d)
3. **Faza 4:** 4.1 (chat WS, 1.5d), 4.2 (notifications, 1.5d), 4.3 (admin users, 2d), 4.4 (impersonation, 1d), 4.5 (strikes+broadcast, 1d), 4.6 (reminders, 1d)
4. **Faza 5:** 5.1 (PSE, 0.5d), 5.4 (testovi, 1d)

### Filip (frontend / project lead) — ~17 dana fokus

1. **Faza 2:** 2.2 (layout shell, 1.5d), 2.3 (api moduli + hooks + tipovi, 1d)
2. **Faza 3:** 3.4 (forgot+dashboard+my-appointments, 1.5d), 3.5 (search + professor + booking, 3.5d), 3.6 (appointment detail + chat UI, 2d), 3.7 (professor dashboard + settings, 3d)
3. **Faza 4:** 4.7 (admin panel, 3.5d), 4.8 (documents + notifications, 1.5d)
4. **Faza 5:** 5.1 (PSE UI, 0.25d), 5.2 (PWA, 1.5d), 5.3 (infra, 1.5d)

### Sinhronizacija

- **Pre Faze 3:** Filip i Stefan dogovaraju API kontrakt (Pydantic šeme + TypeScript tipovi) u jednom PR-u. Šeme u `backend/app/schemas/` i tipovi u `frontend/types/` moraju se uparivati red za red.
- **Pre Faze 4:** WebSocket šema poruka (chat message JSON, notification JSON) — napisati u `docs/websocket-schema.md`.
- **Daily sync (5 min):** šta je merged, šta blokira.

---

## Pravila kojih se držati (iz CLAUDE.md)

- Sve rute `async def`, ORM only, UUID PK, Pydantic V2, bez Keycloak-a, bez localStorage.
- Svaki PR mora proći: `ReadLints` → build → (kad bude) pytest + playwright.
- Commit format: `feat:`, `fix:`, `chore:`, `docs:`.
- PR target uvek `dev`, nikad `main` direktno.
- Kod `[FULLSTACK]` task-ova dogovori kontrakt **pre** implementacije.

---

*Ažurirati ovaj fajl u svakom PR-u koji menja scope ili trajanje. Procene su realne za iskusan tim; za solo rad dodati ~30%.*
