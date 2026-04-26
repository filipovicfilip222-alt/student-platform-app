"""broadcast_service.py — Globalni admin broadcast (Faza 4.5).

Ulazi (samo iz ``api/v1/admin.py``):
  - :func:`dispatch` — INSERT ``broadcasts`` red, audit log
    (``BROADCAST_SENT``), commit, i delay Celery fan-out task-a
    (``broadcast_tasks.fanout_broadcast``).
  - :func:`list_history` — poslednjih N redova ``broadcasts`` tabele
    sortirano DESC po ``sent_at`` (frontend hook ``useBroadcastHistory``).

Resolve user_ids (target → SELECT users):
  ALL          → is_active=true (svi aktivni)
  STUDENTS     → role=STUDENT,    is_active=true
  STAFF        → role IN (PROFESOR, ASISTENT), is_active=true
  BY_FACULTY   → faculty=$f,      is_active=true (sve role)

ADMIN role je IZ-FILTRIRAN iz ALL/BY_FACULTY (admin ne treba da dobija
masovna obaveštenja koja je sam poslao). STAFF eksplicitno znači
profesori + asistenti (frontend label "Profesori i asistenti").

Recipient_count se računa **PRE** Celery dispatch-a (resolve query
selectuje ``id``-jeve), upiše se u ``broadcasts`` red i prosleđuje task-u
kao argument. Task ne re-resolve-uje — to znači da broadcast cilja
korisnike koji su bili aktivni u trenutku dispatch-a, što je tačno
semantičko ponašanje (admin koji deaktivira korisnika 2s posle
broadcast-a ne treba da utiče na koga ide notifikacija — već je
"poslata").

Per-user fan-out greške se loguju u Celery worker logu i NE smanjuju
``recipient_count`` u DB-u (vidi ``broadcast_tasks.fanout_broadcast``
za try/except pattern). Korisnik je svestan da ``recipient_count`` =
"ciljani primaoci", ne "uspešno dostavljeni".
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broadcast import Broadcast
from app.models.enums import AuditAction, Faculty, UserRole
from app.models.user import User
from app.schemas.admin import BroadcastRequest


async def _resolve_user_ids(
    db: AsyncSession,
    *,
    target: str,
    faculty: Faculty | None,
) -> list[UUID]:
    """Vrati listu ``users.id`` za zadati target (samo aktivni)."""
    stmt = select(User.id).where(User.is_active.is_(True))

    if target == "ALL":
        stmt = stmt.where(User.role != UserRole.ADMIN)
    elif target == "STUDENTS":
        stmt = stmt.where(User.role == UserRole.STUDENT)
    elif target == "STAFF":
        stmt = stmt.where(User.role.in_([UserRole.PROFESOR, UserRole.ASISTENT]))
    elif target == "BY_FACULTY":
        if faculty is None:
            # Pydantic ``BroadcastRequest`` model_validator već garantuje
            # da je faculty not-None za BY_FACULTY — ovo je defense-in-depth.
            return []
        stmt = stmt.where(
            User.faculty == faculty,
            User.role != UserRole.ADMIN,
        )
    else:
        return []

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def dispatch(
    db: AsyncSession,
    *,
    admin_id: UUID,
    payload: BroadcastRequest,
    ip_address: str,
) -> Broadcast:
    """Resolve targets, INSERT ``broadcasts`` red + audit log, commit,
    delay fan-out task. Vraća kompletiran ``Broadcast`` ORM objekat sa
    ``id``/``sent_at`` populated.

    Caller (``api/v1/admin.py::send_broadcast``) konvertuje ovo u
    ``BroadcastResponse`` Pydantic šemu kroz model_validate.
    """
    # Lokalni import da bi izbegli circular: audit_log_service uvozi enum-e
    # iz ``models.enums`` ali servisi u principu ne smeju da uvoze jedan
    # drugog na top-level (vidi CLAUDE.md §11).
    from app.services import audit_log_service
    from app.tasks.broadcast_tasks import fanout_broadcast

    user_ids = await _resolve_user_ids(
        db,
        target=payload.target,
        faculty=payload.faculty,
    )

    broadcast = Broadcast(
        admin_id=admin_id,
        title=payload.title,
        body=payload.body,
        target=payload.target,
        faculty=payload.faculty.value if payload.faculty else None,
        channels=list(payload.channels),
        recipient_count=len(user_ids),
    )
    db.add(broadcast)
    await db.flush()

    await audit_log_service.log_action(
        db,
        admin_id=admin_id,
        action=AuditAction.BROADCAST_SENT,
        ip_address=ip_address,
    )

    await db.commit()
    await db.refresh(broadcast)

    # Dispatch posle commit-a — ako Celery task propusti zbog Redis ispada,
    # broadcast row je u DB-u i admin može ručno ponoviti (ili u Prompt 2
    # dodajemo retry endpoint). NE delay-ujemo pre commit-a jer task može
    # da bude pickup-ovan pre nego što DB završi commit, pa fan-out čita
    # ``recipient_count=0`` iz tek-nekompletiranog reda.
    fanout_broadcast.delay(
        str(broadcast.id),
        [str(uid) for uid in user_ids],
        list(payload.channels),
    )

    return broadcast


async def list_history(
    db: AsyncSession,
    *,
    limit: int = 50,
) -> list[Broadcast]:
    """Vrati poslednjih ``limit`` broadcast-ova sortirano DESC po ``sent_at``.

    Koristi ``ix_broadcasts_sent_at`` indeks (kreiran u migraciji 0003)
    pa je query O(log n) i bez seq scan-a čak i ako tabela naraste.
    """
    stmt = (
        select(Broadcast)
        .order_by(desc(Broadcast.sent_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
