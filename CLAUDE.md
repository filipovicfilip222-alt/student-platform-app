# CLAUDE.md — Studentska Platforma
## Vodič za AI asistente (Cursor, GitHub Copilot, Claude)

> Ovaj fajl je **jedini source of truth** za AI asistente koji rade na ovom projektu.
> Uvek čitaj ovaj fajl pre nego što predložiš bilo kakav kod.

---

## 1. PROJEKAT U JEDNOJ REČENICI

Platforma za zakazivanje konsultacija između studenata i profesora **FON-a i ETF-a**, sa admin panelovom za studentsku službu, chat sistemom, strike sistemom i zahtevima za zvanične dokumente.

---

## 2. TEHNOLOŠKI STEK (FIKSAN — NE PREDLAŽИ ALTERNATIVE)

| Sloj | Tehnologija | Verzija |
|------|-------------|---------|
| Backend | FastAPI | 0.111+ |
| Python | Python | 3.12+ |
| ORM | SQLAlchemy (async) + asyncpg | Latest |
| Migracije | Alembic | Latest |
| Baza | PostgreSQL | 16 |
| Keš / Queue | Redis | 7 |
| Background tasks | Celery + Redis broker | Latest |
| Frontend | Next.js App Router | 14 |
| Styling | Tailwind CSS + Shadcn/ui | Latest |
| State | Zustand (client), TanStack Query (server) | Latest |
| Forme | react-hook-form + zod | Latest |
| Kalendar | FullCalendar (React) | Latest |
| HTTP klijent | Axios sa JWT interceptorom | Latest |
| WebSocket klijent | socket.io-client | Latest |
| File storage | MinIO (S3-compatible) | Latest |
| Auth V1 | JWT (python-jose + bcrypt) | — |
| Auth V2 | Keycloak 24+ | Planira se naknadno |
| Kontejnerizacija | Docker + Docker Compose | Latest |
| Reverse proxy | Nginx | Latest |
| PWA | next-pwa | Latest |

---

## 3. ARHITEKTURA — KRITIČNA PRAVILA

### Backend
- **Sve rute su async** — koristiti `async def` za sve endpoint funkcije
- **ORM only** — zabranjen raw SQL, koristiti SQLAlchemy ORM ili `select()` statements
- **Dependency injection** za auth: `current_user = Depends(get_current_user)`
- **RBAC** se proverava u svakom endpoint-u: `Depends(require_role("PROFESOR"))`
- **Pydantic V2** za sve request/response šeme — striktna validacija
- **UUID** kao primarni ključevi (ne Integer auto-increment)
- **Celery** za sve background operacije: email slanje, cron, waitlist processing

### Frontend
- **App Router** — koristiti `app/` direktorijum, ne `pages/`
- **Server Components** za statični sadržaj (profili, FAQ)
- **Client Components** (`"use client"`) za interaktivne elemente (kalendar, chat, forme)
- **JWT u memory** — access token se čuva u Zustand store-u, **NIKADA u localStorage**
- **Refresh token u httpOnly cookie** — postavljan od strane backend-a
- **Protected routes** putem Next.js middleware (`middleware.ts`)
- **TanStack Query** za sve server state — ne koristiti `useEffect` + `fetch`
- **Zod** za validaciju formi, šeme usklađene sa backend Pydantic šemama

---

## 4. EMAIL VALIDACIJA — KRITIČNO

```python
# backend/app/core/security.py

ALLOWED_STUDENT_DOMAINS = [
    "student.fon.bg.ac.rs",
    "student.etf.bg.ac.rs",
]

ALLOWED_STAFF_DOMAINS = [
    "fon.bg.ac.rs",
    "etf.bg.ac.rs",
]

def get_domain(email: str) -> str:
    return email.split("@")[1].lower()

def is_student_email(email: str) -> bool:
    return get_domain(email) in ALLOWED_STUDENT_DOMAINS

def is_staff_email(email: str) -> bool:
    return get_domain(email) in ALLOWED_STAFF_DOMAINS

def validate_email_domain(email: str) -> None:
    domain = get_domain(email)
    allowed = ALLOWED_STUDENT_DOMAINS + ALLOWED_STAFF_DOMAINS
    if domain not in allowed:
        raise ValueError(f"Email domen '{domain}' nije dozvoljen.")
```

