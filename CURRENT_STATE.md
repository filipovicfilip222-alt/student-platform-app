# CURRENT_STATE.md — Studentska Platforma
## Presek stanja projekta za onboarding AI asistenta

> **Datum:** April 2026  
> **Projekat:** Platforma za zakazivanje konzultacija između studenata i profesora FON-a i ETF-a  
> **Referentni dokumenti:** `CLAUDE.md` (pravila i konvencije), `docs/copilot_plan_prompt.md` (pun plan), `docs/PRD_Studentska_Platforma.md` (poslovni zahtevi), `docs/Arhitektura_i_Tehnoloski_Stek.md` (tehničke odluke)

---

## 1. STRUKTURA PROJEKTA (Monorepo)

```
Student_Platform_App/
├── CLAUDE.md                         ← jedini source of truth za AI asistente
├── CURRENT_STATE.md                  ← ovaj fajl
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── .env.example
│   ├── alembic/
│   │   ├── env.py                    ← async alembic setup
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 20260423_0001_initial_schema.py  ← inicijalna migracija (sve tabele)
│   └── app/
│       ├── main.py                   ← FastAPI app, CORS, router registracija
│       ├── celery_app.py             ← Celery instanca
│       ├── core/
│       │   ├── config.py             ← pydantic-settings (sve env varijable)
│       │   ├── database.py           ← async engine + AsyncSessionLocal + get_db()
│       │   ├── security.py           ← JWT helpers, bcrypt, email validacija, Redis Lua lock
│       │   ├── dependencies.py       ← get_current_user, require_role(), typed shortcuts
│       │   └── email.py              ← email dispatch helpers (pozivaju Celery task)
│       ├── models/
│       │   ├── base.py               ← DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin
│       │   ├── enums.py              ← svi Python enum tipovi
│       │   ├── user.py
│       │   ├── professor.py
│       │   ├── subject.py            ← + subject_assistants (M2M Table)
│       │   ├── availability_slot.py  ← AvailabilitySlot + BlackoutDate
│       │   ├── appointment.py        ← Appointment + AppointmentParticipant + Waitlist
│       │   ├── file.py
│       │   ├── chat.py               ← TicketChatMessage
│       │   ├── crm_note.py
│       │   ├── strike.py             ← StrikeRecord + StudentBlock
│       │   ├── faq.py
│       │   ├── notification.py
│       │   ├── audit_log.py
│       │   ├── canned_response.py
│       │   ├── document_request.py
│       │   └── password_reset_token.py
│       ├── schemas/
│       │   └── auth.py               ← RegisterRequest, LoginRequest, TokenResponse, UserResponse, itd.
│       ├── services/
│       │   └── auth_service.py       ← register, login, refresh, logout, forgot/reset password
│       ├── tasks/
│       │   └── email_tasks.py        ← Celery task za slanje emailova (smtplib + STARTTLS)
│       └── api/
│           └── v1/
│               └── auth.py           ← svi auth endpointi
│
├── frontend/
│   ├── Dockerfile                    ← 3-stage build (deps → builder → runner)
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs               ← output: standalone, image domains za MinIO
│   ├── tailwind.config.ts            ← shadcn/ui CSS variable color sistem
│   ├── postcss.config.mjs
│   ├── middleware.ts                 ← protected routes (čita refresh_token cookie)
│   ├── .env.example
│   ├── app/
│   │   ├── layout.tsx                ← root layout, Inter font, Providers wrapper
│   │   ├── globals.css               ← Tailwind + CSS varijable (light/dark tema)
│   │   ├── providers.tsx             ← QueryClientProvider + SessionRestorer (auto-refresh)
│   │   ├── (auth)/
│   │   │   ├── layout.tsx
│   │   │   ├── login/page.tsx        ← PUNA IMPLEMENTACIJA (react-hook-form + zod + shadcn)
│   │   │   ├── register/page.tsx     ← PUNA IMPLEMENTACIJA (domain validacija na frontendu)
│   │   │   └── forgot-password/page.tsx  ← STUB
│   │   ├── (student)/
│   │   │   ├── layout.tsx
│   │   │   ├── dashboard/page.tsx        ← STUB
│   │   │   ├── search/page.tsx           ← STUB
│   │   │   ├── professor/[id]/page.tsx   ← STUB
│   │   │   ├── appointments/[id]/page.tsx ← STUB
│   │   │   ├── my-appointments/page.tsx  ← STUB
│   │   │   └── document-requests/page.tsx ← STUB
│   │   ├── (professor)/
│   │   │   ├── layout.tsx
│   │   │   ├── professor/dashboard/page.tsx ← STUB
│   │   │   └── professor/settings/page.tsx  ← STUB
│   │   └── (admin)/
│   │       ├── layout.tsx
│   │       ├── admin/page.tsx               ← STUB
│   │       ├── admin/users/page.tsx         ← STUB
│   │       ├── admin/document-requests/page.tsx ← STUB
│   │       ├── admin/strikes/page.tsx       ← STUB
│   │       ├── admin/broadcast/page.tsx     ← STUB
│   │       └── admin/audit-log/page.tsx     ← STUB
│   ├── components/
│   │   └── ui/
│   │       ├── button.tsx            ← shadcn/ui (class-variance-authority)
│   │       ├── card.tsx              ← shadcn/ui
│   │       ├── form.tsx              ← shadcn/ui (react-hook-form integration)
│   │       ├── input.tsx             ← shadcn/ui
│   │       └── label.tsx             ← shadcn/ui (@radix-ui/react-label)
│   ├── lib/
│   │   ├── utils.ts                  ← cn() helper (clsx + tailwind-merge)
│   │   ├── api.ts                    ← Axios instance + JWT interceptor + auto-refresh logika
│   │   ├── api/
│   │   │   └── auth.ts               ← authApi (register, login, refresh, logout, me, itd.)
│   │   └── stores/
│   │       └── auth.ts               ← Zustand store (user, accessToken, setAuth, clearAuth)
│   └── types/
│       └── auth.ts                   ← TypeScript tipovi usklađeni sa backend Pydantic šemama
│
├── infra/
│   ├── docker-compose.yml
│   ├── nginx/
│   │   └── nginx.conf                ← reverse proxy za FastAPI (:8000) i Next.js (:3000)
│   └── minio/
│       └── init-buckets.sh           ← kreira 4 bucketa pri startovanju
│
├── scripts/
│   ├── migrate.sh                    ← Alembic wrapper (upgrade/downgrade/revision/current)
│   └── seed_db.py                    ← seed korisnici iz PRD §1.2
│
└── docs/
    ├── CLAUDE.md
    ├── PRD_Studentska_Platforma.md
    ├── Arhitektura_i_Tehnoloski_Stek.md
    └── copilot_plan_prompt.md
```

