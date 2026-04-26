"""audit_log_service.py — Pisanje i čitanje ``audit_log`` tabele (Faza 4.4).

Tabela postoji od ``alembic/versions/20260423_0001_initial_schema.py`` — kolone
``admin_id`` (FK users RESTRICT), ``impersonated_user_id`` (FK users SET NULL),
``action`` (Text), ``ip_address`` (PG INET), ``created_at`` (timestamptz, default
now). Nema migracije 0003.

Striktna validacija ``action``-a se radi kroz Python ``AuditAction`` enum
(``app.models.enums``). Trenutno scope: samo IMPERSONATION_START /
IMPERSONATION_END (KORAK 6). Buduće akcije (USER_CREATE, BROADCAST_SENT, ...)
samo dodaju vrednosti u enum, bez šeme.

Servis se ZA SADA poziva isključivo iz ``impersonation_service.start/end``;
``api/v1/admin.py::list_audit_log`` čita kroz :func:`list_entries`. Ne koristi
ga niko drugi — i to je namerno (jedna ulazna tačka).
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction


# Hard cap na broj redova koji se vraća u jednom GET-u — čisti UX (admin
# tabela u UI nije paginirana u Fazi 4.4) + zaštita od memory blow-up-a kad
# log naraste. Ako filter ne sužava dovoljno, korisnik mora suziti datum.
_DEFAULT_LIMIT = 200


async def log_action(
    db: AsyncSession,
    *,
    admin_id: UUID,
    action: AuditAction,
    ip_address: str,
    impersonated_user_id: UUID | None = None,
) -> AuditLog:
    """
    Insert a new audit row. **Caller je odgovoran za commit** — servis radi
    samo ``add()`` da bi se atomsko uvezivanje sa biznis transakcijom (npr.
    impersonation start) sačuvalo (jedan rollback briše i log i akciju ako
    nešto pukne).

    ``ip_address`` je sirov string — :class:`INET` PG kolona prihvata IPv4 ili
    IPv6 literal. Pripremi ga kroz ``_client_ip(request)`` u ruti.
    """
    row = AuditLog(
        admin_id=admin_id,
        impersonated_user_id=impersonated_user_id,
        action=action.value,
        ip_address=ip_address,
    )
    db.add(row)
    await db.flush()
    return row


async def list_entries(
    db: AsyncSession,
    *,
    admin_id: UUID | None = None,
    action: AuditAction | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = _DEFAULT_LIMIT,
) -> list[AuditLog]:
    """
    Vrati audit redove sortirano DESC po ``created_at``, sa eager-load-ovanim
    ``admin`` i ``impersonated_user`` relationships da rute mogu da pune
    ``admin_full_name`` / ``impersonated_user_full_name`` polja iz
    :class:`AuditLogRow` šeme bez N+1 query-ja.

    Datum filteri su inkluzivni na granicama (full-day prozor):
      ``from_date`` → 00:00:00 UTC tog dana
      ``to_date``   → 23:59:59.999999 UTC tog dana

    Action je **exact-match** (enum, ne free text). Frontend
    :data:`AuditLogFilter` šalje tačnu vrednost ili ništa.
    """
    stmt = (
        select(AuditLog)
        .options(
            selectinload(AuditLog.admin),
            selectinload(AuditLog.impersonated_user),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )

    conditions = []
    if admin_id is not None:
        conditions.append(AuditLog.admin_id == admin_id)
    if action is not None:
        conditions.append(AuditLog.action == action.value)
    if from_date is not None:
        start_dt = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        conditions.append(AuditLog.created_at >= start_dt)
    if to_date is not None:
        end_dt = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        conditions.append(AuditLog.created_at <= end_dt)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_active_impersonation_target(
    db: AsyncSession,
    *,
    admin_id: UUID,
) -> UUID | None:
    """
    Pronađi ID trenutno-impersoniranog korisnika za zadatog admina, ili None
    ako nema otvorenu sesiju. "Otvorena" znači: poslednji IMPERSONATION_START
    za ovog admina nije zatvoren naknadnim IMPERSONATION_END-om.

    Ovaj helper je optimizacija za :func:`impersonation_service.start_impersonation`
    da bi pri re-impersonation flow-u (admin ide A → B bez Izađi) mogli da
    automatski upišemo ``IMPERSONATION_END`` za A pre nego što izdamo novi
    token za B.

    Jednostavna implementacija: čitamo poslednje 2 redaka za ovog admina,
    sortiramo DESC. Ako je TOP red START i nema END posle njega → otvorena.
    Heuristika "samo poslednji START vs poslednji END" radi tačno jer je
    impersonation single-session per admin — admin ne može imati 2 paralelne
    sesije (token swap zatvara prethodnu).
    """
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.admin_id == admin_id,
            AuditLog.action.in_(
                [AuditAction.IMPERSONATION_START.value, AuditAction.IMPERSONATION_END.value]
            ),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    last: AuditLog | None = result.scalar_one_or_none()

    if last is None:
        return None
    if last.action == AuditAction.IMPERSONATION_START.value:
        return last.impersonated_user_id
    return None
