from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.canned_response import CannedResponse
from app.models.user import User
from app.schemas.professor import CannedResponseCreate, CannedResponseUpdate
from app.services.professor_portal_service import get_professor_or_404


async def list_mine(db: AsyncSession, current_user: User) -> list[CannedResponse]:
    professor = await get_professor_or_404(db, current_user.id)
    result = await db.execute(
        select(CannedResponse)
        .where(CannedResponse.professor_id == professor.id)
        .order_by(CannedResponse.created_at.desc())
    )
    return result.scalars().all()


async def create(
    db: AsyncSession,
    current_user: User,
    data: CannedResponseCreate,
) -> CannedResponse:
    professor = await get_professor_or_404(db, current_user.id)
    item = CannedResponse(
        professor_id=professor.id,
        title=data.title.strip(),
        content=data.content.strip(),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def update(
    db: AsyncSession,
    current_user: User,
    item_id: UUID,
    data: CannedResponseUpdate,
) -> CannedResponse:
    professor = await get_professor_or_404(db, current_user.id)
    result = await db.execute(
        select(CannedResponse).where(
            CannedResponse.id == item_id,
            CannedResponse.professor_id == professor.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Šablon nije pronađen.",
        )

    changes = data.model_dump(exclude_unset=True)
    if "title" in changes:
        changes["title"] = changes["title"].strip()
    if "content" in changes:
        changes["content"] = changes["content"].strip()

    for field, value in changes.items():
        setattr(item, field, value)

    await db.flush()
    await db.refresh(item)
    return item


async def delete(db: AsyncSession, current_user: User, item_id: UUID) -> None:
    professor = await get_professor_or_404(db, current_user.id)
    result = await db.execute(
        select(CannedResponse).where(
            CannedResponse.id == item_id,
            CannedResponse.professor_id == professor.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Šablon nije pronađen.",
        )

    await db.delete(item)
    await db.flush()
