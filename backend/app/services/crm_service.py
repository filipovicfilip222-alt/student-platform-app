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


async def _assert_assistant_can_access_student(
    db: AsyncSession,
    *,
    assistant_user: User,
    student_id: UUID,
) -> None:
    """KORAK 3 Prompta 2 / PRD §1.3 — strikni RBAC zid za asistenta.

    Asistent SME CRM samo za studenta koji je imao **bilo kakav
    Appointment** (status nebitan — istorija ostaje validna) za
    predmet kome je asistent dodeljen u ``subject_assistants``, ILI
    appointment koji je delegiran direktno asistentu (``delegated_to``).
    Drugi studenti (na predmetima gde asistent nije dodeljen) → 403.

    Uglovi:
      - Profesor i admin **NE prolaze** kroz ovaj helper (njih treba
        propustiti pre poziva). Ovo je explicit-asisistent provera.
      - Ne učitava CrmNote — samo Appointment (existence query, brz).
      - Vraća None na pristup; raise 403 inače.
    """
    if assistant_user.role != UserRole.ASISTENT:
        # Defenzivan check — caller je trebao da rutira pre.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="_assert_assistant_can_access_student je zvana za ne-asistenta.",
        )

    # Subjects gde je asistent dodeljen.
    subj_q = await db.execute(
        select(subject_assistants.c.subject_id).where(
            subject_assistants.c.assistant_id == assistant_user.id
        )
    )
    assistant_subject_ids = [row[0] for row in subj_q.all()]

    # Postoji li bilo kakav Appointment za studenta gde:
    #   (a) appointment je delegiran TOM asistentu, ili
    #   (b) appointment.subject_id je u listi asistentovih predmeta.
    from sqlalchemy import or_

    access_clauses = [Appointment.delegated_to == assistant_user.id]
    if assistant_subject_ids:
        access_clauses.append(Appointment.subject_id.in_(assistant_subject_ids))

    appt_q = await db.execute(
        select(Appointment.id)
        .where(
            Appointment.lead_student_id == student_id,
            or_(*access_clauses),
        )
        .limit(1)
    )
    if appt_q.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Nemate pristup ovom studentu. Asistent može da pravi CRM "
                "beleške samo za studente koji su imali termine sa Vama "
                "ili za predmete kojima ste dodeljeni."
            ),
        )


async def list_for_student(
    db: AsyncSession,
    current_user: User,
    student_id: UUID,
) -> list[CrmNote]:
    allowed_professor_ids = await _allowed_professor_ids_for_user(db, current_user)
    if current_user.role == UserRole.ASISTENT:
        await _assert_assistant_can_access_student(
            db, assistant_user=current_user, student_id=student_id
        )
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

    if current_user.role == UserRole.ASISTENT:
        await _assert_assistant_can_access_student(
            db, assistant_user=current_user, student_id=data.student_id
        )

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

    if current_user.role == UserRole.ASISTENT:
        await _assert_assistant_can_access_student(
            db, assistant_user=current_user, student_id=note.student_id
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

    if current_user.role == UserRole.ASISTENT:
        await _assert_assistant_can_access_student(
            db, assistant_user=current_user, student_id=note.student_id
        )

    await db.delete(note)
    await db.flush()
