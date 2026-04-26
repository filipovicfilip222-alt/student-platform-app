"""admin_user_service.py — Admin CRUD nad korisnicima (Faza 4.3).

Sav business code za:

    GET   /api/v1/admin/users
    GET   /api/v1/admin/users/{id}
    POST  /api/v1/admin/users
    PATCH /api/v1/admin/users/{id}
    POST  /api/v1/admin/users/{id}/deactivate
    POST  /api/v1/admin/users/bulk-import/preview
    POST  /api/v1/admin/users/bulk-import/confirm

Bulk import je SAMO za studente (whitelist domeni
``*@student.fon.bg.ac.rs`` / ``*@student.etf.bg.ac.rs``); profesore i
admine kreira admin POJEDINAČNO preko ``POST /users``.

Welcome email (admin-created) ide kroz Celery — `core.email
.send_welcome_email_with_reset_link` koji koristi postojeći
``/reset-password?token=...`` URL sa TTL=7d (config:
``WELCOME_RESET_TOKEN_TTL_DAYS``). Time se reuse-uje postojeći
password-reset flow umesto pravljenja paralelnog (CLAUDE.md §11 +
CURRENT_STATE2 §6.17).
"""

from __future__ import annotations

import csv
import io
import re
import secrets
from collections import Counter
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_welcome_email_with_reset_link
from app.core.security import (
    hash_password,
    is_staff_email,
    is_student_email,
    validate_email_domain,
)
from app.models.enums import Faculty, UserRole
from app.models.professor import Professor
from app.models.user import User
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserUpdate,
    BulkImportPreview,
    BulkImportResult,
    BulkImportRow,
)
from app.services.auth_service import (
    _create_reset_token,
    _faculty_from_email,
    _get_user_by_email,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _validate_role_domain_match(role: UserRole, email: str) -> None:
    """Enforce email-whitelist ↔ role mapping.

    PRD §1.1 + CLAUDE.md §4: studenti samo na ``*@student.{fon,etf}.bg.ac.rs``,
    staff (PROFESOR/ASISTENT/ADMIN) samo na ``*@{fon,etf}.bg.ac.rs``.
    """
    try:
        validate_email_domain(email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    if role == UserRole.STUDENT and not is_student_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "STUDENT mora imati email iz studentskog domena "
                "(*@student.fon.bg.ac.rs ili *@student.etf.bg.ac.rs)."
            ),
        )
    if role != UserRole.STUDENT and not is_staff_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"{role.value} mora imati email iz staff domena "
                "(*@fon.bg.ac.rs ili *@etf.bg.ac.rs)."
            ),
        )


async def _ensure_email_unique(db: AsyncSession, email: str) -> None:
    if await _get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Korisnik sa ovom email adresom već postoji.",
        )


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Korisnik nije pronađen.",
        )
    return user


def _send_welcome(user: User, raw_token: str) -> None:
    """Dispatch the welcome email Celery task. Wrapped to keep the call site
    single-line in services. Caller MUST already have committed the user row
    (otherwise the worker may read a row that doesn't exist yet)."""
    send_welcome_email_with_reset_link(
        to_email=user.email,
        first_name=user.first_name,
        reset_token=raw_token,
        ttl_days=settings.WELCOME_RESET_TOKEN_TTL_DAYS,
    )


# ── Public service API ────────────────────────────────────────────────────────


async def list_users(
    db: AsyncSession,
    q: str | None = None,
    role: UserRole | None = None,
    faculty: Faculty | None = None,
) -> list[User]:
    """List users with optional ILIKE search + exact role/faculty filters.

    Frontend (``frontend/lib/api/admin.ts::listUsers``) šalje samo
    ``q``, ``role``, ``faculty`` — bez paginate, bez ``is_active``.
    Vraćamo bare list[User] sortiran po ``created_at DESC``.
    """
    statement = select(User).order_by(User.created_at.desc())

    if role is not None:
        statement = statement.where(User.role == role)
    if faculty is not None:
        statement = statement.where(User.faculty == faculty)
    if q:
        # Admin pretraga koristi isti ``f_unaccent`` wrapper kao student
        # search (migracija 0004) da bi „petrovic" i „petrović" davali
        # istu listu. ``User.email`` je ASCII-only (whitelist domeni
        # ``*@fon.bg.ac.rs``, ``*@etf.bg.ac.rs`` itd.) pa wrapper nema
        # smisla — ostaje plain ILIKE.
        needle = f"%{q.strip()}%"
        unaccent_needle = func.f_unaccent(needle)
        statement = statement.where(
            or_(
                func.f_unaccent(User.first_name).ilike(unaccent_needle),
                func.f_unaccent(User.last_name).ilike(unaccent_needle),
                User.email.ilike(needle),
            )
        )

    result = await db.execute(statement)
    return list(result.scalars().all())


