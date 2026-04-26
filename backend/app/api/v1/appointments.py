"""Appointment detail / chat / files / participants router (Faza 3.3).

Endpoint inventory mirrors ``frontend/lib/api/appointments.ts`` 1:1:

    GET    /{id}                                        → AppointmentDetailResponse
    GET    /{id}/messages                               → list[ChatMessageResponse]
    POST   /{id}/messages                               → ChatMessageResponse
    GET    /{id}/files                                  → list[FileResponse]
    POST   /{id}/files                          (multipart "file") → FileResponse
    DELETE /{id}/files/{file_id}                        → MessageResponse
    GET    /{id}/participants                           → list[ParticipantResponse]
    POST   /{id}/participants/{participant_id}/confirm  → ParticipantResponse
    POST   /{id}/participants/{participant_id}/decline  → ParticipantResponse

All endpoints depend on ``CurrentUser`` (any authenticated, active user). RBAC
is enforced inside the service layer
(``appointment_detail_service.load_appointment_for_user``) so the same rules
apply to REST today and WS chat tomorrow (Faza 4.1).
"""

from uuid import UUID

from fastapi import APIRouter, File, UploadFile

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.appointment import (
    AppointmentDetailResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    FileResponse,
    ParticipantResponse,
)
from app.schemas.auth import MessageResponse
from app.services import appointment_detail_service, chat_service

router = APIRouter()


# ── Detail ───────────────────────────────────────────────────────────────────


@router.get(
    "/{id}",
    response_model=AppointmentDetailResponse,
    summary="Detalji termina (flat shape sa countovima)",
)
async def get_appointment_detail(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> AppointmentDetailResponse:
    return await appointment_detail_service.get_detail(db, current_user, id)


# ── Chat (REST polling fallback; WS upgrade in Faza 4.1) ──────────────────────


@router.get(
    "/{id}/messages",
    response_model=list[ChatMessageResponse],
    summary="Lista chat poruka za termin (max 20)",
)
async def list_chat_messages(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[ChatMessageResponse]:
    return await chat_service.list_messages(db, current_user, id)


@router.post(
    "/{id}/messages",
    response_model=ChatMessageResponse,
    status_code=201,
    summary="Slanje chat poruke (REST fallback dok WS ne live-uje)",
)
async def send_chat_message(
    id: UUID,
    data: ChatMessageCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> ChatMessageResponse:
    return await chat_service.send_message(db, current_user, id, data.content)


# ── Files ────────────────────────────────────────────────────────────────────


@router.get(
    "/{id}/files",
    response_model=list[FileResponse],
    summary="Lista fajlova sa presigned download URL-ovima (TTL 1h)",
)
async def list_appointment_files(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[FileResponse]:
    return await appointment_detail_service.list_files(db, current_user, id)


@router.post(
    "/{id}/files",
    response_model=FileResponse,
    status_code=201,
    summary="Otpremanje fajla (multipart, max 5MB, MIME whitelist)",
)
async def upload_appointment_file(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> FileResponse:
    return await appointment_detail_service.upload_file(db, current_user, id, file)


@router.delete(
    "/{id}/files/{file_id}",
    response_model=MessageResponse,
    summary="Brisanje sopstvenog fajla (uploader-only)",
)
async def delete_appointment_file(
    id: UUID,
    file_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> MessageResponse:
    await appointment_detail_service.delete_file(db, current_user, id, file_id)
    return MessageResponse(message="Fajl je obrisan.")


# ── Participants (group consultations) ───────────────────────────────────────


@router.get(
    "/{id}/participants",
    response_model=list[ParticipantResponse],
    summary="Lista učesnika (sa student_full_name kroz join)",
)
async def list_appointment_participants(
    id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[ParticipantResponse]:
    return await appointment_detail_service.list_participants(db, current_user, id)


@router.post(
    "/{id}/participants/{participant_id}/confirm",
    response_model=ParticipantResponse,
    summary="Potvrda sopstvenog učešća na grupnoj konsultaciji",
)
async def confirm_participation(
    id: UUID,
    participant_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> ParticipantResponse:
    return await appointment_detail_service.confirm_participant(
        db, current_user, id, participant_id
    )


@router.post(
    "/{id}/participants/{participant_id}/decline",
    response_model=ParticipantResponse,
    summary="Odbijanje sopstvenog učešća (lead ne može — neka otkaže termin)",
)
async def decline_participation(
    id: UUID,
    participant_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> ParticipantResponse:
    return await appointment_detail_service.decline_participant(
        db, current_user, id, participant_id
    )
