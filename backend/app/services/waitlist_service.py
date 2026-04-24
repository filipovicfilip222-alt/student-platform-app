from datetime import datetime, timedelta, timezone
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

WAITLIST_OFFER_TTL_SECONDS = 2 * 60 * 60


def waitlist_key(slot_id: UUID) -> str:
    return f"waitlist:{slot_id}"


def waitlist_offer_key(slot_id: UUID, user_id: UUID) -> str:
    return f"waitlist:offer:{slot_id}:{user_id}"


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