---

## 2. IMPLEMENTIRANE FUNKCIONALNOSTI

### 2.1 Infrastruktura (Faza 0 — ✅ KOMPLETNO)

#### Docker Compose (`infra/docker-compose.yml`)
Servisi:
- **postgres:16-alpine** — healthcheck via `pg_isready`, persistent volume
- **redis:7-alpine** — `--appendonly yes --requirepass`, persistent volume
- **minio:latest** — API port 9000, konzola port 9001, persistent volume
- **minio-init** (`minio/mc`) — pokreće `init-buckets.sh` nakon što minio postane healthy
- **nginx:alpine** — reverse proxy, čita `nginx/nginx.conf`
- **backend** (FastAPI) — `profiles: [app]`, zavisi od postgres+redis healthcheck
- **frontend** (Next.js) — `profiles: [app]`, zavisi od backend
- **keycloak** — **zakomentarisan** (planiran za V2), konfiguracija je tu ali ne radi

#### MinIO bucketi (`infra/minio/init-buckets.sh`)
| Bucket | Pristup | Namena |
|--------|---------|--------|
| `appointment-files` | Private (presigned URL) | Fajlovi uz termine |
| `professor-avatars` | **Public (anonymous download)** | Profilne slike |
| `bulk-imports` | Private | CSV fajlovi za bulk import studenata |
| `document-requests` | Private | Dokumenti studentske službe |

#### Nginx (`infra/nginx/nginx.conf`)
- `/api/*` → `backend:8000` (FastAPI)
- `/docs`, `/openapi.json` → FastAPI Swagger
- `/` → `frontend:3000` (Next.js)
- WebSocket upgrade za `/api/v1/appointments/` i `/api/v1/notifications/stream` (timeout 3600s)
- HMR (`/_next/webpack-hmr`) za development
- Security headeri: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

---

### 2.2 Backend — FastAPI Skeleton (Faza 0 — ✅ KOMPLETNO)

#### `app/main.py`
- FastAPI app sa `ORJSONResponse` kao default
- CORS middleware (allowed origin: `FRONTEND_URL` iz env)
- **Registrovan router:** `auth.router` na `/api/v1/auth`
- Health check endpoint: `GET /api/v1/health` → `{"status": "ok", ...}`
- Ostali routeri su zakomentarisani, čekaju implementaciju

