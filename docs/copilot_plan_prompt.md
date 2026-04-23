# GitHub Copilot — Plan Mode: Studentska Platforma

## ULOGA I KONTEKST

Ti si senior full-stack arhitekta koji planira razvoj **Platforme za upravljanje univerzitetskim konsultacijama i komunikacijom** za FON i ETF. Tvoj zadatak je da kreirate detaljan, strukturiran razvojni plan pre nego što se napiše i jedna linija koda.

Čitaj sledeća dva dokumenta u `docs/` direktorijumu kao **jedini source of truth**:

- `docs/PRD_Studentska_Platforma.md`
- `docs/Arhitektura_i_Tehnoloski_Stek.md`

**NE predlaži alternativne tehnologije.** Arhitektura je finalizovana.

---

## TEHNOLOŠKI STEK (FIKSAN)

| Sloj | Tehnologija |
|------|-------------|
| Backend API | FastAPI (Python 3.12+) |
| Relaciona baza | PostgreSQL 16 + pgvector |
| Keš / Locking / Queues | Redis 7 |
| Frontend | Next.js 14 (App Router) + Tailwind CSS + Shadcn/ui |
| Autentifikacija V1 | JWT (python-jose + bcrypt) — direktna email/password |
| Autentifikacija V2 | Keycloak (self-hosted) — planira se naknadno |
| File Storage | MinIO (self-hosted, S3-compatible) |
| Real-time | WebSockets (FastAPI native) |
| Kontejnerizacija | Docker + Docker Compose |
| Kalendar UI | FullCalendar (React) |

---

## ZADATAK: KREIRAJ KOMPLETAN RAZVOJNI PLAN

---

### 1. STRUKTURA PROJEKTA (Monorepo)

```
/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── students.py
│   │   │       ├── professors.py
│   │   │       ├── appointments.py
│   │   │       ├── document_requests.py
│   │   │       ├── admin.py
│   │   │       ├── search.py
│   │   │       └── notifications.py
│   │   ├── core/
│   │   │   ├── config.py          — pydantic-settings env varijable
│   │   │   ├── security.py        — JWT helper funkcije
│   │   │   ├── dependencies.py    — get_current_user, require_role
│   │   │   └── email.py           — email sender helper
│   │   ├── models/                — SQLAlchemy ORM modeli
│   │   ├── schemas/               — Pydantic request/response šeme
│   │   ├── services/              — business logika (booking, strikes, waitlist)
│   │   ├── tasks/                 — Celery taskovi
│   │   └── main.py
│   ├── alembic/                   — migracije
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                       — Next.js App Router stranice
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   └── register/
│   │   ├── (student)/
│   │   │   ├── dashboard/
│   │   │   ├── search/
│   │   │   ├── professor/[id]/
│   │   │   ├── appointments/
│   │   │   │   └── [id]/
│   │   │   ├── my-appointments/
│   │   │   └── document-requests/
│   │   ├── (professor)/
│   │   │   ├── dashboard/
│   │   │   └── settings/
│   │   └── (admin)/
│   │       └── dashboard/
│   ├── components/
│   │   ├── ui/                    — shadcn/ui komponente
│   │   ├── calendar/
│   │   ├── chat/
│   │   ├── notifications/
│   │   └── shared/
│   ├── lib/
│   │   ├── api.ts                 — axios klijent sa JWT interceptorom
│   │   ├── auth.ts                — auth store (zustand)
│   │   └── hooks/
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── nginx/
│   │   └── nginx.conf
│   └── minio/
│       └── init-buckets.sh
├── docs/
│   ├── PRD_Studentska_Platforma.md
│   ├── Arhitektura_i_Tehnoloski_Stek.md
│   └── CLAUDE.md
└── scripts/
    ├── seed_db.py                 — seed korisnika (profesori, admini)
    ├── bulk_import.py
    └── migrate.sh
```

---

### 2. BAZA PODATAKA — ŠEMA

