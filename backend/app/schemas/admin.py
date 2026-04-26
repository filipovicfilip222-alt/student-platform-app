"""Admin Pydantic schemas (Faza 4.3).

Source of truth: ``frontend/types/admin.ts`` (zaključan TS ugovor — vidi
CLAUDE.md §17 / CURRENT_STATE2 §6.17). Polja moraju da se poklope red-za-red.

REST endpointi (``frontend/lib/api/admin.ts``):

    GET   /api/v1/admin/users?q=&role=&faculty=          → list[AdminUserResponse]
    GET   /api/v1/admin/users/{id}                       → AdminUserResponse
    POST  /api/v1/admin/users                            → AdminUserResponse
    PATCH /api/v1/admin/users/{id}                       → AdminUserResponse
    POST  /api/v1/admin/users/{id}/deactivate            → MessageResponse
    POST  /api/v1/admin/users/bulk-import/preview (CSV)  → BulkImportPreview
    POST  /api/v1/admin/users/bulk-import/confirm (CSV)  → BulkImportResult

Bulk CSV format po PRD §4.1: ``ime, prezime, email, indeks, smer,
godina_upisa`` (UTF-8, BOM-tolerant). Bulk je ISKLJUČIVO za studente
(whitelist domeni ``*@student.fon.bg.ac.rs`` / ``*@student.etf.bg.ac.rs``).
Profesori/asistenti/admini se kreiraju POJEDINAČNO preko ``POST /users``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import Faculty, UserRole


# ── User CRUD shapes ──────────────────────────────────────────────────────────

class AdminUserResponse(BaseModel):
    """Mirror of ``frontend/types/admin.ts::AdminUserResponse`` (= alias na
    ``UserResponse`` iz ``frontend/types/auth.ts``)."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    faculty: Faculty
    is_active: bool
    is_verified: bool
    profile_image_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserCreate(BaseModel):
    """Mirror of ``frontend/types/admin.ts::AdminUserCreate``.

    ``password`` je **obavezan** u TS ugovoru (form min_length=8) — admin ga
    unosi ručno i hash-ujemo ga (vidi service: hibridni welcome flow šalje
    *uz to* reset link sa TTL=7d preko Celery task-a; admin može i usmeno
    saopštiti privremenu lozinku, kao backup).
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: UserRole
    faculty: Faculty

    @field_validator("first_name", "last_name", "email", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


class AdminUserUpdate(BaseModel):
    """Mirror of ``frontend/types/admin.ts::AdminUserUpdate`` —
    ``Partial<{first_name, last_name, role, faculty}> & {is_active?: boolean}``.

    Email + password su LOCKED u edit mode-u (vidi
    ``frontend/components/admin/user-form-modal.tsx``).
    Password reset ide kroz postojeći ``/auth/forgot-password`` flow.
    """

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: UserRole | None = None
    faculty: Faculty | None = None
    is_active: bool | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() if isinstance(v, str) else v


# ── Bulk CSV import shapes ────────────────────────────────────────────────────

class BulkImportRow(BaseModel):
    """Mirror of ``frontend/types/admin.ts::BulkImportRow``.

    Backend uvek puni:
      - ``role = "STUDENT"`` (bulk je samo za studente)
      - ``faculty`` izveden iz email domena (FON za ``*@student.fon.bg.ac.rs``,
        ETF za ``*@student.etf.bg.ac.rs``)
      - ``password`` se NE puni (welcome flow generiše random temp)
      - ``errors`` lista user-friendly poruka za UI (PR; kategorisano:
        invalid → invalid_rows, dup → duplicates, OK → valid_rows)
    """

    row_number: int = Field(ge=1)
    email: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.STUDENT
    faculty: Faculty
    password: str | None = None
    errors: list[str] = Field(default_factory=list)


class BulkImportPreview(BaseModel):
    """Mirror of ``frontend/types/admin.ts::BulkImportPreview``."""

    valid_rows: list[BulkImportRow]
    invalid_rows: list[BulkImportRow]
    duplicates: list[BulkImportRow]
    total: int = Field(ge=0)


class BulkImportResult(BaseModel):
    """Mirror of ``frontend/types/admin.ts::BulkImportResult``.

    Confirm endpoint koristi savepoint princip: ako bilo koji insert padne,
    ROLLBACK i ``failed`` raste — ali u praksi confirm radi bulk-insert SAMO
    nad ``valid_rows`` (re-validacija ponovi parser i odbaci dup/invalid),
    pa je ``failed=0`` u happy path-u. ``skipped`` = invalid + duplicates.
    """

    created: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)


# ── Impersonation shapes (Faza 4.4) ───────────────────────────────────────────
# Mirror docs/websocket-schema.md §6.1 + frontend/types/admin.ts.


class ImpersonatorSummary(BaseModel):
    """Mirror of ``frontend/types/admin.ts::ImpersonatorSummary`` — minimalan
    info o admin-u koji je započeo impersonation, vraća se u start response-u
    da banner može da prikaže "Admin: {ime}".
    """

    id: UUID
    email: str
    first_name: str
    last_name: str

    model_config = {"from_attributes": True}


class ImpersonationStartResponse(BaseModel):
    """Mirror of ``frontend/types/admin.ts::ImpersonationStartResponse`` —
    ugovor iz ``docs/websocket-schema.md §6.1``.

    ``access_token`` nosi custom claims ``imp=true``, ``imp_email``,
    ``imp_name`` (vidi §6.2). NE prati refresh token — kad istekne (TTL=30min),
    klijent dobija 401 i admin re-impersonira (CLAUDE.md §14).
    """

    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = Field(description="Seconds until imp token exp (default 1800).")
    user: AdminUserResponse
    impersonator: ImpersonatorSummary
    imp_expires_at: datetime


class ImpersonationEndResponse(BaseModel):
    """Mirror of ``frontend/types/admin.ts::ImpersonationEndResponse``.

    Vraća svež regularni admin access token (``imp`` claim NIJE prisutan) i
    admin UserResponse — frontend store-uje token u :data:`useAuthStore` umesto
    impersonation tokena, banner self-heal logika ga pokreće (vidi
    ``frontend/components/shared/impersonation-banner.tsx``).
    """

    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = Field(description="Seconds until admin access token exp.")
    user: AdminUserResponse


# ── Audit log shapes (Faza 4.4) ───────────────────────────────────────────────


class AuditLogRow(BaseModel):
    """Mirror of ``frontend/types/admin.ts::AuditLogRow``.

    ``admin_full_name`` i ``impersonated_user_full_name`` su denormalizovana
    polja popunjena u ruti iz eager-load-ovanih ``audit_log_service`` veza
    (admin: 1:1 RESTRICT, impersonated_user: nullable SET NULL).
    """

    id: UUID
    admin_id: UUID
    admin_full_name: str
    impersonated_user_id: UUID | None
    impersonated_user_full_name: str | None
    action: str
    ip_address: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Strikes admin shapes (Faza 4.5) ───────────────────────────────────────────
# Mirror frontend/types/admin.ts (StrikeRow, UnblockRequest).
#
# StrikeRow agregira po studentu — total_points iz strike_records SUM(points),
# blocked_until iz student_blocks (1:1, NULL ako nikad nije bio blokiran ili
# je admin već override-ovao), last_strike_at iz MAX(strike_records.created_at).
# Lista nije paginate-ovana (vidi frontend hook use-strikes.ts) i filtrira se
# na ``total_points >= 1`` u service sloju (admin praćenje pre blokade).


class StrikeRow(BaseModel):
    """Mirror of ``frontend/types/admin.ts::StrikeRow``.

    Polja:
      - ``student_id``: UUID studenta
      - ``student_full_name``: ``"Ime Prezime"`` (denormalizovano u service-u)
      - ``email``: studentov email
      - ``faculty``: ``FON`` ili ``ETF``
      - ``total_points``: ``SUM(strike_records.points)`` (uvek >= 1 u listi)
      - ``blocked_until``: ``student_blocks.blocked_until`` ili None
        (NULL ako nikad nije bio blokiran ILI ako je blokada istekla
        prirodno ILI ako je admin override-ovao). Frontend disabled-uje
        "Odblokiraj" dugme kad je ``!blocked_until && total_points === 0``,
        ali takvi redovi se i ne vraćaju ovde (filter na servisu).
      - ``last_strike_at``: ``MAX(strike_records.created_at)`` ili None
    """

    student_id: UUID
    student_full_name: str
    email: str
    faculty: Faculty
    total_points: int = Field(ge=1)
    blocked_until: datetime | None = None
    last_strike_at: datetime | None = None


class UnblockRequest(BaseModel):
    """Mirror of ``frontend/types/admin.ts::UnblockRequest``.

    ``removal_reason`` je obavezan — admin uvek mora da obrazloži override
    blokade (PRD §5.1: "Admin može skinuti blokadu uz obrazloženje"). Min
    length=10 mirror-uje frontend zod schema u
    ``components/admin/strikes-table.tsx::unblockSchema``.
    """

    removal_reason: str = Field(min_length=10, max_length=2000)

    @field_validator("removal_reason", mode="before")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


# ── Broadcast shapes (Faza 4.5) ───────────────────────────────────────────────
# Mirror frontend/types/admin.ts (BroadcastTarget, BroadcastChannel,
# BroadcastRequest, BroadcastResponse).
#
# Frontend ugovor je striktan:
#   - target ∈ {"ALL", "STUDENTS", "STAFF", "BY_FACULTY"}  (NE postoji "YEAR")
#   - channels ⊆ {"IN_APP", "EMAIL"}                       (PUSH ne postoji)
#   - faculty se popunjava SAMO kad je target = "BY_FACULTY"
#
# Zato koristimo ``Literal[...]`` — Pydantic V2 striktno odbija nepoznate
# vrednosti sa 422, što je čistije od ``str + field_validator`` parovanja.

BroadcastTarget = Literal["ALL", "STUDENTS", "STAFF", "BY_FACULTY"]
BroadcastChannel = Literal["IN_APP", "EMAIL"]


class BroadcastRequest(BaseModel):
    """Mirror of ``frontend/types/admin.ts::BroadcastRequest``.

    Validacija (model_validator):
      - ``target == "BY_FACULTY"`` → ``faculty`` mora biti not-None (422 inače).
      - ``target != "BY_FACULTY"`` → ``faculty`` se ignoriše (postavljamo
        na None u DB redu; frontend može da pošalje vrednost ali backend
        je čisti — sprečava lažni "FON" u history-u na ALL broadcast-u).

    ``channels`` mora imati >= 1 element (frontend već validira lokalno;
    backend dodaje 422 za safety).
    """

    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=10)
    target: BroadcastTarget
    faculty: Faculty | None = None
    channels: list[BroadcastChannel] = Field(min_length=1)

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _faculty_consistency(self) -> "BroadcastRequest":
        if self.target == "BY_FACULTY" and self.faculty is None:
            raise ValueError(
                "faculty je obavezan kad je target=BY_FACULTY"
            )
        if self.target != "BY_FACULTY":
            # Tiho ignorišemo eventualnu vrednost (defensive — frontend ne
            # bi smeo da je pošalje, ali ne pravimo 422 da bi UX bio
            # otporniji na potencijalne form re-render bug-ove).
            self.faculty = None
        return self


class BroadcastResponse(BaseModel):
    """Mirror of ``frontend/types/admin.ts::BroadcastResponse``.

    Vraća se i sa POST /broadcast (uspešan dispatch) i sa GET /broadcast
    (history listing) — istu strukturu mapira frontend
    ``BroadcastHistoryRow``.

    ``channels`` je ``list[str]`` (ne Literal) jer ``from_attributes=True``
    učitava direktno iz ``Broadcast.channels`` PG array kolone — Pydantic
    V2 ne primenjuje Literal na ``model_validate(orm_obj)`` ako ulaz nije
    iz ``BroadcastRequest`` toka. Service garantuje da su vrednosti
    isključivo ``IN_APP``/``EMAIL`` (validacija je na entry point-u).
    """

    id: UUID
    title: str
    body: str
    target: BroadcastTarget
    faculty: Faculty | None
    channels: list[str]
    sent_by: UUID
    sent_at: datetime
    recipient_count: int

    model_config = {"from_attributes": True}
