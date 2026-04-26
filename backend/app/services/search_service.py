from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot, BlackoutDate
from app.models.enums import AppointmentStatus, ConsultationType, Faculty
from app.models.faq import FaqItem
from app.models.professor import Professor
from app.models.subject import Subject
from app.models.user import User
from app.schemas.student import (
    AvailableSlotResponse,
    FaqResponse,
    ProfessorProfileResponse,
    ProfessorSearchResponse,
)


def _available_slots_query(professor_id: UUID) -> Select[tuple[AvailabilitySlot]]:
    slot_date = func.date(AvailabilitySlot.slot_datetime)

    has_active_appointment = exists(
        select(Appointment.id).where(
            Appointment.slot_id == AvailabilitySlot.id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]),
        )
    )

    overlaps_blackout = exists(
        select(BlackoutDate.id).where(
            BlackoutDate.professor_id == AvailabilitySlot.professor_id,
            BlackoutDate.start_date <= slot_date,
            BlackoutDate.end_date >= slot_date,
        )
    )

    return (
        select(AvailabilitySlot)
        .where(
            AvailabilitySlot.professor_id == professor_id,
            AvailabilitySlot.is_available.is_(True),
            AvailabilitySlot.slot_datetime >= datetime.now(timezone.utc),
            ~has_active_appointment,
            ~overlaps_blackout,
        )
        .order_by(AvailabilitySlot.slot_datetime.asc())
    )


async def search_professors(
    db: AsyncSession,
    q: str | None,
    faculty: Faculty | None,
    subject: str | None,
    consultation_type: ConsultationType | None,
) -> list[ProfessorSearchResponse]:
    statement = (
        select(Professor)
        .options(selectinload(Professor.user), selectinload(Professor.subjects))
        .join(User, Professor.user_id == User.id)
        .outerjoin(Subject, Subject.professor_id == Professor.id)
        .where(User.is_active.is_(True))
    )

    if faculty is not None:
        statement = statement.where(User.faculty == faculty)

    if q:
        # Diakritik-insensitive pretraga preko ``f_unaccent`` (migracija 0004).
        # Wrapper transformiše „Petrović" → „Petrovic" i „Đorđević" →
        # „Djordjevic", pa search „petrovic"/„djordjevic" matchuje. Obe
        # strane (kolona i needle) idu kroz istu funkciju da bi rezultat
        # bio simetričan. ``Subject.code`` je ASCII-only (npr. „IS101")
        # pa ostaje plain ILIKE — ekstra wrapper bi bio no-op overhead.
        # ``professors.areas_of_interest`` je TEXT[] pa koristimo
        # ``f_unaccent_array`` koji enkapsulira ``array_to_string`` +
        # ``f_unaccent``.
        needle = f"%{q.strip()}%"
        unaccent_needle = func.f_unaccent(needle)
        statement = statement.where(
            or_(
                func.f_unaccent(User.first_name).ilike(unaccent_needle),
                func.f_unaccent(User.last_name).ilike(unaccent_needle),
                func.f_unaccent(
                    func.concat(User.first_name, " ", User.last_name)
                ).ilike(unaccent_needle),
                func.f_unaccent(Professor.department).ilike(unaccent_needle),
                func.f_unaccent_array(Professor.areas_of_interest).ilike(
                    unaccent_needle
                ),
                func.f_unaccent(Subject.name).ilike(unaccent_needle),
                Subject.code.ilike(needle),
            )
        )

    if subject:
        subject_needle = f"%{subject.strip()}%"
        unaccent_subject_needle = func.f_unaccent(subject_needle)
        statement = statement.where(
            or_(
                func.f_unaccent(Subject.name).ilike(unaccent_subject_needle),
                Subject.code.ilike(subject_needle),
            )
        )

    if consultation_type is not None:
        has_slot_of_type = exists(
            _available_slots_query(Professor.id).where(
                AvailabilitySlot.consultation_type == consultation_type
            )
        )
        statement = statement.where(has_slot_of_type)

    result = await db.execute(statement.order_by(User.last_name.asc(), User.first_name.asc()))
    professors = result.scalars().unique().all()

    now_utc = datetime.now(timezone.utc)
    responses: list[ProfessorSearchResponse] = []
    for professor in professors:
        user = professor.user
        subject_names = sorted({s.name for s in professor.subjects if s.name})

        slot_types_result = await db.execute(
            select(AvailabilitySlot.consultation_type)
            .where(
                AvailabilitySlot.professor_id == professor.id,
                AvailabilitySlot.is_available.is_(True),
                AvailabilitySlot.slot_datetime >= now_utc,
            )
            .distinct()
        )
        consultation_types = [row[0] for row in slot_types_result.all()]

        responses.append(
            ProfessorSearchResponse(
                id=professor.id,
                full_name=f"{user.first_name} {user.last_name}",
                title=professor.title,
                department=professor.department,
                faculty=user.faculty,
                subjects=subject_names,
                consultation_types=consultation_types,
            )
        )

    return responses


async def list_professor_available_slots(
    db: AsyncSession,
    professor_id: UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[AvailableSlotResponse]:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date ne može biti pre start_date.",
        )

    professor_exists = await db.execute(select(Professor.id).where(Professor.id == professor_id))
    if professor_exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profesor nije pronađen.")

    statement = _available_slots_query(professor_id)
    if start_date is not None:
        statement = statement.where(func.date(AvailabilitySlot.slot_datetime) >= start_date)
    if end_date is not None:
        statement = statement.where(func.date(AvailabilitySlot.slot_datetime) <= end_date)

    slots_result = await db.execute(statement)
    slots = slots_result.scalars().all()
    return [AvailableSlotResponse.model_validate(slot) for slot in slots]


async def get_professor_profile(db: AsyncSession, professor_id: UUID) -> ProfessorProfileResponse:
    result = await db.execute(
        select(Professor)
        .options(selectinload(Professor.user), selectinload(Professor.subjects))
        .join(User, Professor.user_id == User.id)
        .where(Professor.id == professor_id, User.is_active.is_(True))
    )
    professor = result.scalar_one_or_none()

    if professor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesor nije pronađen.",
        )

    faq_result = await db.execute(
        select(FaqItem)
        .where(FaqItem.professor_id == professor.id)
        .order_by(FaqItem.sort_order.asc(), FaqItem.created_at.asc())
    )
    faq_items = faq_result.scalars().all()

    available_slots = await list_professor_available_slots(db, professor.id)

    user = professor.user
    return ProfessorProfileResponse(
        id=professor.id,
        full_name=f"{user.first_name} {user.last_name}",
        title=professor.title,
        department=professor.department,
        office=professor.office,
        office_description=professor.office_description,
        faculty=user.faculty,
        areas_of_interest=professor.areas_of_interest,
        subjects=sorted({subject.name for subject in professor.subjects if subject.name}),
        faq=[FaqResponse.model_validate(item) for item in faq_items],
        available_slots=available_slots,
    )
