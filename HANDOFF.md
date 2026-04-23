# HANDOFF.md — Preuzimanje razvoja
## Studentska Platforma — FON & ETF
**Datum:** April 2026  
**Od:** Filip  
**Za:** [Drugarevo ime]

---

## Gde smo stali

Faza 0 je kompletna i aplikacija se pokreće lokalno. Sve što ti treba je već u repu.

### Šta radi:
- Docker Compose sa svim servisima (postgres, redis, minio, nginx, backend, frontend)
- PostgreSQL sa svim tabelama (17 tabela, sve relacije)
- JWT auth sistem — register, login, refresh, logout, forgot/reset password
- RBAC middleware — `require_role()` dependency
- Seed korisnici (profesori, admini) već u bazi
- Next.js login i register stranice (rade, domain validacija na frontendu)
- MinIO sa 4 bucketa, Nginx reverse proxy

### Šta NE postoji još:
- Nema ni jednog biznis feature-a (zakazivanje, slotovi, chat, admin...)
- Sve frontend stranice osim login/register su prazni STUB-ovi

---

## Kako da pokreneš projekat

```bash
# 1. Kloniraj repo
git clone https://github.com/filipovicfilip222-alt/student-platform-app.git
cd student-platform-app

# 2. Napravi .env fajlove
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. U backend/.env promeni ovo dvoje:
# SECRET_KEY=bilo-koja-random-string-od-32-karaktera
# REDIS_PASSWORD=redis_pass

# 4. Pokreni sve
cd infra
docker compose --profile app up -d --build

# 5. Migracije (samo prvi put)
docker exec studentska_backend alembic upgrade head

# 6. Seed korisnici (samo prvi put)
docker cp ../scripts/seed_db.py studentska_backend:/app/seed_db.py
docker exec studentska_backend python /app/seed_db.py
```

### Provera da sve radi:
- `http://localhost/api/v1/health` → `{"status":"ok"}`
- `http://localhost/docs` → Swagger UI sa auth endpointima
- `http://localhost` → login stranica
- `http://localhost:9001` → MinIO (minioadmin / minioadmin)

### Test login (Swagger → POST /api/v1/auth/login):
```json
{
  "email": "profesor1@fon.bg.ac.rs",
  "password": "Seed@2024!"
}
```

---

## Tvoj zadatak — Faza 1 Backend (Developer A)

Implementiraj redom. Svaki korak je nezavisan i može se testirati u Swagger-u.

### Korak 1 — Availability Engine

**Fajlovi koje praviš:**
- `backend/app/schemas/professor.py` — SlotCreate, SlotUpdate, SlotResponse, BlackoutCreate, BlackoutResponse
- `backend/app/services/availability_service.py` — CRUD za slotove i blackout datume
- `backend/app/api/v1/professors.py` — HTTP endpointi

**Endpointi:**
```
GET    /api/v1/professors/slots
POST   /api/v1/professors/slots
PUT    /api/v1/professors/slots/{slot_id}
DELETE /api/v1/professors/slots/{slot_id}
POST   /api/v1/professors/blackout
DELETE /api/v1/professors/blackout/{blackout_id}
```

**Pravila:** Sve `async def`, `require_role("PROFESOR")`, UUID pk, Pydantic V2.  
**Nakon toga:** odkomentiraj `professors.router` u `backend/app/main.py`.

---

### Korak 2 — Student pretraga i profili

**Fajlovi koje praviš:**
- `backend/app/schemas/student.py` — ProfessorSearchResponse, ProfessorProfileResponse
- `backend/app/services/search_service.py` — pretraga po imenu, katedri, predmetu, keyword
- `backend/app/api/v1/students.py` — search + profil endpointi

**Endpointi:**
```
GET /api/v1/students/professors/search   — query params: q, faculty, subject, type
GET /api/v1/students/professors/{id}     — profil + FAQ + slobodni slotovi
GET /api/v1/students/professors/{id}/slots  — slobodni slotovi (filter: date range)
```

---

### Korak 3 — Booking Engine (najkritičniji deo)

**Fajlovi koje praviš:**
- `backend/app/services/booking_service.py` — Redis locking + rezervacija

**Redis Lua lock (kopiraj iz CLAUDE.md sekcija 6):**
```python
LOCK_SCRIPT = """
if redis.call("exists", KEYS[1]) == 0 then
    redis.call("setex", KEYS[1], ARGV[1], ARGV[2])
    return 1
end
return 0
"""
```

