from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot, BlackoutDate
from app.models.professor import Professor
from app.models.user import User
from app.schemas.professor import BlackoutCreate, SlotCreate, SlotUpdate


async def _get_professor_profile_or_404(db: AsyncSession, user_id: UUID) -> Professor:
    result = await db.execute(select(Professor).where(Professor.user_id == user_id))
    professor = result.scalar_one_or_none()
    if not professor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesor profil nije pronađen.",
        )
    return professor


async def list_slots(db: AsyncSession, current_user: User) -> list[AvailabilitySlot]:
    professor = await _get_professor_profile_or_404(db, current_user.id)
    result = await db.execute(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.professor_id == professor.id)
        .order_by(AvailabilitySlot.slot_datetime.asc())
    )
    return list(result.scalars().all())


async def create_slot(
    db: AsyncSession,
    current_user: User,
    data: SlotCreate,
) -> AvailabilitySlot:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    slot = AvailabilitySlot(
        professor_id=professor.id,
        slot_datetime=data.slot_datetime,
        duration_minutes=data.duration_minutes,
        consultation_type=data.consultation_type,
        max_students=data.max_students,
        online_link=data.online_link,
        is_available=data.is_available,
        recurring_rule=data.recurring_rule,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
    )
    db.add(slot)
    await db.flush()
    await db.refresh(slot)
    return slot


async def update_slot(
    db: AsyncSession,
    current_user: User,
    slot_id: UUID,
    data: SlotUpdate,
) -> AvailabilitySlot:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    result = await db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id,
            AvailabilitySlot.professor_id == professor.id,
        )
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot nije pronađen.",
        )

    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(slot, field, value)

    await db.flush()
    await db.refresh(slot)
    return slot


async def delete_slot(db: AsyncSession, current_user: User, slot_id: UUID) -> None:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    result = await db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id,
            AvailabilitySlot.professor_id == professor.id,
        )
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot nije pronađen.",
        )

    appointment_exists = await db.execute(
        select(Appointment.id).where(Appointment.slot_id == slot.id)
    )
    if appointment_exists.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot ima povezane termine i ne može biti obrisan.",
        )

    await db.delete(slot)
    await db.flush()


async def create_blackout(
    db: AsyncSession,
    current_user: User,
    data: BlackoutCreate,
) -> BlackoutDate:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    blackout = BlackoutDate(
        professor_id=professor.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
    )

    db.add(blackout)
    await db.flush()
    await db.refresh(blackout)
    return blackout


async def delete_blackout(db: AsyncSession, current_user: User, blackout_id: UUID) -> None:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    result = await db.execute(
        select(BlackoutDate).where(
            BlackoutDate.id == blackout_id,
            BlackoutDate.professor_id == professor.id,
        )
    )
    blackout = result.scalar_one_or_none()

    if not blackout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blackout period nije pronađen.",
        )

    await db.delete(blackout)
    await db.flush()
