# HANDOFF2.md — Druga primopredaja razvoja
## Studentska Platforma — FON & ETF
**Datum:** April 2026
**Od:** Filip
**Za:** Stefan
**Prethodni dokument:** `HANDOFF.md` (Faza 0 → Stefan, Faza 1)

---

## Gde smo stali

Frontend je **u potpunosti završen** — sve stranice, komponente, API klijenti, TanStack Query hookovi, TypeScript tipovi, Zustand store-ovi, WebSocket klijenti, PWA (manifest + service worker + offline cache), i E2E Playwright scaffold. Sve što frontend može da uradi bez backend-a — radi. Sve što čeka backend — čeka te tebe.

Sve odluke koje se tiču WebSocket-a, impersonation JWT claimova, i notification tipova su zakucane u **`docs/websocket-schema.md`** (~700 linija). Taj dokument je autoritativan ugovor između frontend-a i backend-a. **Pročitaj ga celog pre nego što počneš da pišeš chat WS ili notifications WS endpointe** — frontend je već usklađen sa tim ugovorom, ti samo implementiraš server stranu.

### Šta radi (u live browser-u):

- Docker Compose sa svih 9 servisa (postgres, redis, minio, minio-init, nginx, backend, celery-worker, celery-beat, **frontend**)
- Nginx reverse proxy — jedan URL `http://localhost` serverira i frontend i `/api/*` rute ka backend-u + WebSocket upgrade
- Next.js 14 App Router + Tailwind + shadcn/ui — production build, standalone output u Docker-u
- Svih 19 ruta imaju kompletan UI (9 povezano na live backend endpointe, 10 prikazuje graceful "backend endpoint nije live" placeholdere)
- JWT auth sistem — login, register, logout, refresh, forgot/reset password — **E2E funkcionalni**
- RBAC guard (`<ProtectedPage allowedRoles={[...]} />`) blokira pristup tuđim rutama
- Student journey je demo-able: login → search → profesor profil (sa FAQ iznad kalendara) → klik na slot → request forma → submit → redirect na detail → otvori my-appointments → otkaži (sa <24h strike warning-om)
- PWA: manifest, service worker, offline indicator, runtime caching za `/my-appointments` i `/notifications`

### Šta je UI-gotovo ali čeka backend (10/19 stranica):

| Stranica | Čeka endpoint |
|----------|---------------|
| `/appointments/[id]` | `GET /appointments/{id}` + chat WS |
| `/document-requests` | `POST/GET /students/document-requests` |
| `/professor/dashboard` | `GET /professors/requests` + approve/reject/delegate |
| `/professor/settings` | `/professors/profile`, `/canned-responses`, `/faq`, `/crm` |
| `/admin` | `GET /admin/overview` |
| `/admin/users` | `GET/POST/PUT /admin/users` + bulk-import |
| `/admin/document-requests` | `/admin/document-requests` approve/reject/complete |
| `/admin/strikes` | `GET /admin/strikes` + unblock |
| `/admin/broadcast` | `POST /admin/broadcast` + fanout Celery task |
| `/admin/audit-log` | `GET /admin/audit-log` |

Kad backend isporučiš bilo koji od tih endpointa — odgovarajući frontend `TODO: backend endpoint not yet implemented` placeholder automatski prelazi u 🟢 (frontend već ima `lib/api/*` wrapper-e + `useXxx` hookove + error handling).

### Poznati bug-ovi u postojećem kodu (pre nego što išta novo napišeš):

1. **`backend/app/tasks/waitlist_tasks.py:83`** — `timedelta(...)` bez importa. Treba dodati `timedelta` u postojeću liniju `from datetime import datetime, timezone`. *Trivijalno, jedan red.*
2. **`infra/docker-compose.yml` celery-beat** — command koristi `--scheduler django_celery_beat.schedulers:DatabaseScheduler` ali paket nije u `requirements.txt`. Zameni sa `celery.beat.PersistentScheduler` (default, bez Django overhead-a).
3. **`backend/app/main.py`** — obrisati zakomentarisane routere koji su već registrovani; ostaviti samo za buduće (`admin`, `appointments`, `search`, `notifications`).

**Popravi ta 3 pre nego što počneš Fazu 3.** (ROADMAP Korak 2.1, ~0.5 dana.)

---

## Kako da pokreneš projekat

### Prvi put (clean machine):