#### `users`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| email | VARCHAR(255) | NOT NULL, UNIQUE |
| hashed_password | VARCHAR(255) | NOT NULL |
| first_name | VARCHAR(100) | NOT NULL |
| last_name | VARCHAR(100) | NOT NULL |
| role | ENUM('STUDENT','ASISTENT','PROFESOR','ADMIN') | NOT NULL |
| faculty | ENUM('FON','ETF') | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| is_verified | BOOLEAN | DEFAULT FALSE |
| profile_image_url | TEXT | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `professors`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| user_id | UUID | FK users.id, UNIQUE |
| title | VARCHAR(100) | NOT NULL (dr, prof. dr, itd.) |
| department | VARCHAR(200) | NOT NULL |
| office | VARCHAR(100) | NULLABLE |
| office_description | TEXT | NULLABLE |
| areas_of_interest | TEXT[] | DEFAULT '{}' |
| auto_approve_recurring | BOOLEAN | DEFAULT TRUE |
| auto_approve_special | BOOLEAN | DEFAULT FALSE |
| buffer_minutes | INTEGER | DEFAULT 5 |

#### `subjects`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| name | VARCHAR(200) | NOT NULL |
| code | VARCHAR(50) | UNIQUE |
| faculty | ENUM('FON','ETF') | NOT NULL |
| professor_id | UUID | FK professors.id |

#### `subject_assistants`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| subject_id | UUID | FK subjects.id |
| assistant_id | UUID | FK users.id |
| PRIMARY KEY | (subject_id, assistant_id) | |

#### `availability_slots`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| professor_id | UUID | FK professors.id |
| slot_datetime | TIMESTAMPTZ | NOT NULL |
| duration_minutes | INTEGER | NOT NULL |
| consultation_type | ENUM('UZIVO','ONLINE') | NOT NULL |
| max_students | INTEGER | DEFAULT 1 |
| online_link | TEXT | NULLABLE |
| is_available | BOOLEAN | DEFAULT TRUE |
| recurring_rule | JSONB | NULLABLE |
| valid_from | DATE | NULLABLE |
| valid_until | DATE | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `blackout_dates`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| professor_id | UUID | FK professors.id |
| start_date | DATE | NOT NULL |
| end_date | DATE | NOT NULL |
| reason | TEXT | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `appointments`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| slot_id | UUID | FK availability_slots.id |
| professor_id | UUID | FK professors.id |
| lead_student_id | UUID | FK users.id |
| subject_id | UUID | FK subjects.id, NULLABLE |
| topic_category | ENUM('SEMINARSKI','PREDAVANJA','ISPIT','PROJEKAT','OSTALO') | NOT NULL |
| description | TEXT | NOT NULL, CHECK length >= 20 |
| status | ENUM('PENDING','APPROVED','REJECTED','CANCELLED','COMPLETED') | DEFAULT 'PENDING' |
| consultation_type | ENUM('UZIVO','ONLINE') | NOT NULL |
| rejection_reason | TEXT | NULLABLE |
| delegated_to | UUID | FK users.id, NULLABLE |
| is_group | BOOLEAN | DEFAULT FALSE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `appointment_participants`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| appointment_id | UUID | FK appointments.id |
| student_id | UUID | FK users.id |
| status | ENUM('PENDING','CONFIRMED','DECLINED') | DEFAULT 'PENDING' |
| is_lead | BOOLEAN | DEFAULT FALSE |
| confirmed_at | TIMESTAMPTZ | NULLABLE |

#### `waitlist`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| slot_id | UUID | FK availability_slots.id |
| student_id | UUID | FK users.id |
| joined_at | TIMESTAMPTZ | DEFAULT NOW() |
| notified_at | TIMESTAMPTZ | NULLABLE |
| offer_expires_at | TIMESTAMPTZ | NULLABLE |
| UNIQUE | (slot_id, student_id) | |

