from uuid import UUID

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentAdmin, DBSession
from app.models.enums import DocumentStatus
from app.schemas.document_request import (
    DocumentRequestApproveRequest,
    DocumentRequestRejectRequest,
    DocumentRequestResponse,
)
from app.services import document_request_service

router = APIRouter()


@router.get(
    "/document-requests",
    response_model=list[DocumentRequestResponse],
    summary="Inbox zahteva za dokumente",
)
async def list_document_requests(
    db: DBSession,
    current_user: CurrentAdmin,
    status: DocumentStatus | None = Query(default=None),
) -> list[DocumentRequestResponse]:
    items = await document_request_service.list_for_admin(db, status)
    return [DocumentRequestResponse.model_validate(item) for item in items]


@router.post(
    "/document-requests/{request_id}/approve",
    response_model=DocumentRequestResponse,
    summary="Odobravanje zahteva za dokument",
)
async def approve_document_request(
    request_id: UUID,
    data: DocumentRequestApproveRequest,
    db: DBSession,
    current_user: CurrentAdmin,
) -> DocumentRequestResponse:
    item = await document_request_service.approve(db, current_user, request_id, data)
    return DocumentRequestResponse.model_validate(item)


@router.post(
    "/document-requests/{request_id}/reject",
    response_model=DocumentRequestResponse,
    summary="Odbijanje zahteva za dokument",
)
async def reject_document_request(
    request_id: UUID,
    data: DocumentRequestRejectRequest,
    db: DBSession,
    current_user: CurrentAdmin,
) -> DocumentRequestResponse:
    item = await document_request_service.reject(db, current_user, request_id, data)
    return DocumentRequestResponse.model_validate(item)


@router.post(
    "/document-requests/{request_id}/complete",
    response_model=DocumentRequestResponse,
    summary="Označavanje zahteva kao preuzetog",
)
async def complete_document_request(
    request_id: UUID,
    db: DBSession,
    current_user: CurrentAdmin,
) -> DocumentRequestResponse:
    item = await document_request_service.complete(db, current_user, request_id)
    return DocumentRequestResponse.model_validate(item)