#### `app/core/config.py` — pydantic-settings
Sve env varijable sa defaults:
- Database: `DATABASE_URL`, `POSTGRES_*`
- Redis: `REDIS_URL`, `REDIS_PASSWORD`
- JWT: `SECRET_KEY`, `ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=60`, `REFRESH_TOKEN_EXPIRE_DAYS=7`
- MinIO: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, 4x bucket nazivi, `MINIO_SECURE`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME`
- Google PSE: `GOOGLE_PSE_API_KEY`, `GOOGLE_PSE_CX`
- Domeni: `ALLOWED_STUDENT_DOMAINS`, `ALLOWED_STAFF_DOMAINS` (comma-separated, parsirani u `student_domains` / `staff_domains` properties)
- App: `APP_ENV`, `DEBUG`, `LOG_LEVEL`, `FRONTEND_URL`
- Celery: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`

#### `app/core/database.py`
- `create_async_engine` sa `pool_pre_ping=True`, `pool_size=10`, `max_overflow=20`
- `AsyncSessionLocal` via `async_sessionmaker`
- `get_db()` — async generator sa auto-commit i rollback on exception

#### `app/core/security.py`
- `hash_password()` / `verify_password()` — bcrypt, **12 rounds** (`passlib`)
- `create_access_token()` / `create_refresh_token()` — JWT (`python-jose`), type claim za razlikovanje
- `decode_access_token()` / `decode_refresh_token()` — validacija type claim
- `validate_email_domain()` / `is_student_email()` / `is_staff_email()` — whitelist domen validacija
- `acquire_slot_lock()` / `release_slot_lock()` — **atomičan Redis Lua skript** (pessimistic lock, TTL 30s)

#### `app/core/dependencies.py`
- `get_redis()` — lazy singleton pool (`aioredis.from_url`)
- `get_current_user()` — HTTPBearer → JWT decode → DB lookup
- `require_role(*roles)` — dependency factory za RBAC
- **Typed shortcuts:** `CurrentUser`, `CurrentAdmin`, `CurrentProfesor`, `CurrentProfesorOrAsistent`, `CurrentStudent`, `RedisClient`, `DBSession`

---

### 2.3 Baza Podataka — SQLAlchemy Modeli (Faza 0 — ✅ KOMPLETNO)

#### Enum tipovi (9 PostgreSQL native ENUM tipova)
| Python Enum | PostgreSQL tip | Vrednosti |
|-------------|---------------|-----------|
| `UserRole` | `userrole` | STUDENT, ASISTENT, PROFESOR, ADMIN |
| `Faculty` | `faculty` | FON, ETF |
| `ConsultationType` | `consultationtype` | UZIVO, ONLINE |
| `AppointmentStatus` | `appointmentstatus` | PENDING, APPROVED, REJECTED, CANCELLED, COMPLETED |
| `TopicCategory` | `topiccategory` | SEMINARSKI, PREDAVANJA, ISPIT, PROJEKAT, OSTALO |
| `ParticipantStatus` | `participantstatus` | PENDING, CONFIRMED, DECLINED |
| `StrikeReason` | `strikereason` | LATE_CANCEL, NO_SHOW |
| `DocumentType` | `documenttype` | POTVRDA_STATUSA, UVERENJE_ISPITI, UVERENJE_PROSEK, PREPIS_OCENA, POTVRDA_SKOLARINE, OSTALO |
| `DocumentStatus` | `documentstatus` | PENDING, APPROVED, REJECTED, COMPLETED |

#### Base klase (`app/models/base.py`)
- `Base` — SQLAlchemy `DeclarativeBase`
- `UUIDPrimaryKeyMixin` — UUID PK sa `server_default=gen_random_uuid()`
- `TimestampMixin` — `created_at`, `updated_at` (TIMESTAMPTZ sa `func.now()`)

#### Tabele (20 tabela, sve u zasebnim fajlovima)

