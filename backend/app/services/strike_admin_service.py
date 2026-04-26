"""strike_admin_service.py — Admin pregled strike-ova (Faza 4.5).

Servis za :func:`api.v1.admin.list_strikes` — agregira ``strike_records``
po studentu (SUM points + MAX created_at) i LEFT JOIN-uje sa
``student_blocks`` da pokupi ``blocked_until`` za UI badge.

Filter: vraćamo studente sa ``total_points >= 1`` (uključujući one bez
aktivnog bloka — admin praćenje pre nego što stignu na 3 poena). Frontend
``components/admin/strikes-table.tsx`` disabled-uje "Odblokiraj" dugme
kad je ``!blocked_until && total_points === 0``, što znači da očekuje i
preventivni listing.

Sortiranje (DB-side, frontend može da re-sortira):
  1. Aktivne blokade prve (``blocked_until > now()`` desc, NULLS LAST)
  2. Pa po ``total_points`` DESC
  3. Pa po ``last_strike_at`` DESC NULLS LAST

Bez paginate-a (vidi frontend hook ``use-strikes.ts`` — ne šalje params).
Realan broj redova u produkciji je < 100, pa hard cap nije dodat.

NB: ``strike_service.unblock_student`` setuje ``blocked_until = now()``
posle čega ``StudentBlock`` red OSTAJE u tabeli (nije DELETE; ``unique
(student_id)`` constraint sprečava re-insert). Zato ``blocked_until``
za odblokirane studente vraćamo kao istorijski timestamp; UI badge se
prikazuje samo ako je ``blocked_until > now()``, što je tačno semantičko
ponašanje (odblokirani student i dalje ima ``StudentBlock`` red, ali
nije aktivno blokiran). Da bismo mirror-ovali UI namen, u response
vraćamo ``blocked_until`` SAMO kad je u budućnosti — istorijske blokade
postavljamo na None.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Faculty
from app.models.strike import StrikeRecord, StudentBlock
from app.models.user import User
from app.schemas.admin import StrikeRow


async def list_strike_rows(db: AsyncSession) -> list[StrikeRow]:
    """Lista studenata sa ``total_points >= 1``, sortirano DB-side."""
    now_utc = datetime.now(timezone.utc)

    # Subquery: per-student agregat strike_records.
    agg = (
        select(
            StrikeRecord.student_id.label("student_id"),
            func.sum(StrikeRecord.points).label("total_points"),
            func.max(StrikeRecord.created_at).label("last_strike_at"),
        )
        .group_by(StrikeRecord.student_id)
        .having(func.sum(StrikeRecord.points) >= 1)
        .subquery()
    )

    # Glavni query: User INNER JOIN agg + LEFT JOIN student_blocks.
    # INNER na agg jer filter je "ima bar 1 strike". LEFT na blocks jer
    # student možda nikad nije bio blokiran (1-2 poena slučaj).
    stmt = (
        select(
            User.id,
            User.first_name,
            User.last_name,
            User.email,
            User.faculty,
            agg.c.total_points,
            agg.c.last_strike_at,
            StudentBlock.blocked_until,
        )
        .join(agg, agg.c.student_id == User.id)
        .outerjoin(StudentBlock, StudentBlock.student_id == User.id)
        .order_by(
            # Active blocks first (TRUE=1 → first if DESC). NULLS LAST je
            # default u PG-u za DESC, što odgovara našem "no block last".
            case(
                (StudentBlock.blocked_until > now_utc, 1),
                else_=0,
            ).desc(),
            agg.c.total_points.desc(),
            agg.c.last_strike_at.desc().nulls_last(),
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    output: list[StrikeRow] = []
    for r in rows:
        # Mirror UI semantike: prikazujemo ``blocked_until`` SAMO ako je
        # blokada aktivna (u budućnosti). Istorijske / admin-override
        # blokade se vraćaju kao None — UI tako neće prikazati badge.
        blocked_until = (
            r.blocked_until if r.blocked_until and r.blocked_until > now_utc else None
        )

        output.append(
            StrikeRow(
                student_id=r.id,
                student_full_name=f"{r.first_name} {r.last_name}",
                email=r.email,
                faculty=Faculty(r.faculty.value if hasattr(r.faculty, "value") else r.faculty),
                total_points=int(r.total_points),
                blocked_until=blocked_until,
                last_strike_at=r.last_strike_at,
            )
        )

    return output
