from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.dependencies import CurrentProfesor, CurrentProfesorOrAsistent, DBSession
from app.schemas.auth import MessageResponse
from app.schemas.professor import (
    AssistantOptionResponse,
    BlackoutCreate,
    BlackoutResponse,
    CannedResponseCreate,
    CannedResponseResponse,
    CannedResponseUpdate,
    CrmNoteCreate,
    CrmNoteResponse,
    CrmNoteUpdate,
    FaqCreate,
    FaqResponse,
    FaqUpdate,
    ProfessorMeResponse,
    ProfessorProfileUpdate,
    RequestDelegateRequest,
    RequestInboxRow,
    RequestRejectRequest,
    SlotCreate,
    SlotResponse,
    SlotUpdate,
)
from app.services import (
    availability_service,
    canned_response_service,
    crm_service,
    faq_service,
    professor_portal_service,
)

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


@router.get(
    "/blackout",
    response_model=list[BlackoutResponse],
    summary="Lista blackout perioda",
)
async def list_blackouts(
    db: DBSession,
    current_user: CurrentProfesor,
) -> list[BlackoutResponse]:
    items = await availability_service.list_blackouts(db, current_user)
    return [BlackoutResponse.model_validate(item) for item in items]


@router.get(
    "/profile",
    response_model=ProfessorMeResponse,
    summary="Sopstveni profil profesora",
)
async def get_profile(
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> ProfessorMeResponse:
    profile = await professor_portal_service.get_profile(db, current_user)
    return ProfessorMeResponse.model_validate(profile)


@router.put(
    "/profile",
    response_model=ProfessorMeResponse,
    summary="Izmena sopstvenog profila",
)
async def update_profile_put(
    data: ProfessorProfileUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> ProfessorMeResponse:
    profile = await professor_portal_service.update_profile(db, current_user, data)
    return ProfessorMeResponse.model_validate(profile)


@router.patch(
    "/profile",
    response_model=ProfessorMeResponse,
    summary="Parcijalna izmena sopstvenog profila",
)
async def update_profile_patch(
    data: ProfessorProfileUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> ProfessorMeResponse:
    profile = await professor_portal_service.update_profile(db, current_user, data)
    return ProfessorMeResponse.model_validate(profile)


@router.get(
    "/requests",
    response_model=list[RequestInboxRow],
    summary="Inbox zahteva za konsultacije",
)
async def list_requests(
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
    status: str = Query(default="PENDING", pattern="^(PENDING|ALL)$"),
) -> list[RequestInboxRow]:
    items = await professor_portal_service.list_requests(db, current_user, status)
    return [
        RequestInboxRow(
            id=item.id,
            slot_id=item.slot_id,
            professor_id=item.professor_id,
            lead_student_id=item.lead_student_id,
            subject_id=item.subject_id,
            topic_category=item.topic_category,
            description=item.description,
            status=item.status,
            consultation_type=item.consultation_type,
            slot_datetime=item.slot.slot_datetime,
            created_at=item.created_at,
            rejection_reason=item.rejection_reason,
            delegated_to=item.delegated_to,
            lead_student_name=item.lead_student.full_name if item.lead_student else None,
        )
        for item in items
    ]


@router.post(
    "/requests/{appointment_id}/approve",
    response_model=RequestInboxRow,
    summary="Odobravanje zahteva",
)
async def approve_request(
    appointment_id: UUID,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> RequestInboxRow:
    item = await professor_portal_service.approve_request(db, current_user, appointment_id)
    return RequestInboxRow(
        id=item.id,
        slot_id=item.slot_id,
        professor_id=item.professor_id,
        lead_student_id=item.lead_student_id,
        subject_id=item.subject_id,
        topic_category=item.topic_category,
        description=item.description,
        status=item.status,
        consultation_type=item.consultation_type,
        slot_datetime=item.slot.slot_datetime,
        created_at=item.created_at,
        rejection_reason=item.rejection_reason,
        delegated_to=item.delegated_to,
    )


@router.post(
    "/requests/{appointment_id}/reject",
    response_model=RequestInboxRow,
    summary="Odbijanje zahteva",
)
async def reject_request(
    appointment_id: UUID,
    data: RequestRejectRequest,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> RequestInboxRow:
    item = await professor_portal_service.reject_request(db, current_user, appointment_id, data.reason)
    return RequestInboxRow(
        id=item.id,
        slot_id=item.slot_id,
        professor_id=item.professor_id,
        lead_student_id=item.lead_student_id,
        subject_id=item.subject_id,
        topic_category=item.topic_category,
        description=item.description,
        status=item.status,
        consultation_type=item.consultation_type,
        slot_datetime=item.slot.slot_datetime,
        created_at=item.created_at,
        rejection_reason=item.rejection_reason,
        delegated_to=item.delegated_to,
    )


@router.post(
    "/requests/{appointment_id}/delegate",
    response_model=RequestInboxRow,
    summary="Delegiranje zahteva asistentu",
)
async def delegate_request(
    appointment_id: UUID,
    data: RequestDelegateRequest,
    db: DBSession,
    current_user: CurrentProfesor,
) -> RequestInboxRow:
    item = await professor_portal_service.delegate_request(
        db,
        current_user,
        appointment_id,
        data.assistant_id,
    )
    return RequestInboxRow(
        id=item.id,
        slot_id=item.slot_id,
        professor_id=item.professor_id,
        lead_student_id=item.lead_student_id,
        subject_id=item.subject_id,
        topic_category=item.topic_category,
        description=item.description,
        status=item.status,
        consultation_type=item.consultation_type,
        slot_datetime=item.slot.slot_datetime,
        created_at=item.created_at,
        rejection_reason=item.rejection_reason,
        delegated_to=item.delegated_to,
    )


@router.get(
    "/assistants",
    response_model=list[AssistantOptionResponse],
    summary="Lista asistenata dodeljenih predmetima profesora",
)
async def list_assistants(
    db: DBSession,
    current_user: CurrentProfesor,
) -> list[AssistantOptionResponse]:
    return await professor_portal_service.list_assistants(db, current_user)


@router.get(
    "/canned-responses",
    response_model=list[CannedResponseResponse],
    summary="Lista canned response šablona",
)
async def list_canned_responses(
    db: DBSession,
    current_user: CurrentProfesor,
) -> list[CannedResponseResponse]:
    items = await canned_response_service.list_mine(db, current_user)
    return [CannedResponseResponse.model_validate(item) for item in items]


@router.post(
    "/canned-responses",
    response_model=CannedResponseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje canned response šablona",
)
async def create_canned_response(
    data: CannedResponseCreate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> CannedResponseResponse:
    item = await canned_response_service.create(db, current_user, data)
    return CannedResponseResponse.model_validate(item)


@router.put(
    "/canned-responses/{item_id}",
    response_model=CannedResponseResponse,
    summary="Izmena canned response šablona",
)
async def update_canned_response_put(
    item_id: UUID,
    data: CannedResponseUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> CannedResponseResponse:
    item = await canned_response_service.update(db, current_user, item_id, data)
    return CannedResponseResponse.model_validate(item)


@router.patch(
    "/canned-responses/{item_id}",
    response_model=CannedResponseResponse,
    summary="Parcijalna izmena canned response šablona",
)
async def update_canned_response_patch(
    item_id: UUID,
    data: CannedResponseUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> CannedResponseResponse:
    item = await canned_response_service.update(db, current_user, item_id, data)
    return CannedResponseResponse.model_validate(item)


@router.delete(
    "/canned-responses/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje canned response šablona",
)
async def delete_canned_response(
    item_id: UUID,
    db: DBSession,
    current_user: CurrentProfesor,
) -> Response:
    await canned_response_service.delete(db, current_user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/faq",
    response_model=list[FaqResponse],
    summary="Lista FAQ stavki profesora",
)
async def list_faq(
    db: DBSession,
    current_user: CurrentProfesor,
) -> list[FaqResponse]:
    items = await faq_service.list_mine(db, current_user)
    return [FaqResponse.model_validate(item) for item in items]


@router.post(
    "/faq",
    response_model=FaqResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje FAQ stavke",
)
async def create_faq(
    data: FaqCreate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> FaqResponse:
    item = await faq_service.create(db, current_user, data)
    return FaqResponse.model_validate(item)


@router.put(
    "/faq/{faq_id}",
    response_model=FaqResponse,
    summary="Izmena FAQ stavke",
)
async def update_faq_put(
    faq_id: UUID,
    data: FaqUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> FaqResponse:
    item = await faq_service.update(db, current_user, faq_id, data)
    return FaqResponse.model_validate(item)


@router.patch(
    "/faq/{faq_id}",
    response_model=FaqResponse,
    summary="Parcijalna izmena FAQ stavke",
)
async def update_faq_patch(
    faq_id: UUID,
    data: FaqUpdate,
    db: DBSession,
    current_user: CurrentProfesor,
) -> FaqResponse:
    item = await faq_service.update(db, current_user, faq_id, data)
    return FaqResponse.model_validate(item)


@router.delete(
    "/faq/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje FAQ stavke",
)
async def delete_faq(
    faq_id: UUID,
    db: DBSession,
    current_user: CurrentProfesor,
) -> Response:
    await faq_service.delete(db, current_user, faq_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/crm/{student_id}",
    response_model=list[CrmNoteResponse],
    summary="CRM beleške za studenta",
)
async def list_crm_notes_by_path(
    student_id: UUID,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> list[CrmNoteResponse]:
    notes = await crm_service.list_for_student(db, current_user, student_id)
    return [CrmNoteResponse.model_validate(note) for note in notes]


@router.post(
    "/crm/{student_id}",
    response_model=CrmNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje CRM beleške za studenta",
)
async def create_crm_note_by_path(
    student_id: UUID,
    data: CrmNoteUpdate,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> CrmNoteResponse:
    note = await crm_service.create_note(
        db,
        current_user,
        CrmNoteCreate(student_id=student_id, content=data.content),
    )
    return CrmNoteResponse.model_validate(note)


@router.put(
    "/crm/{note_id}",
    response_model=CrmNoteResponse,
    summary="Izmena CRM beleške",
)
async def update_crm_note_put(
    note_id: UUID,
    data: CrmNoteUpdate,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> CrmNoteResponse:
    note = await crm_service.update_note(db, current_user, note_id, data)
    return CrmNoteResponse.model_validate(note)


@router.delete(
    "/crm/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje CRM beleške",
)
async def delete_crm_note_by_path(
    note_id: UUID,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> Response:
    await crm_service.delete_note(db, current_user, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/crm-notes",
    response_model=list[CrmNoteResponse],
    summary="CRM beleške (frontend kompatibilnost)",
)
async def list_crm_notes(
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
    student_id: UUID = Query(...),
) -> list[CrmNoteResponse]:
    notes = await crm_service.list_for_student(db, current_user, student_id)
    return [CrmNoteResponse.model_validate(note) for note in notes]


@router.post(
    "/crm-notes",
    response_model=CrmNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Kreiranje CRM beleške (frontend kompatibilnost)",
)
async def create_crm_note(
    data: CrmNoteCreate,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> CrmNoteResponse:
    note = await crm_service.create_note(db, current_user, data)
    return CrmNoteResponse.model_validate(note)


@router.patch(
    "/crm-notes/{note_id}",
    response_model=CrmNoteResponse,
    summary="Parcijalna izmena CRM beleške",
)
async def update_crm_note_patch(
    note_id: UUID,
    data: CrmNoteUpdate,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> CrmNoteResponse:
    note = await crm_service.update_note(db, current_user, note_id, data)
    return CrmNoteResponse.model_validate(note)


@router.delete(
    "/crm-notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Brisanje CRM beleške (frontend kompatibilnost)",
)
async def delete_crm_note(
    note_id: UUID,
    db: DBSession,
    current_user: CurrentProfesorOrAsistent,
) -> Response:
    await crm_service.delete_note(db, current_user, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
