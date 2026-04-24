from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment, AppointmentParticipant
from app.models.availability_slot import AvailabilitySlot, BlackoutDate
from app.models.enums import (
    AppointmentStatus,
    ParticipantStatus,
)
from app.models.professor import Professor
from app.models.strike import StudentBlock
from app.models.user import User
from app.schemas.student import AppointmentCreateRequest
from app.services import strike_service

LOCK_SCRIPT = """
if redis.call("exists", KEYS[1]) == 0 then
    redis.call("setex", KEYS[1], ARGV[1], ARGV[2])
    return 1
end
return 0
"""

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def _slot_lock_key(slot_id: UUID) -> str:
    return f"slot:lock:{slot_id}"


async def acquire_slot_lock(
    redis: aioredis.Redis,
    slot_id: str,
    user_id: str,
    ttl: int = 30,
) -> bool:
    result = await redis.eval(LOCK_SCRIPT, 1, f"slot:lock:{slot_id}", ttl, user_id)
    return result == 1


async def _release_slot_lock(
    redis: aioredis.Redis,
    slot_id: UUID,
    user_id: UUID,
) -> None:
    await redis.eval(_RELEASE_LOCK_SCRIPT, 1, _slot_lock_key(slot_id), str(user_id))


async def _ensure_student_not_blocked(db: AsyncSession, student_id: UUID) -> None:
    now_utc = datetime.now(timezone.utc)
    block_result = await db.execute(
        select(StudentBlock).where(
            StudentBlock.student_id == student_id,
            StudentBlock.blocked_until > now_utc,
        )
    )
    block = block_result.scalar_one_or_none()
    if block:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Student je blokiran do {block.blocked_until.isoformat()}.",
        )


async def _load_slot_or_404(db: AsyncSession, slot_id: UUID) -> AvailabilitySlot:
    result = await db.execute(
        select(AvailabilitySlot)
        .options(selectinload(AvailabilitySlot.professor).selectinload(Professor.user))
        .where(AvailabilitySlot.id == slot_id)
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot nije pronađen.")
    return slot


async def _ensure_slot_is_bookable(db: AsyncSession, slot: AvailabilitySlot) -> None:
    now_utc = datetime.now(timezone.utc)

    if not slot.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot nije dostupan za zakazivanje.",
        )

    if slot.slot_datetime <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nije moguće zakazati termin u prošlosti.",
        )

    slot_date = slot.slot_datetime.date()
    blackout_exists = await db.execute(
        select(BlackoutDate.id).where(
            BlackoutDate.professor_id == slot.professor_id,
            BlackoutDate.start_date <= slot_date,
            BlackoutDate.end_date >= slot_date,
        )
    )
    if blackout_exists.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profesor nije dostupan u izabranom periodu.",
        )

    active_appointments_count_result = await db.execute(
        select(func.count(Appointment.id)).where(
            Appointment.slot_id == slot.id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]),
        )
    )
    active_count = active_appointments_count_result.scalar_one()
    if active_count >= slot.max_students:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot je upravo zauzet, pokušajte ponovo.",
        )


async def _ensure_student_not_already_booked(
    db: AsyncSession,
    student_id: UUID,
    slot_id: UUID,
) -> None:
    existing_result = await db.execute(
        select(Appointment.id).where(
            Appointment.lead_student_id == student_id,
            Appointment.slot_id == slot_id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]),
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Već imate aktivan termin za izabrani slot.",
        )


async def create_appointment(
    db: AsyncSession,
    redis: aioredis.Redis,
    current_user: User,
    data: AppointmentCreateRequest,
) -> Appointment:
    lock_acquired = await acquire_slot_lock(redis, str(data.slot_id), str(current_user.id), ttl=30)
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot je upravo zauzet, pokušajte ponovo.",
        )

    try:
        await _ensure_student_not_blocked(db, current_user.id)

        slot = await _load_slot_or_404(db, data.slot_id)
        await _ensure_slot_is_bookable(db, slot)
        await _ensure_student_not_already_booked(db, current_user.id, slot.id)

        professor = slot.professor
        appointment_status = (
            AppointmentStatus.APPROVED
            if professor.auto_approve_special
            else AppointmentStatus.PENDING
        )

        appointment = Appointment(
            slot_id=slot.id,
            professor_id=slot.professor_id,
            lead_student_id=current_user.id,
            subject_id=data.subject_id,
            topic_category=data.topic_category,
            description=data.description,
            status=appointment_status,
            consultation_type=slot.consultation_type,
            is_group=False,
        )
        db.add(appointment)
        await db.flush()

        participant = AppointmentParticipant(
            appointment_id=appointment.id,
            student_id=current_user.id,
            status=ParticipantStatus.CONFIRMED,
            is_lead=True,
            confirmed_at=datetime.now(timezone.utc),
        )
        db.add(participant)
        await db.flush()
        await db.commit()

        result = await db.execute(
            select(Appointment)
            .options(selectinload(Appointment.slot))
            .where(Appointment.id == appointment.id)
        )
        appointment = result.scalar_one()

        if appointment.status == AppointmentStatus.APPROVED:
            from app.tasks.notifications import send_appointment_confirmed

            send_appointment_confirmed.delay(str(appointment.id))

        return appointment
    finally:
        await _release_slot_lock(redis, data.slot_id, current_user.id)


async def cancel_appointment(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> Appointment:
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(
            Appointment.id == appointment_id,
            Appointment.lead_student_id == current_user.id,
        )
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Termin nije pronađen.",
        )

    if appointment.status not in {AppointmentStatus.PENDING, AppointmentStatus.APPROVED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Termin nije moguće otkazati u trenutnom statusu.",
        )

    now_utc = datetime.now(timezone.utc)
    time_until_start = appointment.slot.slot_datetime - now_utc
    if time_until_start <= timedelta(0):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Termin nije moguće otkazati nakon što je počeo.",
        )

    appointment.status = AppointmentStatus.CANCELLED

    if time_until_start < timedelta(hours=12):
        await strike_service.add_late_cancel_strike(
            db=db,
            student_id=current_user.id,
            appointment_id=appointment.id,
        )

    await db.flush()
    await db.refresh(appointment)

    return appointment


async def list_my_appointments(
    db: AsyncSession,
    current_user: User,
    view: str = "upcoming",
) -> list[Appointment]:
    now_utc = datetime.now(timezone.utc)

    statement = (
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(Appointment.lead_student_id == current_user.id)
        .order_by(Appointment.created_at.desc())
    )

    if view == "upcoming":
        statement = statement.where(Appointment.slot.has(AvailabilitySlot.slot_datetime >= now_utc))
    elif view == "history":
        statement = statement.where(Appointment.slot.has(AvailabilitySlot.slot_datetime < now_utc))

    result = await db.execute(statement)
    return list(result.scalars().all())
