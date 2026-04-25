from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_request import DocumentRequest
from app.models.enums import DocumentStatus
from app.models.user import User
from app.schemas.document_request import (
    DocumentRequestApproveRequest,
    DocumentRequestCreate,
    DocumentRequestRejectRequest,
)


async def create_as_student(
    db: AsyncSession,
    student: User,
    data: DocumentRequestCreate,
) -> DocumentRequest:
    item = DocumentRequest(
        student_id=student.id,
        document_type=data.document_type,
        note=data.note.strip() if data.note else None,
        status=DocumentStatus.PENDING,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def list_my(db: AsyncSession, student: User) -> list[DocumentRequest]:
    result = await db.execute(
        select(DocumentRequest)
        .where(DocumentRequest.student_id == student.id)
        .order_by(DocumentRequest.created_at.desc())
    )
    return result.scalars().all()


async def list_for_admin(
    db: AsyncSession,
    status_filter: DocumentStatus | None,
) -> list[DocumentRequest]:
    statement = select(DocumentRequest).order_by(DocumentRequest.created_at.desc())
    if status_filter is not None:
        statement = statement.where(DocumentRequest.status == status_filter)

    result = await db.execute(statement)
    return result.scalars().all()


async def _get_or_404(db: AsyncSession, request_id: UUID) -> DocumentRequest:
    result = await db.execute(
        select(DocumentRequest).where(DocumentRequest.id == request_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zahtev za dokument nije pronađen.",
        )
    return item


async def approve(
    db: AsyncSession,
    admin: User,
    request_id: UUID,
    data: DocumentRequestApproveRequest,
) -> DocumentRequest:
    item = await _get_or_404(db, request_id)
    if item.status != DocumentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Samo PENDING zahtevi mogu biti odobreni.",
        )

    item.status = DocumentStatus.APPROVED
    item.pickup_date = data.pickup_date
    item.admin_note = data.admin_note.strip() if data.admin_note else None
    item.processed_by = admin.id

    await db.flush()
    await db.refresh(item)

    from app.tasks.notifications import send_document_request_approved

    send_document_request_approved.delay(
        str(item.student_id),
        item.document_type.value,
        item.pickup_date.isoformat(),
        item.admin_note or "",
    )
    return item


async def reject(
    db: AsyncSession,
    admin: User,
    request_id: UUID,
    data: DocumentRequestRejectRequest,
) -> DocumentRequest:
    item = await _get_or_404(db, request_id)
    if item.status != DocumentStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Samo PENDING zahtevi mogu biti odbijeni.",
        )

    item.status = DocumentStatus.REJECTED
    item.admin_note = data.admin_note.strip()
    item.pickup_date = None
    item.processed_by = admin.id

    await db.flush()
    await db.refresh(item)

    from app.tasks.notifications import send_document_request_rejected

    send_document_request_rejected.delay(
        str(item.student_id),
        item.document_type.value,
        item.admin_note,
    )
    return item


async def complete(
    db: AsyncSession,
    admin: User,
    request_id: UUID,
) -> DocumentRequest:
    item = await _get_or_404(db, request_id)
    if item.status != DocumentStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Samo APPROVED zahtevi mogu biti označeni kao preuzeti.",
        )

    item.status = DocumentStatus.COMPLETED
    item.processed_by = admin.id

    await db.flush()
    await db.refresh(item)
    return item
