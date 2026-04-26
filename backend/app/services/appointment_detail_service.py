"""Appointment detail / files / participants service (Faza 3.3).

Owns:
    - The single RBAC gate (``load_appointment_for_user``) reused by both
      this service and ``chat_service`` to keep authorisation consistent.
    - The flat detail aggregate (``get_detail``) backing
      ``GET /appointments/{id}``.
    - File CRUD (``list_files`` / ``upload_file`` / ``delete_file``) backed by
      ``file_service`` (MinIO).
    - Participant read + self-action endpoints (``list_participants`` /
      ``confirm_participant`` / ``decline_participant``).

RBAC policy (CURSOR_PROMPT_1 §1.3 + websocket-schema.md §5.1):
    - Lead student (``appointment.lead_student_id``)
    - Participant student (row in ``appointment_participants``)
    - Professor (``appointment.professor.user_id``)
    - Delegated user — typically the assistant the professor delegated to
      (``appointment.delegated_to``)
    - Assistant assigned to ``appointment.subject`` via ``subject_assistants``
    - ADMIN without impersonation → 403 (must use POST /admin/impersonate;
      KORAK 6). With impersonation, ``get_current_user`` already returns the
      impersonated user, so we never see role=ADMIN here.
    - Anyone else → 403.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment, AppointmentParticipant
from app.models.chat import TicketChatMessage
from app.models.enums import (
    AppointmentStatus,
    ParticipantStatus,
    UserRole,
)
from app.models.file import File as FileModel
from app.models.subject import Subject
from app.models.user import User
from app.schemas.appointment import (
    AppointmentDetailResponse,
    FileResponse,
    ParticipantResponse,
)
from app.services import file_service


# ── RBAC + load helper ───────────────────────────────────────────────────────


async def load_appointment_for_user(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> Appointment:
    """Fetch an appointment with all relations needed for RBAC + detail.

    Raises:
        HTTPException(404): appointment doesn't exist.
        HTTPException(403): caller has no relationship to the appointment.

    The returned ORM object is eagerly loaded (``slot``, ``professor``,
    ``subject.assistants``, ``participants``) so downstream callers can read
    these attributes without triggering further round trips.
    """
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.slot),
            selectinload(Appointment.professor),
            selectinload(Appointment.subject).selectinload(Subject.assistants),
            selectinload(Appointment.participants),
        )
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Termin nije pronađen.",
        )

    if not _is_authorised(appointment, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemate pristup ovom terminu.",
        )

    return appointment


def _is_authorised(appointment: Appointment, current_user: User) -> bool:
    """Pure RBAC predicate. No DB access — relations must be loaded."""
    user_id = current_user.id

    if user_id == appointment.lead_student_id:
        return True
    if appointment.delegated_to is not None and user_id == appointment.delegated_to:
        return True
    if any(p.student_id == user_id for p in appointment.participants):
        return True

    if appointment.professor is not None and appointment.professor.user_id == user_id:
        return True

    if current_user.role == UserRole.ASISTENT and appointment.subject is not None:
        if any(a.id == user_id for a in appointment.subject.assistants):
            return True

    # ADMIN without impersonation falls through. Impersonation (KORAK 6) swaps
    # ``current_user`` to the target user before this layer sees it.
    return False


# ── Detail ───────────────────────────────────────────────────────────────────


async def get_detail(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> AppointmentDetailResponse:
    appointment = await load_appointment_for_user(db, current_user, appointment_id)

    chat_count = await db.scalar(
        select(func.count(TicketChatMessage.id)).where(
            TicketChatMessage.appointment_id == appointment_id
        )
    )
    file_count = await db.scalar(
        select(func.count(FileModel.id)).where(FileModel.appointment_id == appointment_id)
    )

    return AppointmentDetailResponse(
        id=appointment.id,
        slot_id=appointment.slot_id,
        professor_id=appointment.professor_id,
        lead_student_id=appointment.lead_student_id,
        subject_id=appointment.subject_id,
        topic_category=appointment.topic_category,
        description=appointment.description,
        status=appointment.status,
        consultation_type=appointment.consultation_type,
        slot_datetime=appointment.slot.slot_datetime,
        created_at=appointment.created_at,
        is_group=appointment.is_group,
        delegated_to=appointment.delegated_to,
        rejection_reason=appointment.rejection_reason,
        chat_message_count=int(chat_count or 0),
        file_count=int(file_count or 0),
    )


# ── Files ────────────────────────────────────────────────────────────────────


async def list_files(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> list[FileResponse]:
    await load_appointment_for_user(db, current_user, appointment_id)

    result = await db.execute(
        select(FileModel)
        .where(FileModel.appointment_id == appointment_id)
        .order_by(FileModel.created_at.desc())
    )
    files = list(result.scalars().all())

    out: list[FileResponse] = []
    for f in files:
        url = await file_service.presigned_get_url(f.minio_object_key)
        out.append(_to_file_response(f, download_url=url))
    return out


async def upload_file(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    upload: UploadFile,
) -> FileResponse:
    await load_appointment_for_user(db, current_user, appointment_id)

    # Read once; 5MB cap is enforced post-read by ``validate_upload``.
    # FastAPI/Starlette spools >1MB to disk so this is safe for the cap we use.
    data = await upload.read()
    filename = upload.filename or ""
    mime_type = upload.content_type or ""

    file_service.validate_upload(filename, mime_type, len(data))

    file_uuid = uuid4()
    object_key = await file_service.upload_appointment_file(
        appointment_id=appointment_id,
        file_uuid=file_uuid,
        filename=filename,
        data=data,
        mime_type=mime_type,
    )

    row = FileModel(
        id=file_uuid,
        appointment_id=appointment_id,
        uploaded_by=current_user.id,
        filename=filename,
        minio_object_key=object_key,
        file_size_bytes=len(data),
        mime_type=mime_type,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)

    download_url = await file_service.presigned_get_url(object_key)
    return _to_file_response(row, download_url=download_url)


async def delete_file(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    file_id: UUID,
) -> None:
    await load_appointment_for_user(db, current_user, appointment_id)

    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.appointment_id == appointment_id,
        )
    )
    file_row = result.scalar_one_or_none()
    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fajl nije pronađen.",
        )

    if file_row.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Možete da brišete samo fajlove koje ste sami otpremili.",
        )

    await file_service.delete_object(file_row.minio_object_key)
    await db.delete(file_row)
    await db.flush()


def _to_file_response(row: FileModel, download_url: str | None = None) -> FileResponse:
    return FileResponse(
        id=row.id,
        appointment_id=row.appointment_id,
        uploaded_by=row.uploaded_by,
        filename=row.filename,
        mime_type=row.mime_type,
        file_size_bytes=row.file_size_bytes,
        created_at=row.created_at,
        download_url=download_url,
    )


# ── Participants ─────────────────────────────────────────────────────────────


async def list_participants(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
) -> list[ParticipantResponse]:
    await load_appointment_for_user(db, current_user, appointment_id)

    result = await db.execute(
        select(AppointmentParticipant, User)
        .join(User, User.id == AppointmentParticipant.student_id)
        .where(AppointmentParticipant.appointment_id == appointment_id)
        .order_by(AppointmentParticipant.is_lead.desc(), User.last_name.asc())
    )
    rows = list(result.all())

    return [
        ParticipantResponse(
            id=p.id,
            appointment_id=p.appointment_id,
            student_id=p.student_id,
            status=p.status,
            is_lead=p.is_lead,
            confirmed_at=p.confirmed_at,
            student_full_name=u.full_name,
        )
        for (p, u) in rows
    ]


async def confirm_participant(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    participant_id: UUID,
) -> ParticipantResponse:
    return await _set_participant_status(
        db=db,
        current_user=current_user,
        appointment_id=appointment_id,
        participant_id=participant_id,
        new_status=ParticipantStatus.CONFIRMED,
    )


async def decline_participant(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    participant_id: UUID,
) -> ParticipantResponse:
    return await _set_participant_status(
        db=db,
        current_user=current_user,
        appointment_id=appointment_id,
        participant_id=participant_id,
        new_status=ParticipantStatus.DECLINED,
    )


async def _set_participant_status(
    db: AsyncSession,
    current_user: User,
    appointment_id: UUID,
    participant_id: UUID,
    new_status: ParticipantStatus,
) -> ParticipantResponse:
    # RBAC on the appointment (existence + access).
    appointment = await load_appointment_for_user(db, current_user, appointment_id)

    if appointment.status not in {AppointmentStatus.PENDING, AppointmentStatus.APPROVED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Termin više nije aktivan.",
        )

    result = await db.execute(
        select(AppointmentParticipant).where(
            AppointmentParticipant.id == participant_id,
            AppointmentParticipant.appointment_id == appointment_id,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Učesnik nije pronađen.",
        )

    if participant.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Možete da menjate samo svoju potvrdu.",
        )

    if participant.is_lead and new_status == ParticipantStatus.DECLINED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nosilac termina ne može da odbije termin (otkažite ga umesto toga).",
        )

    participant.status = new_status
    participant.confirmed_at = (
        datetime.now(timezone.utc) if new_status == ParticipantStatus.CONFIRMED else None
    )
    await db.flush()
    await db.refresh(participant)

    full_name_result = await db.execute(
        select(User.first_name, User.last_name).where(User.id == participant.student_id)
    )
    name_row = full_name_result.one_or_none()
    full_name = f"{name_row[0]} {name_row[1]}" if name_row else None

    return ParticipantResponse(
        id=participant.id,
        appointment_id=participant.appointment_id,
        student_id=participant.student_id,
        status=participant.status,
        is_lead=participant.is_lead,
        confirmed_at=participant.confirmed_at,
        student_full_name=full_name,
    )
