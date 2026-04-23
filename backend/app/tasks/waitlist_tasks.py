import asyncio
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import AppointmentStatus
from app.tasks.notifications import send_waitlist_offer
from app.services import waitlist_service


async def _iter_waitlist_slot_ids(redis: aioredis.Redis) -> list[UUID]:
    slot_ids: list[UUID] = []
    async for key in redis.scan_iter(match="waitlist:*"):
        if key.startswith("waitlist:offer:"):
            continue
        parts = key.split(":", maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            slot_ids.append(UUID(parts[1]))
        except ValueError:
            continue
    return slot_ids


async def _process_waitlist_offers_async() -> int:
    redis = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    sent_offers = 0

    try:
        slot_ids = await _iter_waitlist_slot_ids(redis)

        async with AsyncSessionLocal() as db:
            now_utc = datetime.now(timezone.utc)

            for slot_id in slot_ids:
                slot_result = await db.execute(
                    select(AvailabilitySlot)
                    .where(AvailabilitySlot.id == slot_id)
                )
                slot = slot_result.scalar_one_or_none()
                if slot is None:
                    continue
                if not slot.is_available or slot.slot_datetime <= now_utc:
                    continue

                active_count_result = await db.execute(
                    select(func.count(Appointment.id)).where(
                        Appointment.slot_id == slot_id,
                        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.APPROVED]),
                    )
                )
                active_count = int(active_count_result.scalar_one())
                seats_left = max(slot.max_students - active_count, 0)
                if seats_left == 0:
                    continue

                queue_members = await redis.zrange(waitlist_service.waitlist_key(slot_id), 0, 50)
                if not queue_members:
                    continue

                for member in queue_members:
                    if seats_left <= 0:
                        break

                    try:
                        candidate_id = UUID(member)
                    except ValueError:
                        continue

                    offered = await waitlist_service.issue_waitlist_offer(db, redis, slot_id, candidate_id)
                    if not offered:
                        continue

                    expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=waitlist_service.WAITLIST_OFFER_TTL_SECONDS
                    )
                    send_waitlist_offer.delay(
                        str(candidate_id),
                        str(slot_id),
                        expires_at.isoformat(),
                    )

                    sent_offers += 1
                    seats_left -= 1

            await db.commit()

        return sent_offers
    finally:
        await redis.close()


@celery_app.task(name="waitlist_tasks.process_waitlist_offers")
def process_waitlist_offers_task() -> int:
    return asyncio.run(_process_waitlist_offers_async())
