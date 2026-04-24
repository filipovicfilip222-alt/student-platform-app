import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import AppointmentStatus, StrikeReason
from app.models.strike import StrikeRecord
from app.services import strike_service


async def _detect_no_show_async() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment)
            .options(selectinload(Appointment.slot))
            .where(
                Appointment.status == AppointmentStatus.APPROVED,
                Appointment.slot.has(AvailabilitySlot.slot_datetime <= cutoff),
            )
            .order_by(Appointment.created_at.asc())
        )
        candidates = result.scalars().all()

        processed = 0
        for appointment in candidates:
            appointment_end = appointment.slot.slot_datetime + timedelta(
                minutes=appointment.slot.duration_minutes
            )
            if appointment_end > cutoff:
                continue

            # Avoid duplicate NO_SHOW strikes if task reruns.
            existing_strike_result = await db.execute(
                select(StrikeRecord.id).where(
                    StrikeRecord.appointment_id == appointment.id,
                    StrikeRecord.reason == StrikeReason.NO_SHOW,
                )
            )
            if existing_strike_result.scalar_one_or_none() is not None:
                continue

            await strike_service.add_strike(
                db=db,
                student_id=appointment.lead_student_id,
                appointment_id=appointment.id,
                reason=StrikeReason.NO_SHOW,
                points=2,
            )
            appointment.status = AppointmentStatus.NO_SHOW
            processed += 1

        await db.commit()
        return processed


@celery_app.task(name="strike_tasks.detect_no_show")
def detect_no_show_task() -> int:
    return asyncio.run(_detect_no_show_async())
