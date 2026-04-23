# Onboarding — Lokalno pokretanje projekta

## Preduslov: alati koje moraš imati instalirane

| Alat | Verzija | Proveri |
|------|---------|---------|
| **Git** | bilo koja | `git --version` |
| **Docker Desktop** | latest | `docker --version` |
| **Python** | 3.12+ | `python --version` |
| **Node.js** | 20+ | `node --version` |
| **npm** | 10+ | `npm --version` |

> Docker Desktop mora biti **pokrenut** (ikonica u systray) pre nego što uradiš bilo šta.

---

## Korak 1 — Kloniranje repozitorijuma

```bash
git clone https://github.com/filipovicfilip222-alt/student-platform-app.git
cd student-platform-app
```

---

## Korak 2 — Kreiranje `.env` fajlova

### 2a. Backend `.env`

```bash
cd backend
copy .env.example .env
```

Otvori `backend/.env` i izmeni sledeće:

```env
# Ove vrednosti rade odmah lokalno — ne moraš ništa menjati za osnovno pokretanje
DATABASE_URL=postgresql+asyncpg://studentska:studentska_pass@localhost:5432/studentska_platforma
REDIS_URL=redis://:redis_pass@localhost:6379/0
CELERY_BROKER_URL=redis://:redis_pass@localhost:6379/1
CELERY_RESULT_BACKEND=redis://:redis_pass@localhost:6379/2

# OVO MORAŠ PROMENITI — generiši random string:
SECRET_KEY=upisi-neki-dugacki-random-string-od-minimum-32-karaktera-ovde

# SMTP — ostavi prazno, email neće raditi ali sve ostalo hoće
SMTP_PASSWORD=
```

> **Važno:** kad se backend pokreće **lokalno** (ne u Dockeru), hostname baze je `localhost`, ne `postgres`.

### 2b. Frontend `.env.local`

```bash
cd ../frontend
copy .env.example .env.local
```

`frontend/.env.local` možeš ostaviti potpuno neizmenjenim — defaultne vrednosti rade za lokalni razvoj.

---

## Korak 3 — Pokretanje infrastrukture (Docker)

Infra servisi (PostgreSQL, Redis, MinIO) se pokreću u Dockeru. Backend i frontend **NE** pokrećemo u Dockeru tokom razvoja.

```bash
cd ../infra
docker compose up -d
```

Ovo pokreće:
- **PostgreSQL 16** → `localhost:5432`
- **Redis 7** → `localhost:6379`
- **MinIO** (storage) → `localhost:9000` (API), `localhost:9001` (web konzola)
- **Nginx** → `localhost:80`

Provjeri da li su svi kontejneri `healthy`:

```bash
docker compose ps
```

Svi servisi treba da imaju status `running` ili `healthy`. Sačekaj ~30 sekundi ako su tek startovani.

---

## Korak 4 — Backend setup

### 4a. Virtuelno okruženje

```bash
cd ../backend
python -m venv .venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Mac/Linux:**
```bash
source .venv/bin/activate
```

### 4b. Instalacija biblioteka

```bash
pip install -r requirements.txt
```

### 4c. Migracije baze (Alembic)

Ovo kreira sve tabele u PostgreSQL bazi:

```bash
alembic upgrade head
```

Treba da vidiš output koji se završava sa:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 20260423_0001, initial schema
```

### 4d. Seed baze (početni podaci)

Ovo ubacuje testne profesore, asistente i admin korisnike:

```bash
python ../scripts/seed_db.py
```

### 4e. Pokretanje backend servera

```bash
uvicorn app.main:app --reload --port 8000
```

Provera — otvori u browseru: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

Treba da vrati:
```json
{"status": "ok"}
```

Swagger dokumentacija API-ja: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Korak 5 — Frontend setup

Otvori **novi terminal** (backend neka i dalje radi u prvom).

```bash
cd frontend
npm install
npm run dev
```

Aplikacija je dostupna na: [http://localhost:3000](http://localhost:3000)

---

## Korak 6 — Verifikacija

| URL | Šta je |
|-----|--------|
| http://localhost:3000 | Frontend (Next.js) |
| http://localhost:3000/login | Login stranica |
| http://localhost:3000/register | Register stranica |
| http://localhost:8000/docs | Backend Swagger UI |
| http://localhost:8000/api/v1/health | Health check |
| http://localhost:9001 | MinIO konzola (user: `minioadmin`, pass: `minioadmin`) |

---

## Seed korisnici (za testiranje)

Ovi korisnici se kreiraju po `seed_db.py`:

| Email | Lozinka | Uloga |
|-------|---------|-------|
| `admin@fon.bg.ac.rs` | `Admin123!` | ADMIN |
| `admin2@etf.bg.ac.rs` | `Admin123!` | ADMIN |
| `prof.jovic@fon.bg.ac.rs` | `Prof123!` | PROFESOR |
| `prof.petrovic@fon.bg.ac.rs` | `Prof123!` | PROFESOR |
| `prof.nikolic@etf.bg.ac.rs` | `Prof123!` | PROFESOR |
| `asist.markovic@fon.bg.ac.rs` | `Prof123!` | ASISTENT |

> Studenti se **registruju sami** koristeći `@student.fon.bg.ac.rs` ili `@student.etf.bg.ac.rs` email.

---

## Česti problemi

### `alembic upgrade head` puca sa "connection refused"
Docker nije pokrenut ili PostgreSQL kontejner još nije `healthy`. Provjeri:
```bash
docker compose ps
```

### `uvicorn` kaže "ModuleNotFoundError"
Nisi aktivirao virtuelno okruženje. Ponovi Korak 4a.

### `npm run dev` kaže "Cannot find module"
Nisi pokrenuo `npm install`. Ponovi Korak 5.

### Port 5432/6379/80 je već zauzet
Imaš lokalno instaliran PostgreSQL/Redis/Nginx koji radi na istim portovima. Zaustavi ih ili promeni portove u `infra/docker-compose.yml`.

### PowerShell kaže "running scripts is disabled"
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Struktura projekta (ukratko)

```
student-platform-app/
├── backend/          ← FastAPI (Python 3.12)
├── frontend/         ← Next.js 14 (TypeScript)
├── infra/            ← Docker Compose, Nginx, MinIO config
├── scripts/          ← seed_db.py, migrate.sh
├── docs/             ← PRD, arhitektura, plan
├── CLAUDE.md         ← pravila razvoja (obavezno pročitati!)
└── CURRENT_STATE.md  ← šta je implementirano, šta nije
```

Detaljan opis svega implementiranog je u `CURRENT_STATE.md`.