```bash
# 1. Kloniraj repo (pretpostavka: već imaš pristup)
git clone https://github.com/filipovicfilip222-alt/student-platform-app.git
cd student-platform-app

# 2. .env fajlovi — oba su obavezna, compose ih direktno čita
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. U backend/.env promeni OBAVEZNO:
#   SECRET_KEY=<generiši: openssl rand -hex 32>
#   REDIS_PASSWORD=<nešto tvoje, mora biti isto u REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND>
# Ostali defaulti su OK za lokal.

# 4. Build + start svih servisa (profil 'app' uključuje frontend, backend, celery-worker, celery-beat)
cd infra
docker compose --profile app up -d --build

# 5. Migracije (samo prvi put — idempotentno, može i ponovo)
docker exec studentska_backend alembic upgrade head

# 6. Seed korisnika (samo prvi put — skripta skipuje postojeće)
docker exec studentska_backend python /scripts/seed_db.py
```

### Svaki sledeći put:

```bash
cd infra
docker compose --profile app up -d
# Ako si menjao backend/ ili frontend/ kod i treba rebuild:
docker compose --profile app up -d --build backend celery-worker celery-beat
# ili samo frontend:
docker compose --profile app up -d --build frontend
```

### Rebuild frontend-a nakon izmene `NEXT_PUBLIC_*` varijabli

`NEXT_PUBLIC_*` se **bake-uju u build** (Next.js limit). Ako promeniš bilo koju u `frontend/.env`:

```bash
docker compose --profile app build --no-cache frontend
docker compose --profile app up -d frontend
```

### Provera da sve radi:

| URL | Očekivano |
|-----|-----------|
| `http://localhost` | Next.js login stranica (redirect sa `/` na `/login`) |
| `http://localhost/api/v1/health` | `{"status":"ok"}` |
| `http://localhost/api/v1/docs` | Swagger UI sa svim trenutnim endpointima |
| `http://localhost:9001` | MinIO konzola (`minioadmin` / `minioadmin`) |
| `http://localhost:3000` | (direktan pristup frontend-u, bypass nginx — za debug) |
| `http://localhost:8000/docs` | (direktan pristup backend-u — za debug) |

### Test login (Swagger ili kroz UI):

```json
POST /api/v1/auth/login
{
  "email": "profesor1@fon.bg.ac.rs",
  "password": "Seed@2024!"
}
```

Seed nalozi (svi imaju lozinku `Seed@2024!` ako nisi override-ovao):

| Email | Rola | Fakultet |
|-------|------|----------|
| `sluzba@fon.bg.ac.rs` | ADMIN | FON |
| `sluzba@etf.bg.ac.rs` | ADMIN | ETF |
| `profesor1@fon.bg.ac.rs` | PROFESOR | FON (Milovan Petrović) |
| `profesor2@fon.bg.ac.rs` | PROFESOR | FON (Dragana Nikolić) |
| `profesor1@etf.bg.ac.rs` | PROFESOR | ETF (Aleksandar Jovanović) |
| `asistent1@fon.bg.ac.rs` | ASISTENT | FON |

Za studenta — registruj preko `/register` sa bilo kojim `*@student.fon.bg.ac.rs` ili `*@student.etf.bg.ac.rs` email-om.

### Logovi / debug:

```bash
# Backend logovi
docker logs -f studentska_backend

# Celery worker
docker logs -f studentska_celery_worker

# Celery beat (periodic taskovi)
docker logs -f studentska_celery_beat

# Frontend (Next.js standalone output)
docker logs -f studentska_frontend

# Nginx access log
docker exec studentska_nginx tail -f /var/log/nginx/access.log
```

### Ulazak u kontejner:

```bash
# Backend python shell
docker exec -it studentska_backend python

# Postgres psql
docker exec -it studentska_postgres psql -U studentska -d studentska_platforma

# Redis CLI
docker exec -it studentska_redis redis-cli -a <REDIS_PASSWORD iz .env>
```

---

## Tvoj zadatak — Backend Faza 3 + 4

Sve se nalazi detaljno u `docs/ROADMAP.md` (DEO 3 — PLAN FAZA, koraci 2.1 do 4.6). Ovde je kratki prioritetni red + referentni pointeri.

### Pre svega — ROADMAP Korak 2.1 — bug fixes [~0.5 dana]

Već gore nabrojano. Samo da ne zaboraviš.

### Red rada (strogo po prioritetima iz ROADMAP 2.5):

