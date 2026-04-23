from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentStudent, DBSession, RedisClient
from app.models.enums import ConsultationType, Faculty
from app.schemas.student import (
    AppointmentCancelResponse,
    AppointmentCreateRequest,
    AppointmentResponse,
    AvailableSlotResponse,
    ProfessorProfileResponse,
    ProfessorSearchResponse,
)
from app.services import booking_service, search_service

router = APIRouter()


@router.get(
    "/professors/search",
    response_model=list[ProfessorSearchResponse],
    summary="Pretraga profesora",
)
async def search_professors(
    db: DBSession,
    current_user: CurrentStudent,
    q: str | None = Query(default=None, min_length=1, max_length=200),
    faculty: Faculty | None = Query(default=None),
    subject: str | None = Query(default=None, min_length=1, max_length=200),
    type: ConsultationType | None = Query(default=None),
) -> list[ProfessorSearchResponse]:
    return await search_service.search_professors(
        db=db,
        q=q,
        faculty=faculty,
        subject=subject,
        consultation_type=type,
    )


@router.get(
    "/professors/{id}",
    response_model=ProfessorProfileResponse,
    summary="Profil profesora sa FAQ i dostupnim slotovima",
)
async def get_professor_profile(
    id: UUID,
    db: DBSession,
    current_user: CurrentStudent,
) -> ProfessorProfileResponse:
    return await search_service.get_professor_profile(db, id)


@router.get(
    "/professors/{id}/slots",
    response_model=list[AvailableSlotResponse],
    summary="Dostupni slotovi profesora",
)
async def get_professor_slots(
    id: UUID,
    db: DBSession,
    current_user: CurrentStudent,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> list[AvailableSlotResponse]:
    return await search_service.list_professor_available_slots(
        db=db,
        professor_id=id,
        start_date=start_date,
        end_date=end_date,
    )


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    summary="Zakazivanje termina",
)
async def create_appointment(
    data: AppointmentCreateRequest,
    db: DBSession,
    redis: RedisClient,
    current_user: CurrentStudent,
) -> AppointmentResponse:
    appointment = await booking_service.create_appointment(db, redis, current_user, data)
    return AppointmentResponse(
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
    )


@router.delete(
    "/appointments/{id}",
    response_model=AppointmentCancelResponse,
    summary="Otkazivanje termina (24h pravilo)",
)
async def cancel_appointment(
    id: UUID,
    db: DBSession,
    current_user: CurrentStudent,
) -> AppointmentCancelResponse:
    appointment = await booking_service.cancel_appointment(db, current_user, id)
    return AppointmentCancelResponse(id=appointment.id, status=appointment.status)


@router.get(
    "/appointments",
    response_model=list[AppointmentResponse],
    summary="Moji termini",
)
async def list_my_appointments(
    db: DBSession,
    current_user: CurrentStudent,
    view: Literal["upcoming", "history"] = Query(default="upcoming"),
) -> list[AppointmentResponse]:
    appointments = await booking_service.list_my_appointments(db, current_user, view)
    return [
        AppointmentResponse(
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
        )
        for appointment in appointments
    ]