| Model fajl | Tabela(e) | Ključne napomene |
|-----------|----------|-----------------|
| `user.py` | `users` | email UNIQUE INDEX, role ENUM, faculty ENUM, bcrypt hashed_password |
| `professor.py` | `professors` | FK→users (UNIQUE), `areas_of_interest TEXT[]`, buffer_minutes, auto_approve_* |
| `subject.py` | `subjects` + `subject_assistants` | `subject_assistants` je M2M association Table |
| `availability_slot.py` | `availability_slots` + `blackout_dates` | `recurring_rule JSONB`, valid_from/until DATE |
| `appointment.py` | `appointments` + `appointment_participants` + `waitlist` | `waitlist` ima UNIQUE(slot_id, student_id) |
| `file.py` | `files` | `minio_object_key TEXT`, mime_type, file_size_bytes |
| `chat.py` | `ticket_chat_messages` | FK→appointments (CASCADE) |
| `crm_note.py` | `crm_notes` | FK→professors + users |
| `strike.py` | `strike_records` + `student_blocks` | points INTEGER, StrikeReason ENUM |
| `faq.py` | `faq_items` | sort_order INTEGER |
| `notification.py` | `notifications` | `data JSONB`, is_read BOOLEAN |
| `audit_log.py` | `audit_log` | `ip_address INET` (PostgreSQL native tip) |
| `canned_response.py` | `canned_responses` | FK→professors |
| `document_request.py` | `document_requests` | DocumentType + DocumentStatus ENUM, pickup_date DATE |
| `password_reset_token.py` | `password_reset_tokens` | `token_hash` (SHA-256), `expires_at`, `used_at` |

#### Alembic
- `alembic.ini` — `timezone = Europe/Belgrade`, script_location = alembic
- `alembic/env.py` — **async setup** (`asyncio.run`), importuje sve modele, čita DATABASE_URL iz settings
- `alembic/versions/20260423_0001_initial_schema.py` — kreira sve enum tipove (`op.execute("CREATE TYPE ...")`), zatim sve 20 tabela u ispravnom redosledu zavisnosti (FK). `downgrade()` briše sve u obrnutom redosledu.

---

### 2.4 Auth Sistem (Faza 1 — ✅ KOMPLETNO)

#### Pydantic šeme (`app/schemas/auth.py`)
- `RegisterRequest` — email, password (min 8), first_name, last_name; strip whitespace validator
- `LoginRequest` — email, password
- `ForgotPasswordRequest` — email
- `ResetPasswordRequest` — token, new_password (min 8)
- `ChangePasswordRequest` — current_password, new_password
- `UserResponse` — sve kolone **bez `hashed_password`**, `model_config = {"from_attributes": True}`
- `TokenResponse` — access_token + ugneždeni `UserResponse` objekat
- `MessageResponse` — message: str

#### Auth servis (`app/services/auth_service.py`)

| Funkcija | Opis |
|----------|------|
| `register(db, data)` | Validira domen → blokira staff email sa 403 → unique check → kreira User sa `role=STUDENT`, `faculty` inferiran iz email domene → `db.flush()` |
| `login(db, redis, email, password)` | verify_password → kreira access+refresh JWT → `redis.setex("refresh:{user_id}", 7d, token)` → vraća (user, access_token, refresh_token) |
| `refresh_access_token(db, redis, token)` | decode JWT → **Redis match check** (revocation) → vraća (user, novi_access_token) |
| `logout(redis, user_id)` | `redis.delete("refresh:{user_id}")` |
| `forgot_password(db, email)` | `secrets.token_urlsafe(32)` → SHA-256 hash → DB (`password_reset_tokens`) → Celery dispatch → uvek 200 (anti-enumeration) |
| `reset_password(db, token, new_password)` | SHA-256 hash → DB lookup → `prt.is_valid` provera → `used_at = now()` → novi bcrypt hash |

#### Auth router (`app/api/v1/auth.py`)

| Method | Endpoint | Auth | Opis |
|--------|----------|------|------|
| POST | `/api/v1/auth/register` | — | Samo studentski domeni; vraća `UserResponse` (201) |
| POST | `/api/v1/auth/login` | — | Vraća `TokenResponse`; postavlja `refresh_token` httpOnly cookie |
| POST | `/api/v1/auth/refresh` | httpOnly cookie | Čita cookie, validira Redis, vraća novi access token; "sliduje" cookie expiry |
| POST | `/api/v1/auth/logout` | Bearer | Redis delete + `response.delete_cookie()` |
| POST | `/api/v1/auth/forgot-password` | — | Uvek 200 OK |
| POST | `/api/v1/auth/reset-password` | — | Token važi 1h |
| GET | `/api/v1/auth/me` | Bearer | Vraća trenutnog korisnika |

#### Cookie konfiguracija
```python
key="refresh_token"
httponly=True
secure=True  # samo u non-development okruženjima
samesite="lax"
path="/api/v1/auth"  # ograničen path
max_age=7 * 24 * 3600
```