```
1. Korak 2.1  → bug fixes (0.5d)                    — pre svega
2. Korak 3.1  → professor portal endpointi (2.5d)   — odblokira /professor/dashboard + settings
3. Korak 3.2  → document requests oba toka (1.5d)   — odblokira /document-requests (student + admin)
4. Korak 3.3  → appointment detail + files (2d)     — odblokira /appointments/[id] + file upload
5. Korak 3.8  → recurring slots ekspanzija (1d)     — odblokira "svakog utorka 10h × 8 nedelja" u settings-u
6. Korak 4.1  → chat WebSocket (1.5d)               — odblokira live chat u /appointments/[id]
7. Korak 4.2  → notifications REST + WS (1.5d)      — odblokira bell counter + live push
8. Korak 4.3  → admin users CRUD + bulk (2d)        — odblokira /admin/users
9. Korak 4.4  → impersonation + audit log (1d)      — odblokira Impersonate dugme + /admin/audit-log
10. Korak 4.5 → admin strikes + broadcast (1d)      — odblokira /admin/strikes + /admin/broadcast
11. Korak 4.6 → reminder Celery beat tasks (1d)     — PRD §5.2 email reminderi
```

**Ukupno:** ~16 dana fokusa.

### Svaki korak — work pattern:

1. Pročitaj pripadajuću sekciju `ROADMAP.md`.
2. Pogledaj frontend TypeScript tipove koji definišu očekivanu response shape — oni su **ugovor** (Pydantic šeme moraju tačno da ih prate):
   - `frontend/types/professor.ts`, `appointment.ts`, `admin.ts`, `document-request.ts`, `notification.ts`, `chat.ts`, `ws.ts`
   - Primer: ako radiš `GET /admin/users`, otvori `frontend/types/admin.ts::AdminUserResponse` — to je tačna shape koju mora da vrati tvoja Pydantic šema.
3. Pogledaj frontend API wrapper — on ti kaže URL + HTTP metod + query params:
   - `frontend/lib/api/admin.ts`, `professors.ts`, `appointments.ts`, `document-requests.ts`, `notifications.ts`, `students.ts`
4. Implementiraj servis → šemu → router.
5. Testiraj kroz Swagger (`http://localhost/api/v1/docs`).
6. Testiraj kroz UI (login u browser-u → idi na odgovarajuću stranicu → placeholder treba da pređe u pravi UI).
7. Open PR targeting `dev` branch.

### Specijalno — ROADMAP 4.1 (Chat WS) i 4.2 (Notifications WS):

**Pročitaj `docs/websocket-schema.md` CEO dokument pre ijednog reda koda.** Tamo je:

- Handshake format (§2.1 — `token` query param, jer browseri ne mogu da šalju Authorization header na WS)
- Close codes tabela (§2.3 — 4401 unauthorized, 4403 forbidden, 4404 not found, 4409 duplicate session, 4429 rate limited, 4430 chat closed-24h)
- Envelope format (§3 — svi WS message-i su `{ id, type, ts, payload }`)
- Eventi za notifications (§4 — 16 tipova: `notification.created`, `broadcast.received`, itd.)
- Eventi za chat (§5 — `chat.message.created`, `chat.closed`)
- Impersonation JWT format (§6 — `imp`, `imp_email`, `imp_name` claimovi; 30 min TTL; **nema refresh-a**)
- Heartbeat (§7.1 — `system.ping`/`system.pong` svakih 30s)
- Reconnect logika (§7.2 — exponential backoff 1→30s, **NE** reconnect na 4401/4403/4404/4430)
- Gotovi TypeScript tipovi (§8 — frontend je već sve iskopirao iz ovog paragrafa, ti pravi Pydantic verzije)

Frontend `lib/ws/notification-socket.ts` je već napisan prema ovom ugovoru i radi. Čim tvoj WS endpoint stigne — frontend se sam prebacuje sa REST polling-a (30s) na live WS. `lib/stores/notification-ws-status.ts` prati connection state.

### Specijalno — ROADMAP 4.3 (Admin users CRUD):

Obrati pažnju na:

- **Email whitelist** — staff domeni (`fon.bg.ac.rs`, `etf.bg.ac.rs`) za PROFESOR/ASISTENT/ADMIN; student domeni (`student.fon.bg.ac.rs`, `student.etf.bg.ac.rs`) za STUDENT. Lista je u `backend/.env::ALLOWED_STUDENT_DOMAINS` + `ALLOWED_STAFF_DOMAINS`.
- **Bulk import CSV** — frontend očekuje `preview` → `confirm` dvostepen flow (vidi `frontend/components/admin/bulk-import-dialog.tsx`). Response za preview je `BulkImportPreview { valid_rows, invalid_rows, duplicates, total }`; response za confirm je `BulkImportResult { created, skipped, failed }`.
- **Deactivate = soft delete** — nikad nemoj da brišeš User red, samo `is_active = False`.