#### `files`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| appointment_id | UUID | FK appointments.id |
| uploaded_by | UUID | FK users.id |
| filename | VARCHAR(255) | NOT NULL |
| minio_object_key | TEXT | NOT NULL |
| file_size_bytes | INTEGER | NOT NULL |
| mime_type | VARCHAR(100) | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `ticket_chat_messages`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| appointment_id | UUID | FK appointments.id |
| sender_id | UUID | FK users.id |
| content | TEXT | NOT NULL, max 1000 chars |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `crm_notes`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| professor_id | UUID | FK professors.id |
| student_id | UUID | FK users.id |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `strike_records`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| student_id | UUID | FK users.id |
| appointment_id | UUID | FK appointments.id |
| points | INTEGER | NOT NULL (1 ili 2) |
| reason | ENUM('LATE_CANCEL','NO_SHOW') | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `student_blocks`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| student_id | UUID | FK users.id, UNIQUE |
| blocked_until | TIMESTAMPTZ | NOT NULL |
| removed_by | UUID | FK users.id, NULLABLE |
| removal_reason | TEXT | NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `faq_items`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| professor_id | UUID | FK professors.id |
| question | TEXT | NOT NULL |
| answer | TEXT | NOT NULL |
| sort_order | INTEGER | DEFAULT 0 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `notifications`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| type | VARCHAR(50) | NOT NULL |
| title | VARCHAR(200) | NOT NULL |
| body | TEXT | NOT NULL |
| data | JSONB | NULLABLE (deep link, IDs) |
| is_read | BOOLEAN | DEFAULT FALSE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `audit_log`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| admin_id | UUID | FK users.id |
| impersonated_user_id | UUID | FK users.id, NULLABLE |
| action | TEXT | NOT NULL |
| ip_address | INET | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `canned_responses`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| professor_id | UUID | FK professors.id |
| title | VARCHAR(100) | NOT NULL |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `document_requests`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| student_id | UUID | FK users.id |
| document_type | ENUM('POTVRDA_STATUSA','UVERENJE_ISPITI','UVERENJE_PROSEK','PREPIS_OCENA','POTVRDA_SKOLARINE','OSTALO') | NOT NULL |
| note | TEXT | NULLABLE |
| status | ENUM('PENDING','APPROVED','REJECTED','COMPLETED') | DEFAULT 'PENDING' |
| admin_note | TEXT | NULLABLE |
| pickup_date | DATE | NULLABLE |
| processed_by | UUID | FK users.id, NULLABLE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

#### `password_reset_tokens`
| Kolona | Tip | Constraints |
|--------|-----|-------------|
| id | UUID | PK |
| user_id | UUID | FK users.id |
| token_hash | VARCHAR(255) | NOT NULL, UNIQUE |
| expires_at | TIMESTAMPTZ | NOT NULL |
| used_at | TIMESTAMPTZ | NULLABLE |

---

### 3. API SPECIFIKACIJA

#### 3.1 Auth (`/api/v1/auth/`)

| Metod | Putanja | Uloga | Opis |
|-------|---------|-------|------|
| POST | `/register` | — | Registracija (validacija email domene, uloga = STUDENT za student domene) |
| POST | `/login` | — | Login, returns `{access_token, refresh_token}` |
| POST | `/refresh` | — | Obnovi access token (refresh token iz cookie) |
| POST | `/logout` | AUTH | Briše refresh token iz Redis |
| POST | `/forgot-password` | — | Šalje reset email |
| POST | `/reset-password` | — | Menja lozinku (token validacija) |
| GET | `/me` | AUTH | Trenutni korisnik + uloga + fakultet |

#### 3.2 Student Portal (`/api/v1/students/`)

| Metod | Putanja | Uloga | Napomena |
|-------|---------|-------|---------|
| GET | `/professors/search` | STUDENT | Query: `q`, `faculty`, `subject`, `type`, `available_today` |
| GET | `/professors/{id}` | STUDENT | Profil + FAQ + slobodni slotovi |
| GET | `/professors/{id}/slots` | STUDENT | Slobodni slotovi (filter: date range) |
| POST | `/appointments` | STUDENT | Zakazivanje (Redis lock na slot_id pre DB upisa) |
| DELETE | `/appointments/{id}` | STUDENT | Otkazivanje (24h pravilo, strike logika) |
| POST | `/waitlist/{slot_id}` | STUDENT | Prijava na waitlist |
| DELETE | `/waitlist/{slot_id}` | STUDENT | Odjava sa waitlist |
| GET | `/appointments` | STUDENT | Moji termini (filter: upcoming/history) |
| POST | `/document-requests` | STUDENT | Novi zahtev za dokument |
| GET | `/document-requests` | STUDENT | Moji zahtevi za dokumente |

#### 3.3 Professor Portal (`/api/v1/professors/`)