async def get_user(db: AsyncSession, user_id: UUID) -> User:
    return await _get_user_or_404(db, user_id)


async def create_user(db: AsyncSession, payload: AdminUserCreate) -> User:
    """Kreira korisnika (single-user flow, NIJE bulk).

    Hibridni welcome flow (vidi user prompt — pitanje B):
      1. Hash-uje admin-unetu lozinku (frontend ugovor zahteva ``password``).
      2. Kreira ``User`` zapis sa ``is_active=true``.
      3. Za PROFESOR/ASISTENT, kreira default ``Professor`` red (admin posle
         dopuni preko ``/professors/profile``).
      4. Generiše password-reset token TTL=7d.
      5. Posle commit-a pozove Celery welcome email task sa reset linkom.
    """
    email = payload.email.lower()

    _validate_role_domain_match(payload.role, email)
    await _ensure_email_unique(db, email)

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
        faculty=payload.faculty,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # PROFESOR i ASISTENT moraju imati Professor red (FK iz availability_slots,
    # subject_assistants itd.). Default-i su prazni stringovi — admin ih posle
    # dopuni preko PUT /professors/profile.
    if payload.role in (UserRole.PROFESOR, UserRole.ASISTENT):
        prof = Professor(
            user_id=user.id,
            title="",
            department="",
            office=None,
            office_description=None,
            areas_of_interest=[],
        )
        db.add(prof)
        await db.flush()

    raw_token = await _create_reset_token(
        db,
        user,
        ttl_seconds=settings.WELCOME_RESET_TOKEN_TTL_DAYS * 24 * 3600,
    )
    # NOTE: ne commit-ujemo ovde — ``get_db()`` finalizuje transakciju posle
    # endpoint-a (vidi ``backend/app/core/database.py``). Celery
    # ``send_email_task`` ne čita DB (radi samo SMTP), pa nije bitno
    # da li je transakcija commit-ovana pre njegovog pickup-a.
    _send_welcome(user, raw_token)
    return user


async def update_user(
    db: AsyncSession,
    user_id: UUID,
    payload: AdminUserUpdate,
) -> User:
    """Patch only the fields actually provided. Email + password locked
    (frontend ugovor — vidi ``user-form-modal.tsx`` edit mode)."""
    user = await _get_user_or_404(db, user_id)

    data = payload.model_dump(exclude_unset=True)

    # Ako se menja role i ako bi nova kombinacija narušila staff/student
    # whitelist mapping, vrati 422.
    new_role: UserRole | None = data.get("role")
    if new_role is not None and new_role != user.role:
        _validate_role_domain_match(new_role, user.email)

        # Promena STUDENT → PROFESOR/ASISTENT povlači kreiranje Professor reda
        # (ako još ne postoji); povratna promena ostavlja postojeći red u bazi
        # (audit-friendly, FK-i ostaju validni).
        if new_role in (UserRole.PROFESOR, UserRole.ASISTENT):
            existing = await db.execute(
                select(Professor).where(Professor.user_id == user.id)
            )
            if existing.scalar_one_or_none() is None:
                db.add(
                    Professor(
                        user_id=user.id,
                        title="",
                        department="",
                        areas_of_interest=[],
                    )
                )

    for field, value in data.items():
        setattr(user, field, value)

    await db.flush()
    return user


async def deactivate_user(db: AsyncSession, user_id: UUID) -> User:
    """Soft delete — set ``is_active=false`` (CURRENT_STATE2 §4.4 +
    user prompt D).

    Postojeći appointmenti, document_request-i, audit_log-ovi ostaju netaknuti.
    Login flow odbija deaktivirane korisnike sa 403 (vidi
    ``auth_service.login`` + ``dependencies.get_current_user``).
    """
    user = await _get_user_or_404(db, user_id)
    if not user.is_active:
        # Idempotentno — već deaktiviran, vraćamo isti zapis bez side-effecta.
        return user
    user.is_active = False
    await db.flush()
    return user