### Specijalno — ROADMAP 4.4 (Impersonation):

Ugovor je **fiksan** u `docs/websocket-schema.md §6`. Frontend već pretpostavlja:

```json
POST /api/v1/admin/impersonate/{user_id}
→ 200 OK
{
  "access_token": "<JWT sa imp=admin_id, imp_email=..., imp_name=..., sub=target_id>",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": { UserResponse target-a },
  "impersonator": { id, email, first_name, last_name },
  "imp_expires_at": "2026-05-01T11:30:00Z"
}
```

```json
POST /api/v1/admin/impersonate/end
→ 200 OK
{
  "access_token": "<JWT admin-a>",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { UserResponse admin-a }
}
```

**Nema refresh endpoint-a za impersonation token.** 30 min TTL, zatim `401` → frontend ponovo pokazuje login / admin re-impersonira.

**Audit log obavezno** — svaki start/end generiše `AuditLog` zapis sa `action="IMPERSONATE_START"` ili `"IMPERSONATE_END"` + IP + `impersonated_user_id`.

---

## Frontend TypeScript tipovi = tvoj API ugovor

Umesto da Pydantic šeme dizajniraš iz glave, otvori jedan od ovih fajlova i kopiraj strukturu u Python:

```bash
frontend/types/admin.ts              # AdminUserCreate, AdminOverviewMetrics, StrikeRow, BroadcastRequest...
frontend/types/appointment.ts        # AppointmentResponse, AppointmentCreateRequest, ChatMessageResponse...
frontend/types/document-request.ts   # DocumentRequestCreate/Response/Approve/Reject
frontend/types/notification.ts       # NotificationType (16 vrednosti), NotificationResponse, TOAST_NOTIFICATION_TYPES
frontend/types/chat.ts               # WsChatMessage, ChatSender
frontend/types/professor.ts          # ProfessorProfileResponse, CannedResponse, CrmNote, FaqResponse
frontend/types/ws.ts                 # WsEnvelope, WS_CLOSE_CODES, svi event tipovi
```

**Primer preslikavanja** — `frontend/types/admin.ts::AdminUserCreate` → `backend/app/schemas/admin.py::AdminUserCreateRequest`:

```typescript
// frontend/types/admin.ts
export interface AdminUserCreate {
  email: string
  password: string
  first_name: string
  last_name: string
  role: Role         // "STUDENT" | "ASISTENT" | "PROFESOR" | "ADMIN"
  faculty: Faculty   // "FON" | "ETF"
}
```

```python
# backend/app/schemas/admin.py (ti pišeš)
from pydantic import BaseModel, EmailStr
from app.models.enums import UserRole, Faculty

class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: UserRole
    faculty: Faculty
```

---

## Git workflow

```bash
# Feature grana po ROADMAP koraku
git checkout -b feature/B-3.1-professor-portal
git checkout -b feature/B-3.2-document-requests
git checkout -b feature/B-4.1-chat-websocket
# itd.

# Commit format (kao i do sada)
git commit -m "feat: professor portal GET/PUT profile + requests inbox"
git commit -m "fix: waitlist_tasks missing timedelta import"
git commit -m "chore: swap celery-beat scheduler to PersistentScheduler"

# Push + PR prema dev
git push origin feature/B-3.1-professor-portal
# GitHub → New Pull Request → base: dev
```

**Ne push-uj direktno na `main` ili `dev`.** Filip review-uje svaki PR pre merge-a.

---

## Referentni fajlovi (sve što ti treba za kontekst)

| Fajl | Zašto |
|------|-------|
| `CLAUDE.md` | **Čitaj pre svakog feature-a.** Pravila koda, konvencije, zabranjena ponašanja (sekcija 11) |
| `docs/ROADMAP.md` | Snimak stanja + plan faza. DEO 3 sadrži sve tvoje korake sa fajlovima, endpointima, acceptance kriterijumima, zavisnostima, procenama |
| `docs/websocket-schema.md` | **Autoritativan ugovor** za WebSocket + impersonation + notification tipove. Sve odluke u Fazi 4 ovde žive |
| `docs/PRD_Studentska_Platforma.md` | Poslovni zahtevi i UX pravila (24h strike pravilo, 3 poena = 14d blok, FAQ iznad kalendara, max 20 msg po chat-u, 24h auto-close chat-a) |
| `docs/copilot_plan_prompt.md` | Detaljna DB šema, API spec, sprint plan (starija verzija; ROADMAP je merodavan za trenutno stanje) |
| `docs/FRONTEND_STRUKTURA.md` | Kako je frontend organizovan — pomaže kad debug-uješ zašto neki UI poziv radi ono što radi |
| `CURRENT_STATE.md` | Fotografija codebase-a pre ove predaje (za reference, nije strogo ažurno) |
| `HANDOFF.md` | Originalna predaja (Faza 0 → Faza 1) — radi konteksta |
| `http://localhost/api/v1/docs` | Swagger UI — tu testiraš endpointe |

