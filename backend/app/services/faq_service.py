from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faq import FaqItem
from app.models.user import User
from app.schemas.professor import FaqCreate, FaqUpdate
from app.services.professor_portal_service import get_professor_or_404


async def list_mine(db: AsyncSession, current_user: User) -> list[FaqItem]:
    professor = await get_professor_or_404(db, current_user.id)
    result = await db.execute(
        select(FaqItem)
        .where(FaqItem.professor_id == professor.id)
        .order_by(FaqItem.sort_order.asc(), FaqItem.created_at.asc())
    )
    return result.scalars().all()


async def create(db: AsyncSession, current_user: User, data: FaqCreate) -> FaqItem:
    professor = await get_professor_or_404(db, current_user.id)
    item = FaqItem(
        professor_id=professor.id,
        question=data.question.strip(),
        answer=data.answer.strip(),
        sort_order=data.sort_order,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def update(
    db: AsyncSession,
    current_user: User,
    faq_id: UUID,
    data: FaqUpdate,
) -> FaqItem:
    professor = await get_professor_or_404(db, current_user.id)
    result = await db.execute(
        select(FaqItem).where(
            FaqItem.id == faq_id,
            FaqItem.professor_id == professor.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ stavka nije pronađena.",
        )

    changes = data.model_dump(exclude_unset=True)
    if "question" in changes:
        changes["question"] = changes["question"].strip()
    if "answer" in changes:
        changes["answer"] = changes["answer"].strip()

    for field, value in changes.items():
        setattr(item, field, value)

    await db.flush()
    await db.refresh(item)
    return item


async def delete(db: AsyncSession, current_user: User, faq_id: UUID) -> None:
    professor = await get_professor_or_404(db, current_user.id)
    result = await db.execute(
        select(FaqItem).where(
            FaqItem.id == faq_id,
            FaqItem.professor_id == professor.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ stavka nije pronađena.",
        )

    await db.delete(item)
    await db.flush()