**Tok zakazivanja:**
1. `acquire_slot_lock(redis, slot_id, user_id, ttl=30)` — atomičan lock
2. Ako lock ne uspe → `409 Conflict` → frontend poruka "Slot je upravo zauzet"
3. Validacija studenta (nema aktivne blokade, slot je slobodan u DB)
4. Kreiranje `Appointment` zapisa u PostgreSQL
5. Ako `auto_approve=True` → status odmah `APPROVED`, okidaj email Celery task
6. Otpusti lock

**Endpointi (dodaj u students.py):**
```
POST   /api/v1/students/appointments        — zakazivanje
DELETE /api/v1/students/appointments/{id}   — otkazivanje (24h pravilo)
GET    /api/v1/students/appointments        — moji termini (filter: upcoming/history)
```

---

### Korak 4 — Strike sistem

**Fajlovi koje praviš:**
- `backend/app/services/strike_service.py` — dodaj strike, proveri blokadu, unblock
- `backend/app/tasks/strike_tasks.py` — Celery task za no-show detekciju

**Logika:**
- Pri otkazivanju < 12h → automatski +1 poen → proveri da li treba blokada
- Celery beat task: svakih 30 min proverava termine koji su završili pre 30 min → ako `APPROVED` i nema potvrde → +2 poena, status → `NO_SHOW`
- 3+ poena → kreira `StudentBlock` zapis sa `blocked_until = now + 14 dana`
- 4+ poena → svaki sledeći prekršaj produžava za 7 dana

---

### Korak 5 — Waitlist logika

**Fajlovi koje praviš:**
- `backend/app/services/waitlist_service.py` — Redis Sorted Sets
- `backend/app/tasks/waitlist_tasks.py` — Celery task za slanje ponuda

**Redis namespace:**
```
waitlist:{slot_id}              → Sorted Set, score = Unix timestamp
waitlist:offer:{slot_id}:{uid}  → String, TTL 2h (aktivna ponuda)
```

**Endpointi (dodaj u students.py):**
```
POST   /api/v1/students/waitlist/{slot_id}  — prijava
DELETE /api/v1/students/waitlist/{slot_id}  — odjava
```

---

### Korak 6 — Email notifikacije (Celery tasks)

**Fajl:** `backend/app/tasks/notifications.py`

Implementiraj Celery taskove za sve okidače iz PRD §5.2:
- `send_appointment_confirmed(appointment_id)`
- `send_appointment_rejected(appointment_id, reason)`
- `send_appointment_reminder(appointment_id, hours_before)` — 24h i 1h
- `send_strike_added(student_id, points, total)`
- `send_block_activated(student_id, blocked_until)`
- `send_waitlist_offer(student_id, slot_id, expires_at)`

Svaki task: dohvati podatke iz DB → pošalji email putem `app/core/email.py`.

---

## Git workflow

```bash
# Uvek radi na feature grani
git checkout -b feature/A-availability-engine
git checkout -b feature/A-booking-engine
# itd.

# Commit format
git commit -m "feat: availability engine CRUD endpoints"
git commit -m "fix: slot lock TTL nije se postavljao"

# Push i otvori PR prema dev branchu
git push origin feature/A-availability-engine
# Na GitHubu → New Pull Request → base: dev
```

**Ne push-uj direktno na `main` ili `dev`.**  
Felipe će review-ovati PR pre merge-a.

---

## Referentni fajlovi (sve što ti treba za kontekst)

| Fajl | Opis |
|------|------|
| `CLAUDE.md` | Pravila koda, konvencije, zabranjena ponašanja — čitaj pre svakog feature-a |
| `CURRENT_STATE.md` | Presek codebase-a, šta postoji, šta ne |
| `docs/copilot_plan_prompt.md` | Detaljna DB šema, API spec, sprint plan |
| `docs/PRD_Studentska_Platforma.md` | Poslovni zahtevi i UX pravila |
| `http://localhost/docs` | Swagger UI — testiraj endpointe ovde |

---

## Cursor workflow (kako koristiti AI)

```
# U Cursor chat, taguj uvek oba fajla:
@CLAUDE.md @CURRENT_STATE.md

# Primer prompta za Korak 1:
"Implementiraj Availability Engine prema Koraku 1 iz HANDOFF.md.
 Modeli već postoje u app/models/. Prati sva pravila iz CLAUDE.md."
```

**Kada Cursor predloži nešto što nije u skladu sa CLAUDE.md** (npr. localStorage, raw SQL, Keycloak) — reci mu: *"Pročitaj CLAUDE.md sekcija 11 — zabranjeno ponašanje"*.

---

## Pitanja?

Pišite na Discord/WhatsApp. Sync 5 min svaki dan — šta je urađeno, šta blokira.

---

*Srećno! Aplikacija se pokreće, baza je spremna — samo implementiraj logiku.*
