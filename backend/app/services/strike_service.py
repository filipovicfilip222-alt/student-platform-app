from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strike import StrikeRecord, StudentBlock
from app.models.enums import StrikeReason


async def get_total_strike_points(db: AsyncSession, student_id: UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(StrikeRecord.points), 0)).where(
            StrikeRecord.student_id == student_id
        )
    )
    return int(result.scalar_one())


async def get_active_block(db: AsyncSession, student_id: UUID) -> StudentBlock | None:
    now_utc = datetime.now(timezone.utc)
    result = await db.execute(
        select(StudentBlock).where(
            StudentBlock.student_id == student_id,
            StudentBlock.blocked_until > now_utc,
        )
    )
    return result.scalar_one_or_none()


async def _apply_block_policy(
    db: AsyncSession,
    student_id: UUID,
    total_points: int,
) -> StudentBlock | None:
    now_utc = datetime.now(timezone.utc)

    result = await db.execute(select(StudentBlock).where(StudentBlock.student_id == student_id))
    block = result.scalar_one_or_none()

    if total_points < 3:
        return None

    if total_points == 3:
        if block is None:
            block = StudentBlock(
                student_id=student_id,
                blocked_until=now_utc + timedelta(days=14),
            )
            db.add(block)
        elif block.blocked_until <= now_utc:
            block.blocked_until = now_utc + timedelta(days=14)
        return block

    # 4+ poena: svaki sledeci prekrsaj produzava blokadu za 7 dana.
    if block is None:
        block = StudentBlock(
            student_id=student_id,
            blocked_until=now_utc + timedelta(days=21),
        )
        db.add(block)
        return block

    base_time = block.blocked_until if block.blocked_until > now_utc else now_utc
    block.blocked_until = base_time + timedelta(days=7)
    return block


async def add_strike(
    db: AsyncSession,
    student_id: UUID,
    appointment_id: UUID,
    reason: StrikeReason,
    points: int,
) -> tuple[StrikeRecord, int, StudentBlock | None]:
    existing_result = await db.execute(
        select(StrikeRecord).where(
            StrikeRecord.student_id == student_id,
            StrikeRecord.appointment_id == appointment_id,
            StrikeRecord.reason == reason,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        total_points = await get_total_strike_points(db, student_id)
        block = await get_active_block(db, student_id)
        return existing, total_points, block

    strike = StrikeRecord(
        student_id=student_id,
        appointment_id=appointment_id,
        reason=reason,
        points=points,
    )
    db.add(strike)
    await db.flush()

    total_points = await get_total_strike_points(db, student_id)
    block = await _apply_block_policy(db, student_id, total_points)
    await db.flush()

    return strike, total_points, block


async def add_late_cancel_strike(
    db: AsyncSession,
    student_id: UUID,
    appointment_id: UUID,
) -> tuple[StrikeRecord, int, StudentBlock | None]:
    return await add_strike(
        db=db,
        student_id=student_id,
        appointment_id=appointment_id,
        reason=StrikeReason.LATE_CANCEL,
        points=1,
    )


async def unblock_student(
    db: AsyncSession,
    student_id: UUID,
    removed_by: UUID,
    removal_reason: str | None = None,
) -> StudentBlock | None:
    result = await db.execute(select(StudentBlock).where(StudentBlock.student_id == student_id))
    block = result.scalar_one_or_none()
    if block is None:
        return None

    block.blocked_until = datetime.now(timezone.utc)
    block.removed_by = removed_by
    block.removal_reason = removal_reason
    await db.flush()
    return block
