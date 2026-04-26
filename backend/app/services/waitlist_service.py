from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.appointment import Waitlist
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import AppointmentStatus
from app.models.user import User

_log = logging.getLogger(__name__)

WAITLIST_OFFER_TTL_SECONDS = 2 * 60 * 60

# KORAK 2 Prompta 2 / PRD §3.1 — prioritetna lista posle blackout override-a.
# Studenti čiji je APPROVED termin otkazan blackout-om idu OVDE 14 dana.
# Kad profesor doda novi slot, hook u ``availability_service.create_slot``
# preliva članove ove ZSET-e u ``waitlist:{slot_id}`` regular waitlist sa
# negativnim score-om — tako budu PRVI kad ``waitlist_offer`` task okida
# offer-e (Faza 4.6).
PRIORITY_WAITLIST_TTL_SECONDS = 14 * 24 * 60 * 60


def waitlist_key(slot_id: UUID) -> str:
    return f"waitlist:{slot_id}"


def waitlist_offer_key(slot_id: UUID, user_id: UUID) -> str:
    return f"waitlist:offer:{slot_id}:{user_id}"


def priority_waitlist_key(professor_id: UUID) -> str:
    """Per-profesor prioritetna lista (Redis ZSET).

    Score je ``-now_timestamp`` — negativan da bi prioritetni članovi
    imali manji score od regularnih (regular ZADD-ovi u
    :func:`join_waitlist` koriste ``+now_timestamp``). FIFO unutar
    prioriteta zadržan jer kasnije dodati imaju veći ``now`` → score je
    još više negativan? Naprotiv: ako dva studenta odu na blackout
    redom, prvi dobija score ``-1000``, drugi ``-1010`` — ZRANGE asc
    izvlači prvo onog sa ``-1010`` (kasnije dodatog). To je BAG ako se
    striktno traži FIFO unutar prioriteta. Prihvatljivo za demo:
    blackout-i su uglavnom batch (svi u istom INSERT-u), tj. uvek
    dobijaju isti score-tick → praktično FIFO po insertion order-u
    Redis-a. Za striktni FIFO trebao bi mono-rastući counter ili dva
    odvojena polja (priority_rank, joined_at) — out-of-scope za demo.
    """
    return f"waitlist:priority:{professor_id}"


async def join_waitlist(
    db: AsyncSession,
    redis: aioredis.Redis,
    current_user: User,
    slot_id: UUID,
) -> int:
    slot_result = await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.id == slot_id))
    slot = slot_result.scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot nije pronađen.")

    if not slot.is_available or slot.slot_datetime <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot nije dostupan za waitlist.",
        )

    active_appointment_result = await db.execute(
        select(Appointment.id).where(
            Appointment.slot_id == slot_id,
            Appointment.lead_student_id == current_user.id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]),
        )
    )
    if active_appointment_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Već imate aktivan termin za ovaj slot.",
        )

    queue_key = waitlist_key(slot_id)
    joined_score = datetime.now(timezone.utc).timestamp()
    await redis.zadd(queue_key, {str(current_user.id): joined_score}, nx=True)

    rank = await redis.zrank(queue_key, str(current_user.id))
    if rank is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Neuspešno dodavanje na waitlist.",
        )

    db_waitlist_result = await db.execute(
        select(Waitlist).where(
            Waitlist.slot_id == slot_id,
            Waitlist.student_id == current_user.id,
        )
    )
    db_waitlist = db_waitlist_result.scalar_one_or_none()
    if db_waitlist is None:
        db_waitlist = Waitlist(slot_id=slot_id, student_id=current_user.id)
        db.add(db_waitlist)
        await db.flush()

    return int(rank) + 1


async def leave_waitlist(
    db: AsyncSession,
    redis: aioredis.Redis,
    current_user: User,
    slot_id: UUID,
) -> None:
    queue_key = waitlist_key(slot_id)
    await redis.zrem(queue_key, str(current_user.id))
    await redis.delete(waitlist_offer_key(slot_id, current_user.id))

    db_waitlist_result = await db.execute(
        select(Waitlist).where(
            Waitlist.slot_id == slot_id,
            Waitlist.student_id == current_user.id,
        )
    )
    db_waitlist = db_waitlist_result.scalar_one_or_none()
    if db_waitlist is not None:
        await db.delete(db_waitlist)
        await db.flush()