---

## Cursor workflow (kako koristiti AI)

```
# U Cursor chat-u, uvek taguj:
@CLAUDE.md @docs/ROADMAP.md @HANDOFF2.md

# Primer za Korak 3.1:
"Implementiraj ROADMAP Korak 3.1 — professor portal endpointi.
Prati sva pravila iz CLAUDE.md. Pydantic šeme moraju da se poklapaju
sa TypeScript tipovima u frontend/types/professor.ts — proveri red po red."

# Primer za Korak 4.2 (WS notifications):
"Implementiraj ROADMAP Korak 4.2 — notifications REST + WS stream.
Ugovor je u docs/websocket-schema.md §4 + §7. Frontend native-WS
klijent (frontend/lib/ws/notification-socket.ts) već postoji i
poštuje taj ugovor — ne menjaj ga, samo backend mora da mu se
prilagodi."
```

**Kad Cursor predloži nešto što nije u skladu sa CLAUDE.md** (npr. localStorage, raw SQL, Keycloak, socket.io, sync endpoint) — reci mu eksplicitno: *"Pročitaj CLAUDE.md sekcija 11 — zabranjena ponašanja"*. Ponoviće fix prema tvojim pravilima.

---

## Pre svakog PR-a — Definition of Done

```
[ ] docker compose --profile app up -d --build prolazi bez greške
[ ] docker exec studentska_backend alembic upgrade head prolazi (ako si menjao modele)
[ ] Novi endpoint vidljiv u Swagger-u (http://localhost/api/v1/docs)
[ ] Ručno pozvao endpoint iz Swagger-a — vraća tačnu shape (uporedi sa frontend/types/*.ts)
[ ] Frontend placeholder prelazi u pravi UI (login u browser-u → idi na pripadajuću stranicu)
[ ] pytest (kad budeš pisao testove) prolazi
[ ] Commit poruke po formatu feat/fix/chore/docs
[ ] PR ima opis šta je urađeno + checklist acceptance kriterijuma iz ROADMAP koraka
[ ] Ne radiš git push --force na dev/main
```

---

## Kad nešto iskrsne

| Problem | Prvo proveri |
|---------|--------------|
| Frontend loguje "Network Error" | `docker logs studentska_backend` — da li je startovao bez migracije? |
| 401 na svakom pozivu | `backend/.env::SECRET_KEY` — da li se poklapa sa onim iz prethodne sesije (JWT-i iz starog key-a neće da se dekodiraju) |
| Celery task ne izvršava se | `docker logs studentska_celery_worker` — da li worker vidi task? Da li je `celery_app.autodiscover_tasks([...])` updated? |
| Celery beat pada pri startu | Scheduler config — vidi bug #2 gore |
| WebSocket odbija konekciju | Proveri nginx.conf — `/api/v1/notifications/stream` + `/api/v1/appointments/{id}/chat` moraju imati `proxy_set_header Upgrade $http_upgrade` i `Connection "upgrade"` (već podešeno u trenutnoj konfiguraciji, ali ako menjaš nginx config pazi da ne obrišeš) |
| MinIO upload pada | `docker logs studentska_minio_init` — da li su 4 buceka (appointment-files, professor-avatars, bulk-imports, document-requests) kreirana? |
| Frontend ne vidi nove NEXT_PUBLIC_ varijable | Obavezan `docker compose build --no-cache frontend` — Next.js ih bake-uje pri build-u |

---

## Pitanja?

Discord / WhatsApp. Daily sync 5 min — šta merge-ovano, šta blokira.

Ako nešto u ROADMAP-u ili `websocket-schema.md` ne razumeš — **pitaj pre nego što napišeš kod**. Frontend je zaključan na te ugovore, pa ako ti backend odstupi, sve moramo da refaktorišemo. Lakše je menjati plan nego kod.

---

*Sve je spremno. Frontend te čeka. Srećno!*