---

### 2.5 Email sistem (`app/core/email.py` + `app/tasks/email_tasks.py`)

#### Celery (`app/celery_app.py`)
- Broker: Redis (db 1), Backend: Redis (db 2)
- `task_acks_late=True`, `worker_prefetch_multiplier=1`
- Include: `["app.tasks.email_tasks"]`

#### `email_tasks.py` — Celery task `send_email_task`
- Synchronous `smtplib` + STARTTLS (bez async problema u workeru)
- Retry: 3x sa 60s razmakom na `SMTPException`
- `bind=True` za pristup `self.request.retries`

#### `core/email.py` — dispatch helpers
- `send_password_reset_email(to, token)` — HTML template sa reset URL
- `send_welcome_email(to, first_name)` — Welcome email
- `send_generic_notification_email(to, subject, title, body_html)` — generički layout
- Svi pozivaju `send_email_task.delay(...)` (late import da se izbegnu circular deps)

---

### 2.6 Seed skripta (`scripts/seed_db.py`)

Idempotentna skripta (skip ako korisnik već postoji). Kreira korisnike iz PRD §1.2:

| Email | Uloga | Fakultet | Profesor profil |
|-------|-------|----------|----------------|
| `sluzba@fon.bg.ac.rs` | ADMIN | FON | — |
| `sluzba@etf.bg.ac.rs` | ADMIN | ETF | — |
| `profesor1@fon.bg.ac.rs` | PROFESOR | FON | ✅ (dr Milovan Petrović, Katedra za IS, kancelarija 216) |
| `profesor2@fon.bg.ac.rs` | PROFESOR | FON | ✅ (dr Dragana Nikolić, Katedra za menadžment, kancelarija 305) |
| `profesor1@etf.bg.ac.rs` | PROFESOR | ETF | ✅ (prof. dr Aleksandar Jovanović, RTI katedra, kancelarija 54) |
| `asistent1@fon.bg.ac.rs` | ASISTENT | FON | — |

Default lozinka: `Seed@2024!` (override via `--password`)

---

### 2.7 Frontend Skeleton (Faza 0/1 — ✅ KOMPLETNO)

#### URL Mapa (Next.js App Router)
| URL | Route group | Fajl | Status |
|-----|------------|------|--------|
| `/login` | `(auth)` | `app/(auth)/login/page.tsx` | **PUNA IMPLEMENTACIJA** |
| `/register` | `(auth)` | `app/(auth)/register/page.tsx` | **PUNA IMPLEMENTACIJA** |
| `/forgot-password` | `(auth)` | `app/(auth)/forgot-password/page.tsx` | STUB |
| `/dashboard` | `(student)` | `app/(student)/dashboard/page.tsx` | STUB |
| `/search` | `(student)` | `app/(student)/search/page.tsx` | STUB |
| `/professor/[id]` | `(student)` | `app/(student)/professor/[id]/page.tsx` | STUB |
| `/appointments/[id]` | `(student)` | `app/(student)/appointments/[id]/page.tsx` | STUB |
| `/my-appointments` | `(student)` | `app/(student)/my-appointments/page.tsx` | STUB |
| `/document-requests` | `(student)` | `app/(student)/document-requests/page.tsx` | STUB |
| `/professor/dashboard` | `(professor)` | `app/(professor)/professor/dashboard/page.tsx` | STUB |
| `/professor/settings` | `(professor)` | `app/(professor)/professor/settings/page.tsx` | STUB |
| `/admin` | `(admin)` | `app/(admin)/admin/page.tsx` | STUB |
| `/admin/users` | `(admin)` | `app/(admin)/admin/users/page.tsx` | STUB |
| `/admin/document-requests` | `(admin)` | `app/(admin)/admin/document-requests/page.tsx` | STUB |
| `/admin/strikes` | `(admin)` | `app/(admin)/admin/strikes/page.tsx` | STUB |
| `/admin/broadcast` | `(admin)` | `app/(admin)/admin/broadcast/page.tsx` | STUB |
| `/admin/audit-log` | `(admin)` | `app/(admin)/admin/audit-log/page.tsx` | STUB |

#### `middleware.ts` — Protected Routes
- Čita `refresh_token` httpOnly cookie (jedini server-vidljiv auth signal)
- Bez cookiea na protected ruti → redirect na `/login?from=<original_path>`
- Sa cookieom na `/login` ili `/register` → redirect na `/dashboard`
- Matcher isključuje: `_next/static`, `_next/image`, `favicon.ico`, `manifest.json`, `icons/`

