from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import AppointmentStatus, UserRole
from app.models.faq import FaqItem
from app.models.professor import Professor
from app.models.subject import Subject, subject_assistants
from app.models.user import User
from app.schemas.professor import AssistantOptionResponse, ProfessorProfileUpdate


def _map_profile_response(professor: Professor) -> dict:
    user = professor.user
    return {
        "id": professor.id,
        "full_name": user.full_name,
        "email": user.email,
        "title": professor.title,
        "department": professor.department,
        "office": professor.office,
        "office_description": professor.office_description,
        "faculty": user.faculty,
        "areas_of_interest": professor.areas_of_interest,
        "auto_approve_recurring": professor.auto_approve_recurring,
        "auto_approve_special": professor.auto_approve_special,
        "buffer_minutes": professor.buffer_minutes,
    }


async def get_professor_or_404(db: AsyncSession, user_id: UUID) -> Professor:
    result = await db.execute(
        select(Professor)
        .options(selectinload(Professor.user))
        .where(Professor.user_id == user_id)
    )
    professor = result.scalar_one_or_none()
    if professor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesor profil nije pronađen.",
        )
    return professor


async def get_profile(db: AsyncSession, current_user: User) -> dict:
    professor = await get_professor_or_404(db, current_user.id)

    faq_result = await db.execute(
        select(FaqItem)
        .where(FaqItem.professor_id == professor.id)
        .order_by(FaqItem.sort_order.asc(), FaqItem.created_at.asc())
    )
    faq = faq_result.scalars().all()

    payload = _map_profile_response(professor)
    payload["faq"] = faq
    return payload


async def update_profile(
    db: AsyncSession,
    current_user: User,
    data: ProfessorProfileUpdate,
) -> dict:
    professor = await get_professor_or_404(db, current_user.id)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(professor, field, value)

    await db.flush()
    await db.refresh(professor)

    return await get_profile(db, current_user)


async def _assistant_subject_ids(db: AsyncSession, assistant_id: UUID) -> list[UUID]:
    result = await db.execute(
        select(subject_assistants.c.subject_id).where(
            subject_assistants.c.assistant_id == assistant_id
        )
    )
    return [row[0] for row in result.all()]


async def list_requests(
    db: AsyncSession,
    current_user: User,
    status_filter: str,
) -> list[Appointment]:
    statement = select(Appointment).options(
        selectinload(Appointment.slot),
        selectinload(Appointment.lead_student),
    )

    if current_user.role == UserRole.PROFESOR:
        professor = await get_professor_or_404(db, current_user.id)
        statement = statement.where(Appointment.professor_id == professor.id)
    else:
        subject_ids = await _assistant_subject_ids(db, current_user.id)
        assistant_filter = Appointment.delegated_to == current_user.id
        if subject_ids:
            statement = statement.where(
                assistant_filter | Appointment.subject_id.in_(subject_ids)
            )
        else:
            statement = statement.where(assistant_filter)

    if status_filter == "PENDING":
        statement = statement.where(Appointment.status == AppointmentStatus.PENDING)

    statement = statement.join(AvailabilitySlot, Appointment.slot_id == AvailabilitySlot.id)
    statement = statement.order_by(AvailabilitySlot.slot_datetime.asc())

    result = await db.execute(statement)
    return result.scalars().all()


async def _get_actionable_request_or_404(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> Appointment:
    result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zahtev nije pronađen.",
        )

    if current_user.role == UserRole.PROFESOR:
        professor = await get_professor_or_404(db, current_user.id)
        if appointment.professor_id != professor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nemate pristup ovom zahtevu.",
            )
        return appointment

    subject_ids = await _assistant_subject_ids(db, current_user.id)
    allowed = appointment.delegated_to == current_user.id
    if not allowed and subject_ids and appointment.subject_id is not None:
        allowed = appointment.subject_id in subject_ids

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemate pristup ovom zahtevu.",
        )

    return appointment


async def approve_request(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> Appointment:
    appointment = await _get_actionable_request_or_404(db, current_user, appointment_id)

    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Samo PENDING zahtevi mogu biti odobreni.",
        )

    appointment.status = AppointmentStatus.APPROVED
    appointment.rejection_reason = None

    await db.flush()

    from app.tasks.notifications import send_appointment_confirmed

    send_appointment_confirmed.delay(str(appointment.id))
    return appointment


async def reject_request(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    reason: str,
) -> Appointment:
    appointment = await _get_actionable_request_or_404(db, current_user, appointment_id)

    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Samo PENDING zahtevi mogu biti odbijeni.",
        )

    appointment.status = AppointmentStatus.REJECTED
    appointment.rejection_reason = reason.strip()

    await db.flush()

    from app.tasks.notifications import send_appointment_rejected

    send_appointment_rejected.delay(str(appointment.id), appointment.rejection_reason)
    return appointment


async def delegate_request(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    assistant_id: UUID,
) -> Appointment:
    if current_user.role != UserRole.PROFESOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Samo profesor može delegirati zahtev.",
        )

    professor = await get_professor_or_404(db, current_user.id)
    appointment = await _get_actionable_request_or_404(db, current_user, appointment_id)

    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Samo PENDING zahtevi mogu biti delegirani.",
        )

    assistant_result = await db.execute(
        select(User).where(User.id == assistant_id, User.role == UserRole.ASISTENT)
    )
    assistant = assistant_result.scalar_one_or_none()
    if assistant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asistent nije pronađen.",
        )

    if appointment.subject_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Termin nema dodeljen predmet za delegiranje.",
        )

    allowed_result = await db.execute(
        select(subject_assistants.c.assistant_id)
        .select_from(Subject)
        .join(subject_assistants, subject_assistants.c.subject_id == Subject.id)
        .where(
            Subject.id == appointment.subject_id,
            Subject.professor_id == professor.id,
            subject_assistants.c.assistant_id == assistant_id,
        )
    )
    if allowed_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Asistent nije dodeljen predmetu ovog zahteva.",
        )

    appointment.delegated_to = assistant_id
    await db.flush()
    return appointment


async def list_assistants(db: AsyncSession, current_user: User) -> list[AssistantOptionResponse]:
    professor = await get_professor_or_404(db, current_user.id)

    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.assistants))
        .where(Subject.professor_id == professor.id)
    )
    subjects = result.scalars().all()

    mapped_subjects: dict[UUID, set[str]] = defaultdict(set)
    mapped_user: dict[UUID, User] = {}
    for subject in subjects:
        for assistant in subject.assistants:
            mapped_user[assistant.id] = assistant
            mapped_subjects[assistant.id].add(subject.name)

    response: list[AssistantOptionResponse] = []
    for assistant_id, assistant in mapped_user.items():
        response.append(
            AssistantOptionResponse(
                id=assistant_id,
                full_name=assistant.full_name,
                email=assistant.email,
                subjects=sorted(mapped_subjects[assistant_id]),
            )
        )

    response.sort(key=lambda item: item.full_name)
    return response
