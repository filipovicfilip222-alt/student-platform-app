# Arhitektura i Tehnološki Stek
## Platforma za upravljanje univerzitetskim konsultacijama i komunikacijom
## FON & ETF Univerzitet u Beogradu

**Status:** Odobreno ✅  
**Verzija:** 2.0  
**Poslednja izmena:** April 2025  

---

## Sadržaj

1. [Pregled Arhitekture](#1-pregled-arhitekture)
2. [Backend API — FastAPI (Python)](#2-backend-api--fastapi-python)
3. [Relaciona Baza — PostgreSQL](#3-relaciona-baza--postgresql)
4. [Keš i State Management — Redis](#4-keš-i-state-management--redis)
5. [Frontend i PWA — Next.js](#5-frontend-i-pwa--nextjs)
6. [Autentifikacija — V1 JWT (Keycloak u V2)](#6-autentifikacija--v1-jwt-keycloak-u-v2)
7. [File Storage — MinIO](#7-file-storage--minio)
8. [Deployment Arhitektura](#8-deployment-arhitektura)
9. [Dijagram Komunikacije između Servisa](#9-dijagram-komunikacije-između-servisa)

---

## 1. Pregled Arhitekture

```
┌─────────────────────────────────────────────────────────┐
│                    KLIJENTI (Browser / PWA)              │
│              Next.js 14 + Tailwind + Shadcn/ui           │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS / WSS
┌────────────────────────▼────────────────────────────────┐
│                   Nginx Reverse Proxy                    │
│              (SSL Termination, CORS, Rate Limit)         │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────▼──────────────────────────────┐
              │         FastAPI Backend                  │
              │   REST API + WebSocket endpoints         │
              │   JWT Auth Middleware (V1)               │
              └────┬──────────┬──────────┬──────────────┘
                   │          │           │
           ┌───────▼──┐ ┌─────▼───┐ ┌───▼─────┐
           │PostgreSQL│ │  Redis  │ │  MinIO  │
           │+ pgvector│ │ (Cache) │ │ (Files) │
           └──────────┘ └─────────┘ └─────────┘
```

> **V1 arhitektura:** Keycloak je izostavljen iz prve verzije. Autentifikacija se vrši direktnim JWT tokenima. Keycloak se uvodi u V2 kao enterprise SSO nadogradnja.

---

## 2. Backend API — FastAPI (Python)

**Odabrana verzija:** FastAPI 0.111+ sa Python 3.12+

### Ključne biblioteke

| Biblioteka | Namena |
|-----------|--------|
| `sqlalchemy[asyncio]` + `asyncpg` | Async ORM za PostgreSQL |
| `alembic` | Migracije baze |
| `redis[asyncio]` | Async Redis klijent |
| `minio` | MinIO S3-compatible klijent |
| `python-jose[cryptography]` | JWT generisanje i validacija (V1 auth) |
| `passlib[bcrypt]` | Hash-ovanje lozinki |
| `python-multipart` | File upload podrška |
| `celery[redis]` | Background taskovi (email, cron) |
| `pydantic-settings` | Type-safe env varijable |
| `pytest-asyncio` | Async testovi |
| `emails` ili `fastapi-mail` | Slanje emailova |

### Razlozi za odabir FastAPI
- **Performanse i asinhronost** — Starlette + Pydantic, async/await za sve I/O operacije
- **Auto-generisana OpenAPI dokumentacija** — Swagger UI za frontend/backend sinhronizaciju
- **Native WebSocket** — In-App Chat i real-time notifikacije

---

## 3. Relaciona Baza — PostgreSQL

**Odabrana verzija:** PostgreSQL 16 sa `pgvector` ekstenzijom

### Razlozi za odabir
- **ACID** — Kritično za sistem zakazivanja (bez double booking)
- **pgvector** — Priprema za V2 semantičku pretragu bez zasebne vektorske baze
- **JSONB** — Čuvanje recurring rules konfiguracije
- **TSTZRANGE** — Nativni intervali za availability slots
- **Row-Level Security** — Zaštita CRM beleški i audit loga

---

## 4. Keš i State Management — Redis

**Odabrana verzija:** Redis 7 (self-hosted)

### Redis Key Namespace

| Namespace | Tip | TTL | Opis |
|-----------|-----|-----|------|
| `slot:lock:{slot_id}` | String | 30s | Pessimistic lock pri zakazivanju |
| `waitlist:{slot_id}` | Sorted Set | ∞ | Lista čekanja (score = Unix timestamp) |
| `chat:session:{appointment_id}` | Hash | 25h | WebSocket sesije za chat |
| `notif:unread:{user_id}` | Counter | ∞ | Broj nepročitanih notifikacija |
| `strike:check:{appointment_id}` | String | 90min | Scheduled no-show provera |
| `refresh_token:{user_id}` | String | 7 dana | JWT refresh token store |

### Namene
- **Pessimistic locking** — Sprečavanje double booking (atomičan SET NX Lua skriptom)
- **Waitlist queue** — Sorted Sets, `ZPOPMIN` za FIFO redosled
- **WebSocket Pub/Sub** — Chat i real-time notifikacije između servera
- **Celery broker** — Background taskovi (email slanje, no-show cron)

---

## 5. Frontend i PWA — Next.js

**Odabrana verzija:** Next.js 14 (App Router) + Tailwind CSS + Shadcn/ui

### Ključne biblioteke

| Biblioteka | Namena |
|-----------|--------|
| `@fullcalendar/react` | Kalendarski UI |
| `shadcn/ui` | UI komponente |
| `tailwindcss` | Utility-first CSS |
| `react-query` (TanStack Query) | Server state, caching |
| `react-hook-form` + `zod` | Forme sa validacijom |
| `socket.io-client` | WebSocket klijent |
| `next-pwa` | PWA + service worker |
| `react-dropzone` | File upload UI |
| `axios` ili `ky` | HTTP klijent sa interceptorima za JWT |
| `zustand` | Globalni client state (auth, notifikacije) |

### Auth na frontendu (V1)
- JWT access token čuvan u **memory** (zustand store) — ne u localStorage radi sigurnosti
- Refresh token čuvan u **httpOnly cookie**
- Axios interceptor za automatski refresh tokena
- Protected routes putem Next.js middleware

---

## 6. Autentifikacija — V1 JWT (Keycloak u V2)

> **Ovo je privremeno rešenje za MVP fazu.** Keycloak se uvodi u V2.

### V1 implementacija

```
POST /api/v1/auth/register   — Registracija (validacija email domene)
POST /api/v1/auth/login      — Login, vraća access + refresh token
POST /api/v1/auth/refresh    — Obnovi access token
POST /api/v1/auth/logout     — Poništi refresh token u Redis-u
POST /api/v1/auth/forgot-password  — Slanje reset linka
POST /api/v1/auth/reset-password   — Postavljanje nove lozinke
```

### Email domen whitelist
```python
ALLOWED_STUDENT_DOMAINS = [
    "student.fon.bg.ac.rs",
    "student.etf.bg.ac.rs"
]
ALLOWED_STAFF_DOMAINS = [
    "fon.bg.ac.rs",
    "etf.bg.ac.rs"
]
```

### Uloga se određuje automatski
- Email sa `@student.*` domenom → uloga `STUDENT`
- Email sa `@fon.bg.ac.rs` ili `@etf.bg.ac.rs` → uloga se manuelno dodeljuje od strane ADMIN-a pri kreiranju naloga (PROFESOR / ASISTENT / ADMIN)

### JWT Payload
```json
{
  "sub": "user_uuid",
  "email": "ime@student.fon.bg.ac.rs",
  "role": "STUDENT",
  "faculty": "FON",
  "exp": 1234567890
}
```

### V2 plan — Keycloak migracija
- Realm setup za FON i ETF
- Identity Providers: G-Suite OAuth2, Microsoft 365 OIDC
- User Federation: LDAP / Active Directory
- FastAPI middleware se menja: umesto `python-jose` validacije, koristi Keycloak JWKS endpoint
- Frontend: zamena custom JWT logike sa `next-auth` + Keycloak adapterom

---

## 7. File Storage — MinIO

**Odabrana verzija:** MinIO AGPL (self-hosted)

### Bucket Struktura
```
minio-buckets/
├── appointment-files/
│   └── {appointment_id}/
│       └── {filename}
├── professor-avatars/
├── bulk-imports/           # CSV fajlovi (privremeno)
└── document-requests/      # Dokumenti vezani za zahteve studentske službe
```

### Pre-signed URL-ovi
- Fajlovi se ne prolaze kroz FastAPI server
- MinIO generiše vremenski ograničene URL-ove za download (TTL: 1h)

---

## 8. Deployment Arhitektura

### Docker Compose Servisi

```yaml
services:
  nginx:          # Reverse proxy, SSL termination
  fastapi:        # Backend API
  celery-worker:  # Background tasks (email, cron)
  celery-beat:    # Cron scheduler (no-show provere, waitlist)
  nextjs:         # Frontend
  postgres:       # Baza podataka
  redis:          # Keš, queue, pub/sub
  minio:          # Object storage
  # keycloak:     # ZAKOMENTARISANO — dodaje se u V2
```

### Mrežna izolacija
- Svi servisi unutar Docker interne mreže
- Javno dostupni samo: Nginx (443) i MinIO console za admin (opciono, interni)
- PostgreSQL i Redis **nisu izloženi** van Docker mreže

---

## 9. Dijagram Komunikacije između Servisa

```
[Browser / PWA]
      │
      │ HTTPS (REST + WebSocket)
      ▼
   [Nginx]
      │
      ├──► [Next.js SSR]         stranice, SSR rendering
      │
      └──► [FastAPI API]
               │
               ├──► JWT Validacija (lokalna, V1)
               │
               ├──► [PostgreSQL]   persistentni podaci
               │        └──► pgvector (V2 semantic search)
               │
               ├──► [Redis]        locking, queue, pub/sub, cache
               │        └──► Celery Worker (email, cron)
               │
               └──► [MinIO]        file storage (pre-signed URLs)
```

---

## Zaključak

| Sloj | Tehnologija | Status |
|------|-------------|--------|
| Backend | FastAPI (Python 3.12) | ✅ V1 |
| Baza | PostgreSQL 16 + pgvector | ✅ V1 |
| Keš | Redis 7 | ✅ V1 |
| Frontend | Next.js 14 + Tailwind + Shadcn/ui | ✅ V1 |
| Auth | JWT (bcrypt + python-jose) | ✅ V1 |
| Auth (upgrade) | Keycloak 24 (on-premise) | 🔜 V2 |
| Storage | MinIO (self-hosted) | ✅ V1 |
| Deployment | Docker + Docker Compose + Nginx | ✅ V1 |

---

*Dokument je deo `docs/` foldera projekta i služi kao jedini source of truth za tehničku arhitekturu.*