#### `lib/api.ts` — Axios
- Base URL: `NEXT_PUBLIC_API_URL ?? "http://localhost/api/v1"`
- `withCredentials: true` (šalje cookie automatski)
- **Request interceptor**: `useAuthStore.getState().accessToken` (Zustand vanilla API, radi van React-a)
- **Response interceptor**: Na 401 → pokušaj refresh → queue za konkurentne 401-ce (`pendingQueue`) → retry originalnog zahteva; neuspeh → `clearAuth()` + `window.location.href = "/login"`

#### `lib/stores/auth.ts` — Zustand
```typescript
interface AuthState {
  user: UserResponse | null
  accessToken: string | null  // NIKADA u localStorage
  isLoading: boolean
  setAuth(user, token): void
  setAccessToken(token): void
  clearAuth(): void
  setLoading(bool): void
}
```
Exportovani selektori: `selectUser`, `selectIsAuthenticated`, `selectIsLoading`, `selectRole`

#### `app/providers.tsx`
- `QueryClientProvider` sa `staleTime: 60s`, `retry: 1`
- `SessionRestorer` — `useRef` za exactly-once poziv `/auth/refresh` pri mount-u (restaurira sesiju iz httpOnly cookieja)

#### Login forma (`app/(auth)/login/page.tsx`) — PUNA IMPLEMENTACIJA
- `useForm` + `zodResolver` + shadcn `Form` komponente
- Zod schema: email validacija, password min 1 (samo required)
- Submit → `authApi.login()` → `setAuth()` → redirect na `?from=` parametar ili `/dashboard`
- Server greška prikazana iznad forme

#### Register forma (`app/(auth)/register/page.tsx`) — PUNA IMPLEMENTACIJA
- **Frontend domen validacija**: blokira staff domene (`fon.bg.ac.rs`, `etf.bg.ac.rs`) sa jasnom porukom; dozvoljeni samo `student.fon.bg.ac.rs` i `student.etf.bg.ac.rs`
- Polja: first_name, last_name (grid 2 col), email, password (min 8), confirmPassword
- `FormDescription` objašnjava dozvoljene domene
- Success state → auto-redirect na `/login` posle 2.5s
- Server greška prikazana iznad forme

#### shadcn/ui komponente u `components/ui/`
- `button.tsx` — `cva` varijante (default, destructive, outline, secondary, ghost, link; sm, lg, icon)
- `card.tsx` — Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter
- `form.tsx` — pun shadcn Form wrapper za react-hook-form (FormField, FormItem, FormLabel, FormControl, FormDescription, FormMessage)
- `input.tsx` — standardni shadcn input
- `label.tsx` — `@radix-ui/react-label` wrapper

---

## 3. KONFIGURACIJA

### 3.1 Backend — Python/FastAPI

**Verzija:** Python 3.12+, FastAPI 0.111+

**`requirements.txt` zavisnosti:**
```
# Web
fastapi>=0.111.0
uvicorn[standard]>=0.30.0

# Database
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0

# Validation
pydantic>=2.7.0
pydantic-settings>=2.3.0
email-validator>=2.1.0

# Auth
python-jose[cryptography]>=3.3.0
bcrypt>=4.1.0
passlib[bcrypt]>=1.7.4

# Redis
redis[hiredis]>=5.0.0

# Background tasks
celery[redis]>=5.4.0
flower>=2.0.0

# File storage
boto3>=1.34.0
minio>=7.2.0

# Email
fastapi-mail>=1.4.0
jinja2>=3.1.0

# HTTP / WebSocket
httpx>=0.27.0
python-multipart>=0.0.9
websockets>=12.0

# Utils
python-dotenv>=1.0.0
pytz>=2024.1
python-dateutil>=2.9.0
orjson>=3.10.0

# Testing
pytest>=8.2.0
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0
factory-boy>=3.3.0
```

