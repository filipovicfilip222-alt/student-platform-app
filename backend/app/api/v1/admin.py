from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, UploadFile, status

from app.core.config import settings
from app.core.dependencies import (
    CurrentAdmin,
    CurrentAdminActor,
    CurrentUser,
    DBSession,
)
from app.models.enums import AuditAction, DocumentStatus, Faculty, UserRole
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    AuditLogRow,
    BroadcastRequest,
    BroadcastResponse,
    BulkImportPreview,
    BulkImportResult,
    ImpersonationEndResponse,
    ImpersonationStartResponse,
    ImpersonatorSummary,
    StrikeRow,
    UnblockRequest,
)
from app.schemas.auth import MessageResponse
from app.schemas.document_request import (
    DocumentRequestApproveRequest,
    DocumentRequestRejectRequest,
    DocumentRequestResponse,
)
from app.services import (
    admin_user_service,
    audit_log_service,
    broadcast_service,
    document_request_service,
    impersonation_service,
    strike_admin_service,
    strike_service,
)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _client_ip(request: Request) -> str:
    """
    Extract the originating client IP for audit logging (CLAUDE.md §15).

    Nginx (vidi ``infra/nginx/nginx.conf``) prosleđuje ``X-Forwarded-For`` i
    ``X-Real-IP`` na svaki backend request, pa ovde čitamo prvi (klijentski)
    hop. Ako nema header-a (npr. direktan curl na :8000 u dev-u), pada na
    ``request.client.host`` koji je TCP peer.

    Za PG ``INET`` kolonu vraćamo plain IPv4/IPv6 string — ``audit_log.ip_address``
    SQLAlchemy-mapping prihvata string i konvertuje u INET na insert-u.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # XFF je comma-separated lista hopova; prvi je originalni klijent.
        return xff.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client is not None:
        return request.client.host
    # Fallback — INET kolona ne sme NULL po šemi; loopback je manje loš od krega.
    return "0.0.0.0"


def _full_name(user) -> str:
    return f"{user.first_name} {user.last_name}"


# ── Users CRUD (Faza 4.3) ─────────────────────────────────────────────────────


@router.get(
    "/users",
    response_model=list[AdminUserResponse],
    summary="Lista korisnika sa ILIKE pretragom + role/faculty filterima",
)
async def list_users(
    db: DBSession,
    current_user: CurrentAdmin,
    q: str | None = Query(default=None, min_length=1, max_length=200),
    role: UserRole | None = Query(default=None),
    faculty: Faculty | None = Query(default=None),
) -> list[AdminUserResponse]:
    """Frontend (``frontend/lib/api/admin.ts::listUsers``) šalje samo
    ``q``/``role``/``faculty`` — bez paginate. Vraćamo bare array sortiran
    po ``created_at DESC`` (vidi ``admin_user_service.list_users``)."""
    users = await admin_user_service.list_users(
        db, q=q, role=role, faculty=faculty
    )
    return [AdminUserResponse.model_validate(u) for u in users]


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Detalji jednog korisnika",
)
async def get_user(
    user_id: UUID,
    db: DBSession,
    current_user: CurrentAdmin,
) -> AdminUserResponse:
    user = await admin_user_service.get_user(db, user_id)
    return AdminUserResponse.model_validate(user)


@router.post(
    "/users",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje korisnika (single) sa welcome email-om + reset linkom (TTL 7d)",
)
async def create_user(
    payload: AdminUserCreate,
    db: DBSession,
    current_user: CurrentAdmin,
) -> AdminUserResponse:
    """Hibridni welcome flow (vidi user prompt — pitanje B):

    * Hash-uje admin-unetu lozinku (frontend ugovor zahteva ``password``).
    * Kreira ``User`` (+ default ``Professor`` red za PROFESOR/ASISTENT).
    * Šalje welcome email sa ``/reset-password?token=...`` linkom (TTL 7d).
    """
    user = await admin_user_service.create_user(db, payload)
    return AdminUserResponse.model_validate(user)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Patch korisnika (first/last name, role, faculty, is_active)",
)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    db: DBSession,
    current_user: CurrentAdmin,
) -> AdminUserResponse:
    user = await admin_user_service.update_user(db, user_id, payload)
    return AdminUserResponse.model_validate(user)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=MessageResponse,
    summary="Soft delete — is_active=false (postojeći appointments ostaju)",
)
async def deactivate_user(
    user_id: UUID,
    db: DBSession,
    current_user: CurrentAdmin,
) -> MessageResponse:
    """Soft delete (CURRENT_STATE2 §4.4 + user prompt D). Login flow odbija
    deaktivirane korisnike sa 403; postojeći appointmenti i document_request-i
    ostaju netaknuti."""
    user = await admin_user_service.deactivate_user(db, user_id)
    return MessageResponse(
        message=f"Korisnik {user.email} je deaktiviran."
    )


# ── Bulk CSV import (Faza 4.3) ────────────────────────────────────────────────
#
# Frontend (``frontend/lib/api/admin.ts``) re-uploaduje fajl na BOTH
# preview i confirm — preview_id se ne čuva (vidi user prompt pitanje C).
# Multipart key je ``file`` u oba slučaja.


@router.post(
    "/users/bulk-import/preview",
    response_model=BulkImportPreview,
    summary="Bulk CSV preview — parse + klasifikacija (valid/invalid/duplicates)",
)
async def bulk_import_preview(
    db: DBSession,
    current_user: CurrentAdmin,
    file: UploadFile = File(..., description="CSV (UTF-8, header: ime, prezime, email, indeks, smer, godina_upisa)"),
) -> BulkImportPreview:
    """Bulk je SAMO za studente (whitelist domeni). Vidi
    ``admin_user_service.bulk_import_preview`` za pravila parsiranja."""
    csv_bytes = await file.read()
    return await admin_user_service.bulk_import_preview(db, csv_bytes)


@router.post(
    "/users/bulk-import/confirm",
    response_model=BulkImportResult,
    summary="Bulk CSV confirm — re-validira fajl, kreira valid redove kao studente",
)
async def bulk_import_confirm(
    db: DBSession,
    current_user: CurrentAdmin,
    file: UploadFile = File(..., description="Isti CSV kao u preview-u (frontend re-upload)"),
) -> BulkImportResult:
    """Re-validira ceo CSV (stateless, vidi user prompt pitanje C) i
    kreira SAMO valid_rows kao ``UserRole.STUDENT``. Welcome email-ovi se
    dispatch-uju Celery task-ovima posle uspešnog flush-a (vidi
    ``admin_user_service.bulk_import_confirm``)."""
    csv_bytes = await file.read()
    return await admin_user_service.bulk_import_confirm(db, csv_bytes)


@router.get(
    "/document-requests",
    response_model=list[DocumentRequestResponse],
    summary="Inbox zahteva za dokumente",
)
async def list_document_requests(
    db: DBSession,
    current_user: CurrentAdmin,
    status: DocumentStatus | None = Query(default=None),
) -> list[DocumentRequestResponse]:
    items = await document_request_service.list_for_admin(db, status)
    return [DocumentRequestResponse.model_validate(item) for item in items]


@router.post(
    "/document-requests/{request_id}/approve",
    response_model=DocumentRequestResponse,
    summary="Odobravanje zahteva za dokument",
)
async def approve_document_request(
    request_id: UUID,
    data: DocumentRequestApproveRequest,
    db: DBSession,
    current_user: CurrentAdmin,
) -> DocumentRequestResponse:
    item = await document_request_service.approve(db, current_user, request_id, data)
    return DocumentRequestResponse.model_validate(item)


@router.post(
    "/document-requests/{request_id}/reject",
    response_model=DocumentRequestResponse,
    summary="Odbijanje zahteva za dokument",
)
async def reject_document_request(
    request_id: UUID,
    data: DocumentRequestRejectRequest,
    db: DBSession,
    current_user: CurrentAdmin,
) -> DocumentRequestResponse:
    item = await document_request_service.reject(db, current_user, request_id, data)
    return DocumentRequestResponse.model_validate(item)


@router.post(
    "/document-requests/{request_id}/complete",
    response_model=DocumentRequestResponse,
    summary="Označavanje zahteva kao preuzetog",
)
async def complete_document_request(
    request_id: UUID,
    db: DBSession,
    current_user: CurrentAdmin,
) -> DocumentRequestResponse:
    item = await document_request_service.complete(db, current_user, request_id)
    return DocumentRequestResponse.model_validate(item)


# ── Impersonation + Audit log (Faza 4.4) ──────────────────────────────────────
# Ugovor: docs/websocket-schema.md §6 + frontend/types/admin.ts.
#
# /admin/impersonate/{user_id} koristi standardni CurrentAdmin (admin token sa
# regularnom rolom) — ne sme da se startuje sledeća imp sesija iz već-imp
# tokena. Re-impersonate (admin u imp na A → B) frontend radi tako što prvo
# zove /impersonate/end (sa imp tokenom — koristi CurrentUser jer current_user
# je target, audit log se uvek vodi za pravog admina iz imp_email claim-a),
# pa onda /impersonate/{B} sa povraćenim admin tokenom.
#
# Alternativno, frontend može da sačuva original admin token u
# ``useImpersonationStore.originalUser`` snapshotu i koristi GA za
# /impersonate/{B} (preporučen flow per impersonation-banner.tsx). U tom
# slučaju backend audit_log_service.start_impersonation auto-zatvori prethodnu
# sesiju kroz ``get_active_impersonation_target``.


# IMPORTANT: ``/impersonate/end`` se MORA registrovati PRE ``/impersonate/{user_id}``
# (FastAPI matche-uje rute po redosledu deklaracije — ako je obrnuto, request sa
# putanjom ``/impersonate/end`` bi prvo pogodio parametrizovanu rutu sa
# ``user_id="end"``, prošao Pydantic UUID validaciju kao 422... ALI je opasniji
# scenario kada ``CurrentAdmin`` dep eksplodira sa 403 pre nego što se uopšte
# stigne do path validacije, jer je sa imp tokenom current_user student).


@router.post(
    "/impersonate/end",
    response_model=ImpersonationEndResponse,
    status_code=status.HTTP_200_OK,
    summary="Završi impersonation i vrati admin sesiju",
)
async def end_impersonate(
    request: Request,
    db: DBSession,
    admin: CurrentAdminActor,
    current_user: CurrentUser,
) -> ImpersonationEndResponse:
    """Klijent zove ovaj endpoint sa AKTIVNIM imp tokenom — ``current_user``
    je target, ``admin`` je razrešen iz ``imp_email`` claim-a kroz
    :data:`CurrentAdminActor`. Audit log dobija END entry, response nosi svež
    regularni admin access token bez ``imp`` claim-a.

    Ako klijent zove ovo sa REGULARNIM admin tokenom (npr. self-heal banner
    detektuje da imp token više ne važi), funkcioniše svejedno —
    ``current_user.id == admin.id`` i ``IMPERSONATION_END`` će imati NULL
    ``impersonated_user_id`` što je tehnički no-op zapis ali ne pravimo 4xx.
    """
    ip = _client_ip(request)
    target_id = current_user.id if current_user.id != admin.id else None

    token, _ = await impersonation_service.end_impersonation(
        db,
        admin=admin,
        target_user_id=target_id,
        ip_address=ip,
    )
    return ImpersonationEndResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=AdminUserResponse.model_validate(admin),
    )


@router.post(
    "/impersonate/{user_id}",
    response_model=ImpersonationStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Započni impersonation sesiju (admin → target user)",
)
async def start_impersonate(
    user_id: UUID,
    request: Request,
    db: DBSession,
    admin: CurrentAdmin,
) -> ImpersonationStartResponse:
    """Issue a 30-min impersonation JWT for ``user_id`` and write the
    ``IMPERSONATION_START`` audit row. ``CurrentAdmin`` (regularni admin token,
    rola=ADMIN) — admin sa AKTIVNIM imp tokenom dobija 403 i mora prvo da
    klikne "Izađi" (ili frontend pošalje sačuvan original admin token iz
    ``useImpersonationStore.originalUser`` — vidi pitanje 5).
    """
    ip = _client_ip(request)
    token, expires_at, target = await impersonation_service.start_impersonation(
        db,
        admin=admin,
        target_user_id=user_id,
        ip_address=ip,
    )
    return ImpersonationStartResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.IMPERSONATION_TOKEN_TTL_MINUTES * 60,
        user=AdminUserResponse.model_validate(target),
        impersonator=ImpersonatorSummary.model_validate(admin),
        imp_expires_at=expires_at,
    )


@router.get(
    "/audit-log",
    response_model=list[AuditLogRow],
    summary="Lista audit log unosa (default DESC, max 200)",
)
async def list_audit_log(
    db: DBSession,
    admin: CurrentAdminActor,
    admin_id: UUID | None = Query(default=None),
    action: AuditAction | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> list[AuditLogRow]:
    """Vraća audit log redove sortirano DESC po ``created_at`` (max 200 po
    pozivu — UI tabela u Fazi 4.4 nije paginirana, suzite filterima ako
    treba više). ``admin_full_name`` i ``impersonated_user_full_name`` se
    pune iz eager-load-ovanih relationships da nema N+1."""
    rows = await audit_log_service.list_entries(
        db,
        admin_id=admin_id,
        action=action,
        from_date=from_date,
        to_date=to_date,
    )
    return [
        AuditLogRow(
            id=r.id,
            admin_id=r.admin_id,
            admin_full_name=_full_name(r.admin),
            impersonated_user_id=r.impersonated_user_id,
            impersonated_user_full_name=(
                _full_name(r.impersonated_user) if r.impersonated_user else None
            ),
            action=r.action,
            ip_address=str(r.ip_address),
            created_at=r.created_at,
        )
        for r in rows
    ]


# ── Strikes + Broadcast (Faza 4.5) ────────────────────────────────────────────
# Ugovor: frontend/types/admin.ts + frontend/lib/api/admin.ts.
#
# Dva domena u jednoj sekciji:
#   - Strikes: read-only listing + admin override unblock
#     (POSTOJEĆI strike_service iz Faze 3.1 reuse-ovan kroz unblock_student
#     helper; novi je samo strike_admin_service.list_strike_rows agregator.)
#   - Broadcast: dispatch (INSERT broadcasts row + audit + Celery fan-out
#     task) + history listing (poslednjih N redova ``broadcasts`` tabele).
#
# Audit log: oba domena pišu u ``audit_log`` (akcije ``STRIKE_UNBLOCKED`` /
# ``BROADCAST_SENT``). Nema metadata kolone — title/body broadcast-a živi u
# zasebnoj ``broadcasts`` tabeli (migracija 0003), audit log nosi samo
# činjenicu + admin ip/identitet.


@router.get(
    "/strikes",
    response_model=list[StrikeRow],
    summary="Lista studenata sa total_points >= 1 (sortirano DB-side)",
)
async def list_strikes(
    db: DBSession,
    current_user: CurrentAdmin,
) -> list[StrikeRow]:
    """Bare array bez paginate-a (vidi ``frontend/lib/hooks/use-strikes.ts``).

    Sortiranje (DB-side, frontend re-sortira u ``strikes-table.tsx``):
    aktivne blokade prve, pa total_points DESC, pa last_strike_at DESC.
    Filter: ``total_points >= 1`` (admin praćenje uključuje i 1-2 poena
    studente, ne samo blokirane).
    """
    return await strike_admin_service.list_strike_rows(db)


@router.post(
    "/strikes/{student_id}/unblock",
    response_model=MessageResponse,
    summary="Admin override blokade — postavlja blocked_until=now + audit + notif",
)
async def unblock_strike(
    student_id: UUID,
    payload: UnblockRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentAdmin,
) -> MessageResponse:
    """Admin override blokade (PRD §5.1).

    Flow:
      1. ``strike_service.unblock_student`` — UPDATE ``student_blocks``:
         setuje ``blocked_until = now()`` (efektivno otključava — ostali
         servisi proveravaju ``blocked_until > now()``), upiše
         ``removed_by`` i ``removal_reason``.
      2. Audit log ``STRIKE_UNBLOCKED`` (admin_id + ip + impersonated_user_id
         = student_id da history pokazuje na koga se odnosi).
      3. Commit DB transakcije.
      4. ``send_block_lifted.delay(...)`` — email + in-app BLOCK_LIFTED notif
         (BLOCK_LIFTED tip već postoji u ``NotificationType`` enum-u).

    Idempotentnost: ako student nije bio blokiran (``unblock_student``
    vraća None), NE pišemo audit log i NE šaljemo notif (ne želimo lažne
    BLOCK_LIFTED-ove studentu koji nikad nije bio blokiran). Vraćamo
    MessageResponse svejedno (200) jer je krajnja stanja idempotentna —
    student je odblokiran (ili nikad nije ni bio).
    """
    from app.tasks.notifications import send_block_lifted

    # Učitavamo studenta da bi MessageResponse imao smisleno ime u toast-u.
    student = await admin_user_service.get_user(db, student_id)

    block = await strike_service.unblock_student(
        db,
        student_id=student_id,
        removed_by=current_user.id,
        removal_reason=payload.removal_reason,
    )

    if block is None:
        # Student nikad nije bio blokiran — no-op (idempotent).
        return MessageResponse(
            message=f"Student {_full_name(student)} nije bio blokiran."
        )

    await audit_log_service.log_action(
        db,
        admin_id=current_user.id,
        action=AuditAction.STRIKE_UNBLOCKED,
        ip_address=_client_ip(request),
        impersonated_user_id=student_id,
    )

    await db.commit()

    # Dispatch posle commit-a — ako Celery propusti task, DB stanje je
    # ispravno (admin override je gotov), a notif retry mehanizam
    # (Celery acks_late=True iz celery_app.py) će dohvatiti.
    send_block_lifted.delay(str(student_id), payload.removal_reason)

    return MessageResponse(
        message=f"Student {_full_name(student)} je odblokiran."
    )


def _broadcast_to_response(b) -> BroadcastResponse:
    """Mapping ORM ``Broadcast`` → frontend ``BroadcastResponse``.

    Frontend ugovor (``frontend/types/admin.ts``) koristi ``sent_by`` polje
    umesto ``admin_id`` — denormalizujemo da rute vraćaju identičan shape
    za POST i GET. ``faculty`` se vraća kao Faculty enum (ili None).
    """
    return BroadcastResponse(
        id=b.id,
        title=b.title,
        body=b.body,
        target=b.target,
        faculty=Faculty(b.faculty) if b.faculty else None,
        channels=list(b.channels),
        sent_by=b.admin_id,
        sent_at=b.sent_at,
        recipient_count=b.recipient_count,
    )


@router.post(
    "/broadcast",
    response_model=BroadcastResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Globalno admin obaveštenje — INSERT + Celery fan-out (IN_APP/EMAIL)",
)
async def send_broadcast(
    payload: BroadcastRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentAdmin,
) -> BroadcastResponse:
    """Resolve user_ids po target-u, INSERT ``broadcasts`` red, audit log
    ``BROADCAST_SENT``, commit, delay Celery fan-out task.

    Per-user IN_APP create i EMAIL send su u try/except u Celery task-u —
    privremeni Redis/SMTP ispad NE smanjuje ``recipient_count`` u DB-u
    (ostane "ciljani" broj resolve-ovan PRE dispatch-a). Greške idu u
    Celery worker log.

    Frontend toast prikaže ``Dostavljeno {recipient_count} primaocima.``;
    napomena: to je broj POSLATIH primaoca, ne nužno DOSTAVLJENIH (ali za
    V1 je to dovoljno — vidi CURRENT_STATE2 §4.5 za argumentaciju).
    """
    broadcast = await broadcast_service.dispatch(
        db,
        admin_id=current_user.id,
        payload=payload,
        ip_address=_client_ip(request),
    )
    return _broadcast_to_response(broadcast)


@router.get(
    "/broadcast",
    response_model=list[BroadcastResponse],
    summary="Istorija broadcast-ova (poslednjih 50, DESC po sent_at)",
)
async def list_broadcasts(
    db: DBSession,
    current_user: CurrentAdmin,
) -> list[BroadcastResponse]:
    """Bare array bez paginate-a (vidi
    ``frontend/lib/hooks/use-broadcast.ts::useBroadcastHistory``).
    Sortirano DESC po ``sent_at`` kroz ``ix_broadcasts_sent_at`` indeks.
    """
    rows = await broadcast_service.list_history(db, limit=50)
    return [_broadcast_to_response(r) for r in rows]
