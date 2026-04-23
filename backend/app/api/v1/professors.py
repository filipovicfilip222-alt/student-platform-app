from uuid import UUID

from fastapi import APIRouter, Response, status

from app.core.dependencies import CurrentProfesor, DBSession
from app.schemas.auth import MessageResponse
from app.schemas.professor import (
    BlackoutCreate,
    BlackoutResponse,
    SlotCreate,
    SlotResponse,
    SlotUpdate,
)
from app.services import availability_service

router = APIRouter()


@router.get(
    "/slots",
    response_model=list[SlotResponse],
    summary="Lista dostupnih slotova profesora",
)
async def get_slots(
    db: DBSession,
    current_user: CurrentProfesor,
) -> list[SlotResponse]:
    slots = await availability_service.list_slots(db, current_user)
    return [SlotResponse.model_validate(slot) for slot in slots]


@router.post(
    "/slots",
    response_model=SlotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje novog availability slota",
)
async def create_slot(
    data: SlotCreate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> SlotResponse:
    slot = await availability_service.create_slot(db, current_user, data)
    return SlotResponse.model_validate(slot)


@router.put(
    "/slots/{slot_id}",
    response_model=SlotResponse,
    summary="Izmena availability slota",
)
async def update_slot(
    slot_id: UUID,
    data: SlotUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> SlotResponse:
    slot = await availability_service.update_slot(db, current_user, slot_id, data)
    return SlotResponse.model_validate(slot)


@router.delete(
    "/slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje availability slota",
)
async def delete_slot(
    slot_id: UUID,
    db: DBSession,
    current_user: CurrentProfesor,
) -> Response:
    await availability_service.delete_slot(db, current_user, slot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/blackout",
    response_model=BlackoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje blackout perioda",
)
async def create_blackout(
    data: BlackoutCreate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> BlackoutResponse:
    blackout = await availability_service.create_blackout(db, current_user, data)
    return BlackoutResponse.model_validate(blackout)


@router.delete(
    "/blackout/{blackout_id}",
    response_model=MessageResponse,
    summary="Brisanje blackout perioda",
)
async def delete_blackout(
    blackout_id: UUID,
    db: DBSession,
    current_user: CurrentProfesor,
) -> MessageResponse:
    await availability_service.delete_blackout(db, current_user, blackout_id)
    return MessageResponse(message="Blackout period uspešno obrisan.")