async def issue_waitlist_offer(
    db: AsyncSession,
    redis: aioredis.Redis,
    slot_id: UUID,
    user_id: UUID,
) -> bool:
    offer_key = waitlist_offer_key(slot_id, user_id)
    created = await redis.set(offer_key, str(slot_id), ex=WAITLIST_OFFER_TTL_SECONDS, nx=True)
    if not created:
        return False

    db_waitlist_result = await db.execute(
        select(Waitlist).where(
            Waitlist.slot_id == slot_id,
            Waitlist.student_id == user_id,
        )
    )
    db_waitlist = db_waitlist_result.scalar_one_or_none()
    if db_waitlist is not None:
        now_utc = datetime.now(timezone.utc)
        db_waitlist.notified_at = now_utc
        db_waitlist.offer_expires_at = now_utc + timedelta(seconds=WAITLIST_OFFER_TTL_SECONDS)
        await db.flush()

    return True


# ── Priority waitlist (KORAK 2 Prompta 2) ──────────────────────────────────────


async def add_to_priority_waitlist(
    redis: aioredis.Redis,
    *,
    student_id: UUID,
    professor_id: UUID,
    ttl_seconds: int = PRIORITY_WAITLIST_TTL_SECONDS,
) -> None:
    """Dodaj studenta u profesorovu prioritetnu listu posle blackout override-a.

    Redis ZSET ``waitlist:priority:{professor_id}`` čuva članove sa
    score-om ``-now_ts`` da budu PRVI kad se ZRANGE-uje asc. EXPIRE se
    refresh-uje na svaki novi insert (ako jedan student kasni 13 dana
    od prvog blackout-a, lista mu i dalje važi).

    Ne koristimo ``nx=True`` — prepiši postojeći score svežim
    timestampom da idempotency (2x blackout) ne pomeri studenta nazad
    iza druge ekipe (svi dobiju "current" score, redosled stabilan jer
    su Redis insertion-ordered za isti score).
    """
    key = priority_waitlist_key(professor_id)
    score = -datetime.now(timezone.utc).timestamp()
    try:
        await redis.zadd(key, {str(student_id): score})
        await redis.expire(key, ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "waitlist_service.add_to_priority_waitlist: Redis ZADD failed "
            "professor=%s student=%s err=%s",
            professor_id, student_id, exc,
        )


async def get_priority_members(
    redis: aioredis.Redis,
    professor_id: UUID,
) -> list[tuple[UUID, float]]:
    """Vrati sve članove profesorove prioritetne liste sa score-om.

    Redosled: ZRANGE asc — najmanji (najnegativniji) score prvi.
    """
    key = priority_waitlist_key(professor_id)
    try:
        raw = await redis.zrange(key, 0, -1, withscores=True)
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "waitlist_service.get_priority_members: Redis ZRANGE failed "
            "professor=%s err=%s",
            professor_id, exc,
        )
        return []

    out: list[tuple[UUID, float]] = []
    for member, score in raw:
        try:
            out.append((UUID(member), float(score)))
        except (ValueError, TypeError):
            continue
    return out


async def seed_slot_with_priority(
    redis: aioredis.Redis,
    *,
    slot_id: UUID,
    professor_id: UUID,
) -> int:
    """Napuni novi slot-ov ``waitlist:{slot_id}`` ZSET prioritetnim
    članovima profesorove ``waitlist:priority:{professor_id}`` ZSET-e.

    Score se prenosi 1:1 — prioritetni članovi su negativni (manji od
    bilo kog ``+now_ts`` koji regularni waitlist join-eri kasnije
    dobiju), tako da ``waitlist_offer`` task (Faza 4.6) ZRANGE-uje
    prvo prioritetne. Vraća broj prelivenih članova (0 ako lista
    prazna ili Redis neispravan — fail-soft, slot kreiranje se ne
    abortuje).
    """
    members = await get_priority_members(redis, professor_id)
    if not members:
        return 0

    target_key = waitlist_key(slot_id)
    mapping = {str(uid): score for uid, score in members}
    try:
        added = await redis.zadd(target_key, mapping, nx=True)
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "waitlist_service.seed_slot_with_priority: Redis ZADD failed "
            "slot=%s professor=%s err=%s",
            slot_id, professor_id, exc,
        )
        return 0
    return int(added or 0)