| Metod | Putanja | Uloga | Napomena |
|-------|---------|-------|---------|
| GET | `/profile` | PROFESOR | Sopstveni profil |
| PUT | `/profile` | PROFESOR | Izmena profila |
| GET | `/slots` | PROFESOR | Lista svih slotova |
| POST | `/slots` | PROFESOR | Novi slot / recurring pravilo |
| PUT | `/slots/{id}` | PROFESOR | Izmena slota |
| DELETE | `/slots/{id}` | PROFESOR | Brisanje slota |
| POST | `/blackout` | PROFESOR | Blokada dana (triggeruje notifikacije ako ima zakazanih) |
| GET | `/requests` | PROFESOR/ASISTENT | Inbox zahteva (filter: pending/all) |
| POST | `/requests/{id}/approve` | PROFESOR/ASISTENT | Odobrenje |
| POST | `/requests/{id}/reject` | PROFESOR/ASISTENT | Odbijanje (obavezno canned_response ili tekst) |
| POST | `/requests/{id}/delegate` | PROFESOR | Delegiranje asistentu |
| GET | `/canned-responses` | PROFESOR | Lista šablona |
| POST | `/canned-responses` | PROFESOR | Novi šablon |
| PUT | `/canned-responses/{id}` | PROFESOR | Izmena šablona |
| DELETE | `/canned-responses/{id}` | PROFESOR | Brisanje šablona |
| GET | `/crm/{student_id}` | PROFESOR/ASISTENT | CRM beleške za studenta |
| POST | `/crm/{student_id}` | PROFESOR/ASISTENT | Nova CRM beleška |
| PUT | `/crm/{note_id}` | PROFESOR/ASISTENT | Izmena beleške |
| GET | `/faq` | PROFESOR | Lista FAQ |
| POST | `/faq` | PROFESOR | Nova FAQ stavka |
| PUT | `/faq/{id}` | PROFESOR | Izmena FAQ |
| DELETE | `/faq/{id}` | PROFESOR | Brisanje FAQ |

#### 3.4 Appointments (`/api/v1/appointments/`)

| Metod | Putanja | Uloga | Napomena |
|-------|---------|-------|---------|
| GET | `/{id}` | AUTH | Detalji termina (samo učesnici) |
| GET | `/{id}/messages` | AUTH | Istorija chat poruka |
| WS | `/{id}/chat` | AUTH | WebSocket chat kanal |
| POST | `/{id}/files` | AUTH | Upload fajla (multipart, max 5MB, MinIO) |
| GET | `/{id}/files` | AUTH | Lista fajlova termina |
| DELETE | `/{id}/files/{file_id}` | AUTH | Brisanje fajla |
| POST | `/{id}/participants/confirm` | STUDENT | Potvrda učešća u grupnoj konsultaciji |
| POST | `/{id}/participants/decline` | STUDENT | Odbijanje učešća |

#### 3.5 Admin Panel (`/api/v1/admin/`)

| Metod | Putanja | Uloga | Napomena |
|-------|---------|-------|---------|
| GET | `/users` | ADMIN | Lista korisnika (filter: role, faculty, search) |
| POST | `/users` | ADMIN | Ručno kreiranje naloga (profesor, asistent, admin) |
| PUT | `/users/{id}` | ADMIN | Izmena (uloga, aktivan/neaktivan) |
| DELETE | `/users/{id}` | ADMIN | Deaktivacija naloga |
| POST | `/users/bulk-import` | ADMIN | CSV upload studenata (multipart) |
| POST | `/impersonate/{user_id}` | ADMIN | Početak impersonacije (audit log) |
| POST | `/impersonate/end` | ADMIN | Kraj impersonacije |
| GET | `/strikes` | ADMIN | Lista svih studenata sa strike poenima |
| POST | `/strikes/{student_id}/unblock` | ADMIN | Skidanje blokade sa obrazloženjem |
| POST | `/broadcast` | ADMIN | Globalno obaveštenje (target group, channels) |
| GET | `/document-requests` | ADMIN | Inbox zahteva za dokumente (filter: status) |
| POST | `/document-requests/{id}/approve` | ADMIN | Odobrenje zahteva (pickup_date, admin_note) |
| POST | `/document-requests/{id}/reject` | ADMIN | Odbijanje (obavezno admin_note) |
| POST | `/document-requests/{id}/complete` | ADMIN | Označava da je student preuzeo dokument |
| GET | `/audit-log` | ADMIN | Pregled audit loga |