**`backend/.env.example` — sve env varijable:**
```env
DATABASE_URL=postgresql+asyncpg://studentska:studentska_pass@postgres:5432/studentska_platforma
POSTGRES_USER=studentska
POSTGRES_PASSWORD=studentska_pass
POSTGRES_DB=studentska_platforma

REDIS_URL=redis://:redis_pass@redis:6379/0
REDIS_PASSWORD=redis_pass

SECRET_KEY=change-me-to-a-random-secret-key-minimum-32-characters
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_APPOINTMENTS=appointment-files
MINIO_BUCKET_AVATARS=professor-avatars
MINIO_BUCKET_IMPORTS=bulk-imports
MINIO_BUCKET_DOCUMENTS=document-requests
MINIO_SECURE=false

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@fon.bg.ac.rs
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=noreply@fon.bg.ac.rs
EMAILS_FROM_NAME=Konsultacije FON & ETF

GOOGLE_PSE_API_KEY=
GOOGLE_PSE_CX=

ALLOWED_STUDENT_DOMAINS=student.fon.bg.ac.rs,student.etf.bg.ac.rs
ALLOWED_STAFF_DOMAINS=fon.bg.ac.rs,etf.bg.ac.rs

APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO
FRONTEND_URL=http://localhost:3000

CELERY_BROKER_URL=redis://:redis_pass@redis:6379/1
CELERY_RESULT_BACKEND=redis://:redis_pass@redis:6379/2
```