# ── Bulk import (Faza 4.3) ────────────────────────────────────────────────────
#
# CSV format po PRD §4.1: ``ime, prezime, email, indeks, smer, godina_upisa``
# (UTF-8 sa ili bez BOM; ekstra kolone se ignorišu, fali kolona → 422).
#
# Bulk je SAMO za studente (whitelist domeni). Svaki red:
#   * email mora pripadati ``*@student.fon.bg.ac.rs`` ili
#     ``*@student.etf.bg.ac.rs`` — ostali se odmah klasifikuju kao invalid
#   * ``godina_upisa`` mora biti integer u [2000..tekuća+1] — out-of-range
#     ili non-numeric → invalid
#   * ``indeks`` se validira na NE-prazan string (format dozvoljen relativno
#     liberalan jer se ne persistuje — vidi user prompt pitanje 1)
#   * email koji već postoji u DB-u ili se ponavlja unutar samog CSV-a →
#     duplicates kategorija (ne kreira se)
#
# Confirm endpoint **re-validira** ceo CSV (stateless approach — vidi user
# prompt pitanje C) umesto da koristi Redis ``preview_id``. To je jedini
# način kompatibilan sa frontend-om koji ne pamti preview_id (vidi
# ``frontend/lib/api/admin.ts::bulkImportConfirm``).

_CSV_REQUIRED_HEADERS: tuple[str, ...] = (
    "ime",
    "prezime",
    "email",
    "indeks",
    "smer",
    "godina_upisa",
)


def _decode_csv_bytes(csv_bytes: bytes) -> str:
    """Decode CSV bytes as UTF-8 with optional BOM tolerance.

    Vraća HTTP 422 ako je payload prazan ili nije validan UTF-8.
    """
    if not csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV fajl je prazan.",
        )
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV fajl mora biti UTF-8: {exc}",
        )
    return text


def _validate_headers(fieldnames: list[str] | None) -> None:
    if not fieldnames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV fajl nema header red.",
        )
    normalized = [h.strip().lower() for h in fieldnames]
    missing = [h for h in _CSV_REQUIRED_HEADERS if h not in normalized]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"CSV header je nepotpun. Fale kolone: {', '.join(missing)}. "
                f"Očekivani format: {', '.join(_CSV_REQUIRED_HEADERS)}."
            ),
        )


def _faculty_for_student_email(email: str) -> Faculty | None:
    """Vrati Faculty na osnovu studentskog email domena, ili None ako
    domen nije whitelist-ovan."""
    domain = email.split("@", 1)[1].lower() if "@" in email else ""
    if domain.endswith("student.fon.bg.ac.rs"):
        return Faculty.FON
    if domain.endswith("student.etf.bg.ac.rs"):
        return Faculty.ETF
    return None


def _parse_int(s: str) -> int | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_csv_to_categories(
    text: str,
    existing_emails: set[str],
) -> tuple[list[BulkImportRow], list[BulkImportRow], list[BulkImportRow]]:
    """Parse + kategorisanje CSV reda po pravilima iz docstring-a iznad.

    Vraća (valid, invalid, duplicates).

    Duplikat = email se već nalazi u bazi ILI se ponavlja unutar samog CSV-a.
    Da bi prvo pojavljivanje email-a unutar fajla bilo "valid" a sledeća
    "duplicate", radimo dvopas (prvi pas — Counter, drugi pas — kategorisanje).
    """
    reader = csv.DictReader(io.StringIO(text))
    _validate_headers(reader.fieldnames)

    # Normalize header keys (strip + lowercase) — DictReader čuva original.
    rows_raw: list[tuple[int, dict[str, str]]] = []
    for idx, row in enumerate(reader, start=2):  # red 1 = header
        normalized = {
            (k.strip().lower() if k else ""): (v if v is not None else "")
            for k, v in row.items()
        }
        rows_raw.append((idx, normalized))

    # Brojač email-ova u fajlu (case-insensitive) za detekciju in-file dup-ova.
    email_counter: Counter[str] = Counter()
    for _, r in rows_raw:
        email_lower = r.get("email", "").strip().lower()
        if email_lower:
            email_counter[email_lower] += 1

    seen_in_file: set[str] = set()
    valid: list[BulkImportRow] = []
    invalid: list[BulkImportRow] = []
    duplicates: list[BulkImportRow] = []

    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    for row_no, r in rows_raw:
        errors: list[str] = []
        email_raw = r.get("email", "").strip()
        first_name = r.get("ime", "").strip()
        last_name = r.get("prezime", "").strip()
        indeks = r.get("indeks", "").strip()
        smer = r.get("smer", "").strip()
        godina_raw = r.get("godina_upisa", "").strip()

        email = email_raw.lower()
        faculty = _faculty_for_student_email(email)

        # Pravila — kumulativno skupljamo greške zbog UI feedback-a.
        if not first_name:
            errors.append("ime je obavezno")
        if not last_name:
            errors.append("prezime je obavezno")
        if not email_raw:
            errors.append("email je obavezan")
        elif not email_re.match(email):
            errors.append("email nije validnog formata")
        elif faculty is None:
            errors.append(
                "email mora biti studentski "
                "(*@student.fon.bg.ac.rs ili *@student.etf.bg.ac.rs)"
            )
        if not indeks:
            errors.append("indeks je obavezan")
        if not smer:
            errors.append("smer je obavezan")
        godina = _parse_int(godina_raw)
        if godina is None:
            errors.append("godina_upisa mora biti broj")
        elif godina < 2000 or godina > 2100:
            errors.append("godina_upisa mora biti u opsegu 2000..2100")

        # Faculty fallback za invalid red bez whitelist domena — koristimo
        # FON kao placeholder jer schema zahteva non-null Faculty (vidi
        # CURRENT_STATE2 §6.17 — student-specific fields se NE persistuju u
        # 4.3, pa fallback ne ostavlja loš trag u bazi).
        bir_faculty = faculty or Faculty.FON

        bir = BulkImportRow(
            row_number=row_no,
            email=email_raw,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.STUDENT,
            faculty=bir_faculty,
            errors=errors,
        )

        if errors:
            invalid.append(bir)
            continue

        # Duplicate detection: in-DB ili in-file (drugi+ pojavak).
        if email in existing_emails:
            bir.errors.append("email već postoji u sistemu")
            duplicates.append(bir)
            continue
        if email_counter.get(email, 0) > 1 and email in seen_in_file:
            bir.errors.append("email se ponavlja u CSV fajlu")
            duplicates.append(bir)
            continue

        seen_in_file.add(email)
        valid.append(bir)

    return valid, invalid, duplicates