#### 3.6 Pretraga (`/api/v1/search/`)

| Metod | Putanja | Uloga | Napomena |
|-------|---------|-------|---------|
| GET | `/university` | AUTH | Google PSE proxy (q param, ograničen na fon.bg.ac.rs i etf.bg.ac.rs) |

#### 3.7 Notifikacije (`/api/v1/notifications/`)

| Metod | Putanja | Uloga | Napomena |
|-------|---------|-------|---------|
| GET | `/` | AUTH | Lista notifikacija (poslednje 50) |
| POST | `/{id}/read` | AUTH | Označi kao pročitano |
| POST | `/read-all` | AUTH | Označi sve kao pročitano |
| WS | `/stream` | AUTH | Real-time notifikacije (Redis Pub/Sub) |

---

### 4. REDIS ARHITEKTURA

| Namespace | Tip | TTL | Opis |
|-----------|-----|-----|------|
| `slot:lock:{slot_id}` | String | 30s | Pessimistic lock (Lua SET NX) |
| `waitlist:{slot_id}` | Sorted Set | ∞ | score = Unix timestamp prijave |
| `chat:pub:{appointment_id}` | Pub/Sub Channel | — | WebSocket chat relay |
| `notif:pub:{user_id}` | Pub/Sub Channel | — | Real-time notifikacije |
| `notif:unread:{user_id}` | String (counter) | ∞ | Broj nepročitanih |
| `refresh:{user_id}` | String | 7d | Refresh token store |
| `strike:check:{appointment_id}` | String | 90min | Trigger za no-show proveru |
| `waitlist:offer:{slot_id}:{user_id}` | String | 2h | Aktivna ponuda sa waitliste |

---

### 5. RAZVOJNI PLAN PO FAZAMA

#### Faza 0 — Infrastruktura (Nedelja 1-2)

**Oba developera zajedno (setup se radi jednom):**
- Docker Compose: PostgreSQL, Redis, MinIO, Nginx
- FastAPI skeleton sa health check (`GET /api/v1/health`)
- Next.js skeleton
- Alembic setup i inicijalne migracije (tabele users, professors)
- MinIO bucket inicijalizacija (`init-buckets.sh`)
- `.env.example` fajlovi za sve servise
- Seed skripta (profesori, admini)
- Git repo sa `main` / `dev` branch strategijom, PR workflow

---

#### Faza 1 — Core MVP (Nedelja 3-7)

**Podela posla između developera:**

##### Developer A — Backend Core
- JWT Auth sistem (register, login, refresh, logout, forgot/reset password)
- RBAC middleware (`require_role` dependency)
- Availability Engine (CRUD slotova, recurring pravila, blackout datumi)
- Booking Engine (zakazivanje + Redis pessimistic locking)
- Strike sistem (automatska detekcija, Celery cron)
- Waitlist logika (Redis Sorted Sets, Celery task za notifikacije)
- Email notifikacije (Celery task, sve okidače iz PRD-a)

##### Developer B — Frontend Core
- Auth stranice (login, register, forgot password)
- Zustand auth store + Axios JWT interceptor
- Student dashboard (upcoming termini)
- Pretraga profesora (search + filteri)
- Profil profesora + FAQ prikaz
- `<BookingCalendar />` — FullCalendar za studente (slobodni slotovi)
- `<AppointmentRequestForm />` — forma za zakazivanje sa file upload-om
- Stranica "Moji termini" sa statusima

---

#### Faza 2 — Komunikacija, Admin, Dokumenti (Nedelja 8-11)

##### Developer A — Backend
- In-App Chat WebSocket endpoint + Redis Pub/Sub
- CRM beleške (CRUD)
- Canned responses (CRUD)
- Admin endpoints: CRUD korisnici, bulk CSV import, impersonacija + audit log
- Global broadcast (Celery task za email + in-app baner)
- **Document Requests** (student podnosi zahtev, admin obrađuje — puni CRUD)
- Google PSE proxy endpoint