**`backend/Dockerfile`:**
```
python:3.12-slim → apt install gcc libpq-dev → pip install requirements.txt
→ COPY . → uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 3.2 Frontend — Next.js 14

**`package.json` zavisnosti:**
```json
{
  "next": "14.2.5",
  "react": "^18.3.1",
  "zustand": "^4.5.4",
  "@tanstack/react-query": "^5.56.2",
  "@tanstack/react-query-devtools": "^5.56.2",
  "axios": "^1.7.7",
  "react-hook-form": "^7.53.0",
  "@hookform/resolvers": "^3.9.0",
  "zod": "^3.23.8",
  "@fullcalendar/react": "^6.1.15",
  "@fullcalendar/daygrid": "^6.1.15",
  "@fullcalendar/timegrid": "^6.1.15",
  "@fullcalendar/interaction": "^6.1.15",
  "@fullcalendar/list": "^6.1.15",
  "socket.io-client": "^4.7.5",
  "class-variance-authority": "^0.7.0",
  "clsx": "^2.1.1",
  "tailwind-merge": "^2.5.2",
  "lucide-react": "^0.441.0",
  "next-themes": "^0.3.0",
  "@radix-ui/react-label": "^2.1.0",
  "@radix-ui/react-slot": "^1.1.0",
  "@radix-ui/react-dialog": "^1.1.1",
  "@radix-ui/react-dropdown-menu": "^2.1.1",
  "@radix-ui/react-select": "^2.1.1",
  "@radix-ui/react-popover": "^1.1.0",
  "@radix-ui/react-toast": "^1.2.1",
  "@radix-ui/react-avatar": "^1.1.0",
  "@radix-ui/react-separator": "^1.1.0",
  "@radix-ui/react-tabs": "^1.1.0",
  "@radix-ui/react-checkbox": "^1.1.1",
  "@radix-ui/react-switch": "^1.1.0",
  "@radix-ui/react-progress": "^1.1.0",
  "@radix-ui/react-scroll-area": "^1.1.0",
  "@radix-ui/react-tooltip": "^1.1.2",
  "@radix-ui/react-alert-dialog": "^1.1.1",
  "@radix-ui/react-accordion": "^1.2.0",
  "@ducanh2912/next-pwa": "^10.2.9"
}
```
DevDeps: `typescript ^5.6`, `@types/node/react/react-dom`, `tailwindcss ^3.4`, `autoprefixer`, `postcss`, `eslint`, `eslint-config-next`.

**`frontend/.env.example`:**
```env
NEXT_PUBLIC_API_URL=http://localhost/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost
NEXT_PUBLIC_APP_NAME=Konsultacije FON & ETF
NEXT_PUBLIC_MINIO_PUBLIC_URL=http://localhost:9000
NEXT_PUBLIC_APP_ENV=development
```

**`frontend/Dockerfile` — 3-stage:**
```
node:20-alpine (deps) → node:20-alpine (builder, npm run build) → node:20-alpine (runner)
Non-root user nextjs:nodejs, server.js, PORT=3000
NEXT_PUBLIC_* se prosleđuju kao ARG/ENV tokom build-a
```

---

## 4. ŠTA NIJE JOŠ IMPLEMENTIRANO (Sledeće faze)

### Backend routers (svi zakomentarisani u `main.py`)
- `app/api/v1/users.py` — Admin CRUD korisnika, bulk CSV import
- `app/api/v1/students.py` — Pretraga profesora, zakazivanje, waitlist, document-requests
- `app/api/v1/professors.py` — Profil, slotovi, requests inbox, canned responses, CRM, FAQ
- `app/api/v1/appointments.py` — Detalji termina, WebSocket chat, file upload
- `app/api/v1/admin.py` — Strike menadžment, impersonacija, broadcast, audit log
- `app/api/v1/search.py` — Google PSE proxy
- `app/api/v1/notifications.py` — Notifikacije + WebSocket stream

### Backend servisi
- `services/booking_service.py` — Redis locking, slot rezervacija, auto-approve logika
- `services/availability_service.py` — CRUD slotova, recurring pravila, blackout datumi
- `services/waitlist_service.py` — Redis Sorted Sets, offer logika (2h TTL)
- `services/strike_service.py` — Automatska detekcija, blokada korisnika
- `services/notification_service.py` — In-app notifikacije + WebSocket Pub/Sub
- `services/document_request_service.py` — CRUD zahteva za dokumente
- `services/file_service.py` — MinIO upload, presigned URL generisanje
- `services/user_service.py` — Admin CRUD, bulk import CSV

### Backend Celery taskovi
- `tasks/notifications.py` — Email notifikacije za sve okidače iz PRD §5.2
- `tasks/strike_tasks.py` — No-show provera (Celery beat, 30min posle termina)
- `tasks/waitlist_tasks.py` — Obrada waitliste pri otkazivanju
- `tasks/reminder_tasks.py` — Podsetnci 24h i 1h pre termina

### Backend: Alembic migracije za buduće promene
- Trenutno postoji samo inicijalna migracija (sve tabele)
- Svaka promena šeme zahteva novu migraciju

### Frontend stranice (sve su STUB)
- `forgot-password` — forma za reset
- `dashboard` — student dashboard (termini, notifikacije, strike status)
- `search` — pretraga profesora sa filterima
- `professor/[id]` — profil + FullCalendar + FAQ
- `appointments/[id]` — detalji + WebSocket chat + fajlovi
- `my-appointments` — istorija sa statusima
- `document-requests` — student forma
- `professor/dashboard` — inbox + FullCalendar za profesore
- `professor/settings` — availability, canned responses, FAQ
- Sve admin stranice

### Frontend komponente (još ne postoje)
- `<BookingCalendar />` — FullCalendar za studente
- `<AvailabilityCalendar />` — FullCalendar za profesore (drag-drop)
- `<AppointmentRequestForm />` — react-dropzone + file upload
- `<TicketChat />` — WebSocket chat
- `<NotificationCenter />` — bell + dropdown
- `<StrikeDisplay />`, `<WaitlistButton />`, `<BulkImportModal />`, `<AuditLogTable />`
- `<DocumentRequestForm />`, `<DocumentRequestCard />`, `<ImpersonationBanner />`

### Infrastruktura (još ne postoji)
- `infra/docker-compose.prod.yml` — produkcijska konfiguracija
- SSL/TLS sertifikati za Nginx
- `celery-worker` i `celery-beat` servisi u Docker Compose
- PWA manifest.json i service worker
- `docs/api-collection.json` — Postman/Insomnia kolekcija

---

## 5. KRITIČNA PRAVILA (iz CLAUDE.md — uvek poštovati)

1. **Sve rute su async** — `async def` za sve FastAPI endpoint funkcije
2. **ORM only** — zabranjen raw SQL, samo SQLAlchemy ORM ili `select()` statements
3. **UUID PK** — ne Integer auto-increment
4. **Pydantic V2** — striktna validacija, `model_config = {"from_attributes": True}` za response šeme
5. **JWT u memory** — access token samo u Zustand, **NIKADA** localStorage/sessionStorage
6. **Refresh u httpOnly cookie** — postavlja backend, čita browser automatski
7. **App Router only** — `app/` direktorijum, **ne `pages/`**
8. **Server Components** za statični sadržaj, `"use client"` samo za interaktivne
9. **TanStack Query** za sve server state — ne `useEffect + fetch`
10. **Celery za sve emailove** — ne direktno iz endpoint funkcija
11. **Staff nalozi samo ADMIN kreira** — nema javne registracije za PROFESOR/ASISTENT/ADMIN
12. **`hashed_password` nikad u response** — UserResponse to ne sadrži
13. **Keycloak zakomentarisan** — V2 feature, ne implementirati u V1
14. **Redis Lua skripta za slot lock** — ne `SET NX` + `EXPIRE` kao odvojene komande

---

*Ovaj fajl je generisan automatski na osnovu skeniranja codebase-a i treba da služi kao kompletni kontekst za nastavak razvoja.*