async def _existing_emails(db: AsyncSession) -> set[str]:
    result = await db.execute(select(User.email))
    return {e.lower() for e in result.scalars().all()}


async def bulk_import_preview(
    db: AsyncSession,
    csv_bytes: bytes,
) -> BulkImportPreview:
    """Parse + klasifikacija bez ikakvog write-a u DB."""
    text = _decode_csv_bytes(csv_bytes)
    existing = await _existing_emails(db)
    valid, invalid, duplicates = _parse_csv_to_categories(text, existing)
    return BulkImportPreview(
        valid_rows=valid,
        invalid_rows=invalid,
        duplicates=duplicates,
        total=len(valid) + len(invalid) + len(duplicates),
    )


async def bulk_import_confirm(
    db: AsyncSession,
    csv_bytes: bytes,
) -> BulkImportResult:
    """Re-parse CSV + kreiraj SAMO valid_rows kao studente.

    Transakcioni princip — sav posao se odvija u jednoj DB transakciji
    (commit-uje se na izlasku iz endpoint-a kroz ``get_db``); ako jedan
    insert padne, ceo bulk se rollback-uje preko mehanizma podignute
    HTTPException u SQLAlchemy session-u (``get_db`` rollback grana).
    Zato je ``failed`` polje u praksi 0 u happy path-u — vidi schema docstring.

    Welcome email-ovi se dispatch-uju Celery task-ovima TEK NAKON
    ``await db.flush()`` za sve redove. Pošto ``send_email_task`` ne čita
    DB (vidi ``email.py``), redosled je benigni.
    """
    text = _decode_csv_bytes(csv_bytes)
    existing = await _existing_emails(db)
    valid, invalid, duplicates = _parse_csv_to_categories(text, existing)

    if not valid:
        # Frontend prikazuje ovo kao toast — admin treba da vidi "ništa nije
        # uvezeno" umesto false-positive 200 OK.
        return BulkImportResult(
            created=0,
            skipped=len(invalid) + len(duplicates),
            failed=0,
        )

    created_users_with_tokens: list[tuple[User, str]] = []
    for row in valid:
        email = row.email.lower()
        # Random temp lozinka — admin nije unosio password u bulk flow-u, a
        # student će postaviti svoju kroz reset link iz welcome email-a.
        temp_password = secrets.token_urlsafe(16)
        user = User(
            email=email,
            hashed_password=hash_password(temp_password),
            first_name=row.first_name,
            last_name=row.last_name,
            role=UserRole.STUDENT,
            faculty=row.faculty,
            is_active=True,
        )
        db.add(user)
        await db.flush()  # podigni UUID + uhvati IntegrityError rano

        raw_token = await _create_reset_token(
            db,
            user,
            ttl_seconds=settings.WELCOME_RESET_TOKEN_TTL_DAYS * 24 * 3600,
        )
        created_users_with_tokens.append((user, raw_token))

    # Tek SADA dispatch-uj welcome email-ove — ako bilo koji insert iznad
    # padne, exception se propagira pre ovog redosleda i ``get_db`` rollback
    # grana poništava sve, pa nećemo poslati email za nepostojeći nalog.
    for u, tok in created_users_with_tokens:
        _send_welcome(u, tok)

    return BulkImportResult(
        created=len(created_users_with_tokens),
        skipped=len(invalid) + len(duplicates),
        failed=0,
    )