- Studenti se registruju sami → uloga se automatski postavlja na `STUDENT`
- Profesori/asistenti/admini → kreiraju ih samo ADMIN korisnici ručno
- Nema javne registracije za staff

---

## 5. RBAC ULOGE I PERMISIJE

```python
from enum import Enum

class UserRole(str, Enum):
    STUDENT = "STUDENT"
    ASISTENT = "ASISTENT"
    PROFESOR = "PROFESOR"
    ADMIN = "ADMIN"
```

| Radnja | STUDENT | ASISTENT | PROFESOR | ADMIN |
|--------|---------|----------|----------|-------|
| Registracija | ✅ (auto) | ❌ | ❌ | ❌ |
| Zakazivanje termina | ✅ | ❌ | ❌ | ❌ |
| Odobravanje termina | ❌ | ✅ (dodeljen predmet) | ✅ | ❌ |
| Delegiranje | ❌ | ❌ | ✅ | ❌ |
| CRM beleške | ❌ | ✅ (čita+piše) | ✅ | ❌ |
| Availability slotovi | ❌ | ❌ | ✅ | ❌ |
| CRUD korisnika | ❌ | ❌ | ❌ | ✅ |
| Impersonacija | ❌ | ❌ | ❌ | ✅ |
| Broadcast | ❌ | ❌ | ❌ | ✅ |
| Zahtevi za dokumente | ✅ (podnosi) | ❌ | ❌ | ✅ (obrađuje) |
| Audit log | ❌ | ❌ | ❌ | ✅ |

---

## 6. REDIS LOCKING — IMPLEMENTACIJA

```python
# backend/app/services/booking.py
# Koristiti Lua skriptu za atomičan lock:

LOCK_SCRIPT = """
if redis.call("exists", KEYS[1]) == 0 then
    redis.call("setex", KEYS[1], ARGV[1], ARGV[2])
    return 1
end
return 0
"""

async def acquire_slot_lock(redis, slot_id: str, user_id: str, ttl: int = 30) -> bool:
    result = await redis.eval(LOCK_SCRIPT, 1, f"slot:lock:{slot_id}", ttl, user_id)
    return result == 1
```

**Pravilo**: Uvek pokušaj lock → ako ne uspe → vrati 409 Conflict → frontend prikazuje "Slot je upravo zauzet, pokušajte ponovo"

---

## 7. DOCUMENT REQUESTS — TOK

```
Student → POST /api/v1/students/document-requests
         (document_type, note)

Admin inbox → GET /api/v1/admin/document-requests?status=PENDING

Admin odobrava → POST /api/v1/admin/document-requests/{id}/approve
                 body: { pickup_date: "2025-06-10", admin_note: "Soба 12, Palata nauke" }

Student dobija email + in-app notifikaciju:
  "Vaš zahtev za [TIP] je odobren.
   Dokument možete preuzeti [DATUM] u [NAPOMENA]."

Admin označava preuzeto → POST /api/v1/admin/document-requests/{id}/complete
```

---

## 8. STRUKTURA FAJLOVA — KONVENCIJE

### Backend
```
app/api/v1/{module}.py          — Router + endpoint funkcije (thin layer)
app/services/{module}_service.py — Sva business logika
app/models/{entity}.py           — SQLAlchemy modeli (jedan model = jedan fajl)
app/schemas/{entity}.py          — Pydantic šeme (Request, Response, Create, Update)
app/tasks/{task_name}.py         — Celery taskovi
app/core/dependencies.py         — Reusable FastAPI Dependencies
```

### Frontend
```
app/(route-group)/page.tsx          — Page komponente
app/(route-group)/layout.tsx        — Layout za grupu
components/{feature}/               — Feature-specifične komponente
components/ui/                      — Shadcn/ui komponente (ne menjati)
lib/api/                            — API pozivi grupisani po feature-u
lib/stores/                         — Zustand store-ovi
lib/hooks/                          — Custom React hooks
types/                              — TypeScript tipovi (usklađeni sa Pydantic šemama)
```

---

## 9. NAMING CONVENTIONS