##### Developer B — Frontend
- `<TicketChat />` — WebSocket chat komponenta
- `<NotificationCenter />` — Bell dropdown + stranica svih notifikacija
- Professor dashboard (inbox zahteva, odobravanje/odbijanje sa canned responses)
- `<AvailabilityCalendar />` — FullCalendar za profesore (drag-and-drop slotovi)
- Professor settings (blackout datumi, auto-approve konfiguracija, FAQ menadžment)
- **Student: stranica "Zahtevi za dokumente"** (podnošenje novog zahteva, praćenje statusa)
- **Admin: Document Requests inbox** (odobrenje/odbijanje, datum preuzimanja, complete)
- Admin panel (CRUD korisnici, bulk import modal, strike menadžment)

---

#### Faza 3 — Polish i V2 Prep (Nedelja 12-14)

**Oba zajedno:**
- Google PSE UI integracija (search boks u aplikaciji)
- `<StrikeDisplay />` komponenta
- `<WaitlistButton />` sa real-time statusom
- PWA manifest, service worker, offline keširanje
- FullCalendar drag-and-drop UX optimizacija
- Grupne konsultacije UI (tagovanje kolega, potvrda učešća)
- Performance testiranje i optimizacija
- Priprema pgvector šeme (empty extension, ready za V2)

---

### 6. SIGURNOSNI ZAHTEVI — CHECKLIST

- [ ] Email domen whitelist pri registraciji (student i staff domeni)
- [ ] bcrypt hash lozinki (12 rounds minimum)
- [ ] JWT access token: kratki lifetime (1h), refresh u httpOnly cookie
- [ ] Refresh token invalidacija pri logout-u (Redis brisanje)
- [ ] RBAC middleware — svaki endpoint proverava ulogu
- [ ] Rate limiting na login i register (sprečavanje brute force)
- [ ] Rate limiting na zakazivanje (sprečavanje spam zahteva)
- [ ] File upload validacija (tip MIME, veličina max 5MB)
- [ ] Audit log za sve admin akcije (impersonacija, brisanje, bulk import)
- [ ] CORS podešen samo za frontend origin
- [ ] HTTPS enforced (Nginx reverse proxy)
- [ ] Redis lock atomičnost (Lua skripta za test-and-set)
- [ ] SQLAlchemy ORM only (no raw queries) — SQL injection prevencija
- [ ] CRM beleške vidljive samo PROFESOR/ASISTENT rolama
- [ ] Chat poruke dostupne samo učesnicima termina
- [ ] Document request detalji dostupni samo podnosiocu i ADMIN-u
- [ ] Parametrizovani upiti za sve pretrrage

---

### 7. ENVIRONMENT VARIJABLE

```env
# FastAPI Backend
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/studentska_platforma
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-super-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_APPOINTMENTS=appointment-files
MINIO_BUCKET_AVATARS=professor-avatars
MINIO_BUCKET_IMPORTS=bulk-imports
MINIO_SECURE=false

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@fon.bg.ac.rs
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=noreply@fon.bg.ac.rs

GOOGLE_PSE_API_KEY=
GOOGLE_PSE_CX=

ALLOWED_STUDENT_DOMAINS=student.fon.bg.ac.rs,student.etf.bg.ac.rs
ALLOWED_STAFF_DOMAINS=fon.bg.ac.rs,etf.bg.ac.rs

FRONTEND_URL=https://konsultacije.fon.bg.ac.rs

# Next.js Frontend
NEXT_PUBLIC_API_URL=https://konsultacije.fon.bg.ac.rs/api/v1
NEXT_PUBLIC_WS_URL=wss://konsultacije.fon.bg.ac.rs
NEXT_PUBLIC_APP_NAME=Konsultacije FON & ETF
```

---

### 8. FRONTEND STRANICE I KOMPONENTE

#### Stranice (Next.js App Router)

