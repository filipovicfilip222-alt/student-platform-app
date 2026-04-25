from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.crm_note import CrmNote
from app.models.enums import UserRole
from app.models.subject import Subject, subject_assistants
from app.models.user import User
from app.schemas.professor import CrmNoteCreate, CrmNoteUpdate
from app.services.professor_portal_service import get_professor_or_404


async def _allowed_professor_ids_for_user(db: AsyncSession, current_user: User) -> list[UUID]:
    if current_user.role == UserRole.PROFESOR:
        professor = await get_professor_or_404(db, current_user.id)
        return [professor.id]

    if current_user.role == UserRole.ASISTENT:
        result = await db.execute(
            select(Appointment.professor_id)
            .where(Appointment.delegated_to == current_user.id)
        )
        delegated_professor_ids = {row[0] for row in result.all() if row[0] is not None}

        subject_result = await db.execute(
            select(Subject.professor_id)
            .join(subject_assistants, subject_assistants.c.subject_id == Subject.id)
            .where(
                subject_assistants.c.assistant_id == current_user.id,
                Subject.professor_id.is_not(None),
            )
        )
        subject_professor_ids = {row[0] for row in subject_result.all() if row[0] is not None}

        allowed = list(delegated_professor_ids | subject_professor_ids)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nemate pristup CRM beleškama.",
            )
        return allowed

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Nemate pristup CRM beleškama.",
    )


async def list_for_student(
    db: AsyncSession,
    current_user: User,
    student_id: UUID,
) -> list[CrmNote]:
    allowed_professor_ids = await _allowed_professor_ids_for_user(db, current_user)
    result = await db.execute(
        select(CrmNote)
        .where(
            CrmNote.student_id == student_id,
            CrmNote.professor_id.in_(allowed_professor_ids),
        )
        .order_by(CrmNote.updated_at.desc())
    )
    return result.scalars().all()


async def create_note(
    db: AsyncSession,
    current_user: User,
    data: CrmNoteCreate,
) -> CrmNote:
    allowed_professor_ids = await _allowed_professor_ids_for_user(db, current_user)

    professor_id = allowed_professor_ids[0]
    if current_user.role == UserRole.PROFESOR:
        professor_id = allowed_professor_ids[0]
    elif len(allowed_professor_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Asistent je vezan za više profesora; trenutno je potrebno delegiranje kroz konkretan termin.",
        )

    note = CrmNote(
        professor_id=professor_id,
        student_id=data.student_id,
        content=data.content.strip(),
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def update_note(
    db: AsyncSession,
    current_user: User,
    note_id: UUID,
    data: CrmNoteUpdate,
) -> CrmNote:
    allowed_professor_ids = await _allowed_professor_ids_for_user(db, current_user)
    result = await db.execute(
        select(CrmNote).where(
            CrmNote.id == note_id,
            CrmNote.professor_id.in_(allowed_professor_ids),
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CRM beleška nije pronađena.",
        )

    note.content = data.content.strip()
    await db.flush()
    await db.refresh(note)
    return note


async def delete_note(db: AsyncSession, current_user: User, note_id: UUID) -> None:
    allowed_professor_ids = await _allowed_professor_ids_for_user(db, current_user)
    result = await db.execute(
        select(CrmNote).where(
            CrmNote.id == note_id,
            CrmNote.professor_id.in_(allowed_professor_ids),
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CRM beleška nije pronađena.",
        )

    await db.delete(note)
    await db.flush()