| Kontekst | Konvencija | Primer |
|---------|-----------|--------|
| Python fajlovi | snake_case | `booking_service.py` |
| Python klase | PascalCase | `AppointmentCreate` |
| Python funkcije | snake_case | `get_current_user` |
| TypeScript fajlovi | kebab-case | `booking-calendar.tsx` |
| React komponente | PascalCase | `BookingCalendar` |
| TypeScript tipovi | PascalCase | `AppointmentResponse` |
| DB tabele | snake_case plural | `availability_slots` |
| DB kolone | snake_case | `created_at` |
| API endpoints | kebab-case | `/document-requests` |
| Env varijable | SCREAMING_SNAKE_CASE | `DATABASE_URL` |

---

## 10. ŠABLONI ZA ČESTE TASKOVE

### Novi backend endpoint
```python
# 1. Dodaj Pydantic šemu u app/schemas/{entity}.py
# 2. Dodaj service metodu u app/services/{entity}_service.py
# 3. Dodaj router endpoint u app/api/v1/{module}.py
# 4. Dodaj Alembic migraciju ako je potrebna promena šeme
# 5. Dodaj test u tests/test_{module}.py
```

### Nova frontend stranica
```
# 1. Kreiraj app/(group)/nova-stranica/page.tsx
# 2. Dodaj API pozive u lib/api/{feature}.ts
# 3. Dodaj TypeScript tipove u types/{feature}.ts
# 4. Dodaj TanStack Query hook u lib/hooks/use{Feature}.ts
# 5. Dodaj route u middleware.ts ako je zaštićena
```

### Nova Celery notifikacija
```python
# 1. Definiši task u app/tasks/notifications.py
# 2. Email template u app/templates/emails/{template_name}.html
# 3. Pozovi task.delay() iz service-a (ne iz endpoint-a direktno)
```

---

## 11. ZABRANJENA PONAŠANJA

❌ **Ne koristiti** `localStorage` ili `sessionStorage` za JWT tokene  
❌ **Ne koristiti** raw SQL — samo SQLAlchemy ORM  
❌ **Ne dozvoliti** registraciju sa emailom izvan whitelist domena  
❌ **Ne vraćati** hashed_password u bilo kom API response-u  
❌ **Ne koristiti** `pages/` direktorijum — samo App Router  
❌ **Ne implementirati** Keycloak u V1 — to je V2 feature  
❌ **Ne koristiti** synchronous SQLAlchemy — sve mora biti async  
❌ **Ne slati** email direktno iz endpoint funkcije — uvek Celery task  
❌ **Ne dozvoliti** pristup CRM beleškama korisnicima sa STUDENT ulogom  

---

## 12. ČESTE GREŠKE I REŠENJA

**Problem**: `422 Unprocessable Entity` pri registraciji  
**Uzrok**: Email ne prolazi domen validaciju  
**Rešenje**: Proveri `ALLOWED_STUDENT_DOMAINS` i `ALLOWED_STAFF_DOMAINS`

**Problem**: Double booking se dešava  
**Uzrok**: Redis lock nije atomičan ili TTL je istekao  
**Rešenje**: Koristiti Lua skriptu iz sekcije 6, ne `SET NX` + `EXPIRE` kao separate komande

**Problem**: WebSocket konekcija se gubi  
**Uzrok**: JWT token je istekao tokom WebSocket sesije  
**Rešenje**: Validacija tokena pri handshake-u, ne pri svakoj poruci; klijent refreshuje token pre WSS konekcije

**Problem**: FullCalendar ne prikazuje slobodne slotove u realnom vremenu  
**Uzrok**: TanStack Query cache je stale  
**Rešenje**: `refetchInterval: 30000` na slot query, ili WebSocket event za invalidaciju cache-a

---

## 13. REFERENTNI DOKUMENTI

- `docs/PRD_Studentska_Platforma.md` — Poslovni zahtevi i UX pravila
- `docs/Arhitektura_i_Tehnoloski_Stek.md` — Tehničke odluke i razlozi
- `docs/copilot_plan_prompt.md` — Detaljan razvojni plan, DB šema, API spec
- Swagger UI (lokalno): `http://localhost:8000/docs`
- MinIO Console (lokalno): `http://localhost:9001`

---

*Ovaj fajl ažuriraju oba developera. Pri svakoj promeni arhitekture ili konvencija, ažuriraj ovaj fajl u istom PR-u.*