| Putanja | Uloga | Opis |
|---------|-------|------|
| `/login` | — | Login forma |
| `/register` | — | Registracija (samo student domeni) |
| `/forgot-password` | — | Reset lozinke |
| `/dashboard` | STUDENT | Upcoming termini, notifikacije, strike status |
| `/search` | STUDENT | Pretraga profesora sa filterima |
| `/professor/[id]` | STUDENT | Profil + FullCalendar + FAQ |
| `/appointments/[id]` | AUTH | Detalji + chat + fajlovi |
| `/my-appointments` | STUDENT | Istorija termina sa statusima |
| `/document-requests` | STUDENT | Lista zahteva + novi zahtev forma |
| `/professor/dashboard` | PROFESOR/ASISTENT | Inbox zahteva, FullCalendar |
| `/professor/settings` | PROFESOR | Availability, canned responses, FAQ, profil |
| `/admin` | ADMIN | Pregled sistema, statistike |
| `/admin/users` | ADMIN | CRUD korisnici, bulk import |
| `/admin/document-requests` | ADMIN | Inbox zahteva za dokumente |
| `/admin/strikes` | ADMIN | Strike menadžment |
| `/admin/broadcast` | ADMIN | Slanje broadcast obaveštenja |
| `/admin/audit-log` | ADMIN | Pregled audit loga |

#### Ključne komponente

| Komponenta | Opis |
|-----------|------|
| `<AvailabilityCalendar />` | FullCalendar za profesore — drag-and-drop kreiranje slotova, recurring pravila |
| `<BookingCalendar />` | FullCalendar za studente — read-only slobodni slotovi, klik za zakazivanje |
| `<AppointmentRequestForm />` | Forma: tema dropdown, opis, file upload (react-dropzone) |
| `<TicketChat />` | WebSocket chat — poruke, scroll-to-bottom, max 20 poruka indikator |
| `<StrikeDisplay />` | Vizualni prikaz strike poena, datum isteka blokade |
| `<WaitlistButton />` | Prijava/odjava, real-time pozicija na listi |
| `<NotificationCenter />` | Bell sa brojem, dropdown, link na sve notifikacije |
| `<BulkImportModal />` | CSV upload, preview tabela, potvrda |
| `<AuditLogTable />` | Tabela audit loga sa filterima |
| `<DocumentRequestForm />` | Student forma za zahtev dokumenta |
| `<DocumentRequestCard />` | Student prikaz zahteva sa statusom |
| `<DocumentRequestAdminRow />` | Admin row sa akcijama: approve (+ datum), reject, complete |
| `<ImpersonationBanner />` | Crveni baner "ADMIN MODE — Impersonirate [Ime]" |

---

### 9. PITANJA ZA POJAŠNJENJE

1. **Email servis**: Koji SMTP server za automatske emailove — fakultetski SMTP, SendGrid, ili lokalni Postfix u Docker-u za development?
2. **Push notifikacije**: Web Push API u MVP-u ili samo email + in-app za V1?
3. **Vremenska zona**: Jedinstven `Europe/Belgrade` za ceo sistem?
4. **Google PSE**: Da li je API ključ već obezbeđen?
5. **Kapacitet**: Koliko simultanih korisnika — za Redis pool i DB connection pool sizing?
6. **Backup**: Ko je odgovoran za PostgreSQL i MinIO backup?
7. **Document pickup napomena**: Da li studentska služba treba da šalje i SMS/email sa fiksnim tekstom (npr. "Vaš dokument je spreman — soба 12, Palata nauke") ili je slobodan tekst dovoljan?

---

### 10. PREPORUČENI WORKFLOW ZA RAD U PARU

#### Git strategija
```
main          — produkcioni branch (zaštićen, merge samo PR-om)
dev           — integracioni branch
feature/A-*   — Developer A feature grane
feature/B-*   — Developer B feature grane
```

#### Pravila
- PR review pre svakog merge-a u `dev`
- Niko ne push-uje direktno na `main` ili `dev`
- Commit poruke: `feat:`, `fix:`, `chore:`, `docs:`
- API kontrakt (OpenAPI šema) se dogovara pre nego što Developer B počne frontend implementaciju feature-a koji zavisi od novog endpointa

#### Sinhronizacija A↔B
- Developer A eksponira Swagger UI lokalno — Developer B koristi za razvoj
- Shared Postman/Insomnia kolekcija u `/docs/api-collection.json`
- Daily sync (5 minuta): šta je urađeno, šta blokira

---

*Dokument je deo `docs/` foldera projekta.*
