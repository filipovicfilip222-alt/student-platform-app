"""
Availability service — single & recurring slot lifecycle for professors.

ROADMAP §3.7 covers single slots; §3.8 expands recurring rules into
N concrete `AvailabilitySlot` rows linked by `recurring_group_id`.

Recurring expansion semantics:
  - Frontend sends a `RecurringRule` payload (see `schemas.professor.RecurringRule`)
    using JS-style weekday integers (0=Sunday, 1=Monday, …, 6=Saturday).
  - Service translates those to `dateutil.rrule` weekday constants and
    materializes every concrete `slot_datetime` in the series.
  - Hard cap: 100 slots per series. Anything larger is rejected with 422
    "prevelik raspon" — protects against runaway rules and the JSONB blob
    in `recurring_rule` from drifting in size.
  - Before any rows are inserted, every generated `slot_datetime` is
    cross-checked against existing APPROVED appointments for that
    professor; any overlap aborts the operation with 422 + a list of
    conflicts (frontend can show a "free up these times first" dialog).

Recurring deletion semantics:
  - Only future slots (`slot_datetime > now()`) are touched. Past slots
    stay for audit / reporting (acceptance §3.8).
  - If any future slot in the group has an APPROVED appointment we
    return 409 with the conflict list — caller (the professor) must
    explicitly cancel those appointments first.
"""

import logging
from datetime import datetime, time, timezone
from uuid import UUID, uuid4

import redis.asyncio as aioredis
from dateutil.rrule import (
    FR,
    MO,
    MONTHLY,
    SA,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    rrule,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot, BlackoutDate
from app.models.enums import AppointmentStatus
from app.models.professor import Professor
from app.models.user import User
from app.schemas.professor import (
    BlackoutCreate,
    RecurringConflict,
    RecurringRule,
    SlotCreate,
    SlotUpdate,
)
from app.services import waitlist_service

_log = logging.getLogger(__name__)

# KORAK 2 Prompta 2 / PRD §3.1 — eksplicitan razlog za blackout-cancel.
# Frontend (`/my-appointments` history) detektuje override case po prefiksu
# i prikazuje ikonu profesorovog blackout-a umesto generic "otkazan".
BLACKOUT_OVERRIDE_REASON_PREFIX = (
    "Profesor je rezervisao termin za drugu obavezu"
)

MAX_RECURRING_SLOTS = 100
# Largest single slot duration allowed by SlotCreate (`le=480`). Used to
# size the conflict-detection prefetch window so we never miss an
# overlapping APPROVED appointment that started slightly before the
# series window.
_MAX_SLOT_MINUTES = 480

# JS Date.getDay() → dateutil rrule weekday constants
_JS_TO_DATEUTIL_WEEKDAY = {
    0: SU,
    1: MO,
    2: TU,
    3: WE,
    4: TH,
    5: FR,
    6: SA,
}


async def _get_professor_profile_or_404(db: AsyncSession, user_id: UUID) -> Professor:
    result = await db.execute(select(Professor).where(Professor.user_id == user_id))
    professor = result.scalar_one_or_none()
    if not professor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesor profil nije pronađen.",
        )
    return professor


# ── Recurring expansion ───────────────────────────────────────────────────────
def _expand_recurring_rule(
    *,
    slot_datetime: datetime,
    rule: RecurringRule,
) -> list[datetime]:
    """
    Materialize a recurring rule into concrete UTC `slot_datetime` values.

    Caller guarantees `slot_datetime` is timezone-aware (Pydantic parses
    the ISO string from the frontend with TZ info). The `until` field
    is interpreted as inclusive end-of-day in UTC so the last day still
    fires.
    """
    freq_map = {"WEEKLY": WEEKLY, "MONTHLY": MONTHLY}
    freq_const = freq_map[rule.freq]

    byweekday = None
    if rule.by_weekday is not None:
        byweekday = tuple(_JS_TO_DATEUTIL_WEEKDAY[d] for d in rule.by_weekday)

    until_dt: datetime | None = None
    if rule.until is not None:
        until_dt = datetime.combine(
            rule.until,
            time(23, 59, 59),
            tzinfo=timezone.utc,
        )

    # Cap at MAX_RECURRING_SLOTS + 1 so we can detect "too many" without
    # iterating an unbounded series — rrule.count enforces upper bound,
    # but `until` may also produce more than the cap and we want to
    # report 422 in that case too.
    rule_obj = rrule(
        freq=freq_const,
        dtstart=slot_datetime,
        interval=rule.interval,
        byweekday=byweekday,
        count=rule.count,
        until=until_dt,
    )

    occurrences: list[datetime] = []
    for occ in rule_obj:
        occurrences.append(occ)
        if len(occurrences) > MAX_RECURRING_SLOTS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Prevelik raspon — rekurentno pravilo bi proizvelo više od "
                    f"{MAX_RECURRING_SLOTS} slotova. Suzite raspon (count, until "
                    f"ili by_weekday)."
                ),
            )

    if not occurrences:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Rekurentno pravilo ne proizvodi nijedan slot. Proverite "
                "by_weekday i raspon datuma."
            ),
        )

    return occurrences


async def _check_recurring_conflicts(
    db: AsyncSession,
    *,
    professor_id: UUID,
    new_starts: list[datetime],
    duration_minutes: int,
) -> list[RecurringConflict]:
    """
    Find APPROVED appointments owned by ``professor_id`` whose slot
    interval overlaps any of the new ``(start, start + duration)`` windows.

    Two intervals [a, b) and [c, d) overlap iff a < d AND c < b. We
    prefetch all candidate appointments in the bounding window
    [min_new − max_slot, max_new + duration] and then do the precise
    pairwise check in Python — this keeps the SQL simple while still
    being O(N * M) for N new × M existing, both bounded (N ≤ 100,
    M typically << 1000 over a season).
    """
    if not new_starts:
        return []

    duration_td = _td_minutes(duration_minutes)
    new_intervals = [(s, s + duration_td) for s in new_starts]

    window_start = min(new_starts) - _td_minutes(_MAX_SLOT_MINUTES)
    window_end = max(end for _, end in new_intervals)

    result = await db.execute(
        select(Appointment, AvailabilitySlot)
        .join(AvailabilitySlot, Appointment.slot_id == AvailabilitySlot.id)
        .where(
            Appointment.professor_id == professor_id,
            Appointment.status == AppointmentStatus.APPROVED,
            AvailabilitySlot.slot_datetime >= window_start,
            AvailabilitySlot.slot_datetime < window_end,
        )
    )
    candidates = result.all()

    conflicts: list[RecurringConflict] = []
    for appointment, slot in candidates:
        existing_start = slot.slot_datetime
        existing_end = existing_start + _td_minutes(slot.duration_minutes)
        for new_start, new_end in new_intervals:
            if existing_start < new_end and new_start < existing_end:
                conflicts.append(
                    RecurringConflict(
                        slot_datetime=new_start,
                        appointment_id=appointment.id,
                        reason=(
                            f"Preklapa sa odobrenim terminom u "
                            f"{existing_start.isoformat()}."
                        ),
                    )
                )
                # One conflict per (existing, new) pair is enough — keep
                # iterating new_intervals so a single existing appt that
                # blocks multiple new slots is still surfaced fully.
    return conflicts


def _td_minutes(minutes: int):
    from datetime import timedelta

    return timedelta(minutes=minutes)


# ── CRUD ──────────────────────────────────────────────────────────────────────
async def list_slots(db: AsyncSession, current_user: User) -> list[AvailabilitySlot]:
    professor = await _get_professor_profile_or_404(db, current_user.id)
    result = await db.execute(
        select(AvailabilitySlot)
        .where(AvailabilitySlot.professor_id == professor.id)
        .order_by(AvailabilitySlot.slot_datetime.asc())
    )
    return list(result.scalars().all())


async def create_slot(
    db: AsyncSession,
    current_user: User,
    data: SlotCreate,
    redis: aioredis.Redis | None = None,
) -> list[AvailabilitySlot]:
    """
    Create one slot or expand a recurring rule into N linked slots.

    Returns a list — single-shot creation returns ``[slot]``, recurring
    creation returns all generated rows in chronological order, all
    sharing the same ``recurring_group_id``.

    KORAK 2 Prompta 2 hook: ako je ``redis`` prosleđen, novokreirani
    slot(ovi) se preliva(ju) prioritetnim članovima profesorove
    ``waitlist:priority:{professor_id}`` ZSET-e (FIFO sa negativnim
    score-om — članovi blackout override-a su PRVI kad waitlist offer
    okida). Bez ``redis``-a (legacy backwards-compatible) hook se
    preskače — slot se kreira ali bez priority preliva, što je OK za
    test/utility pozive koji ne trebaju Redis.
    """
    professor = await _get_professor_profile_or_404(db, current_user.id)

    # ── Single slot path ──────────────────────────────────────────────────
    if data.recurring_rule is None:
        slot = AvailabilitySlot(
            professor_id=professor.id,
            slot_datetime=data.slot_datetime,
            duration_minutes=data.duration_minutes,
            consultation_type=data.consultation_type,
            max_students=data.max_students,
            online_link=data.online_link,
            is_available=data.is_available,
            recurring_rule=None,
            recurring_group_id=None,
            valid_from=data.valid_from,
            valid_until=data.valid_until,
        )
        db.add(slot)
        await db.flush()
        await db.refresh(slot)

        if redis is not None:
            await waitlist_service.seed_slot_with_priority(
                redis, slot_id=slot.id, professor_id=professor.id
            )

        return [slot]

    # ── Recurring path ────────────────────────────────────────────────────
    occurrences = _expand_recurring_rule(
        slot_datetime=data.slot_datetime,
        rule=data.recurring_rule,
    )

    conflicts = await _check_recurring_conflicts(
        db,
        professor_id=professor.id,
        new_starts=occurrences,
        duration_minutes=data.duration_minutes,
    )
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    "Rekurentni slotovi se preklapaju sa postojećim odobrenim "
                    "terminima. Otkažite ih ili promenite pravilo."
                ),
                "conflicts": [c.model_dump(mode="json") for c in conflicts],
            },
        )

    group_id = uuid4()
    rule_payload = data.recurring_rule.model_dump(mode="json", exclude_none=True)

    new_slots: list[AvailabilitySlot] = []
    for occ in occurrences:
        slot = AvailabilitySlot(
            professor_id=professor.id,
            slot_datetime=occ,
            duration_minutes=data.duration_minutes,
            consultation_type=data.consultation_type,
            max_students=data.max_students,
            online_link=data.online_link,
            is_available=data.is_available,
            recurring_rule=rule_payload,
            recurring_group_id=group_id,
            valid_from=data.valid_from,
            valid_until=data.valid_until,
        )
        db.add(slot)
        new_slots.append(slot)

    await db.flush()
    for slot in new_slots:
        await db.refresh(slot)

    if redis is not None:
        for slot in new_slots:
            await waitlist_service.seed_slot_with_priority(
                redis, slot_id=slot.id, professor_id=professor.id
            )

    return new_slots


async def update_slot(
    db: AsyncSession,
    current_user: User,
    slot_id: UUID,
    data: SlotUpdate,
) -> AvailabilitySlot:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    result = await db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id,
            AvailabilitySlot.professor_id == professor.id,
        )
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot nije pronađen.",
        )

    changes = data.model_dump(exclude_unset=True)
    # `recurring_rule` is a Pydantic model in the request schema; the
    # column stores plain JSON — flatten before assignment.
    if "recurring_rule" in changes and changes["recurring_rule"] is not None:
        rr = data.recurring_rule
        changes["recurring_rule"] = (
            rr.model_dump(mode="json", exclude_none=True) if rr is not None else None
        )
    for field, value in changes.items():
        setattr(slot, field, value)

    await db.flush()
    await db.refresh(slot)
    return slot


async def delete_slot(db: AsyncSession, current_user: User, slot_id: UUID) -> None:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    result = await db.execute(
        select(AvailabilitySlot).where(
            AvailabilitySlot.id == slot_id,
            AvailabilitySlot.professor_id == professor.id,
        )
    )
    slot = result.scalar_one_or_none()

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot nije pronađen.",
        )

    appointment_exists = await db.execute(
        select(Appointment.id).where(Appointment.slot_id == slot.id)
    )
    if appointment_exists.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot ima povezane termine i ne može biti obrisan.",
        )

    await db.delete(slot)
    await db.flush()


async def delete_recurring_group(
    db: AsyncSession,
    current_user: User,
    group_id: UUID,
) -> int:
    """
    Delete all *future* slots belonging to a recurring group owned by
    ``current_user``'s professor profile. Past slots (``slot_datetime
    <= now()``) are preserved for audit.

    Returns the number of deleted rows.

    Raises:
      404 — no future slots exist for this group (either bad id or the
            entire series is already in the past).
      409 — at least one future slot has an APPROVED appointment; we
            refuse to cascade-delete confirmed bookings. Body lists the
            conflicts so the UI can prompt the professor to cancel them
            first.
    """
    professor = await _get_professor_profile_or_404(db, current_user.id)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(AvailabilitySlot)
        .where(
            AvailabilitySlot.professor_id == professor.id,
            AvailabilitySlot.recurring_group_id == group_id,
            AvailabilitySlot.slot_datetime > now,
        )
        .order_by(AvailabilitySlot.slot_datetime.asc())
    )
    future_slots = list(result.scalars().all())

    if not future_slots:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Rekurentna grupa nije pronađena ili nema budućih slotova "
                "za brisanje."
            ),
        )

    slot_ids = [s.id for s in future_slots]
    appt_result = await db.execute(
        select(Appointment, AvailabilitySlot)
        .join(AvailabilitySlot, Appointment.slot_id == AvailabilitySlot.id)
        .where(
            Appointment.slot_id.in_(slot_ids),
            Appointment.status == AppointmentStatus.APPROVED,
        )
    )
    blocking = appt_result.all()
    if blocking:
        conflicts = [
            RecurringConflict(
                slot_datetime=slot.slot_datetime,
                appointment_id=appt.id,
                reason=(
                    f"Slot {slot.id} ima odobreni termin — otkažite ga pre "
                    f"brisanja serije."
                ),
            )
            for appt, slot in blocking
        ]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Rekurentna grupa ima odobrene buduće termine i ne "
                    "može biti obrisana dok ih ne otkažete."
                ),
                "conflicts": [c.model_dump(mode="json") for c in conflicts],
            },
        )

    for slot in future_slots:
        await db.delete(slot)
    await db.flush()
    return len(future_slots)


# ── Blackouts (KORAK 2 Prompta 2 — override notifikacije) ─────────────────────
async def create_blackout(
    db: AsyncSession,
    current_user: User,
    data: BlackoutCreate,
    redis: aioredis.Redis | None = None,
) -> BlackoutDate:
    """Kreiraj blackout period + override-cancel postojeće APPROVED termine.

    KORAK 2 Prompta 2 / PRD §3.1 flow:

    1. Učitaj sve APPROVED appointment-e koji upadaju u blackout
       prozor (preko slot.slot_datetime — date-only blackout postaje
       [start_date 00:00 UTC, end_date+1 00:00 UTC) interval).
    2. Bulk-update: status → CANCELLED, rejection_reason →
       BLACKOUT_OVERRIDE_REASON_PREFIX (+ blackout opseg). Idempotency
       je automatska — drugi poziv neće naći ništa u APPROVED jer je
       prvi poziv već prebacio sve u CANCELLED.
    3. Za svaki otkazan termin: dispečuj
       ``send_appointment_cancelled_by_override`` task (in-app + email
       + push) i dodaj studenta u prioritetnu Redis waitlist-u
       (``waitlist:priority:{professor_id}``, TTL 14 dana, score
       ``-now`` da bude PRVI kad se sledeći slot kreira).
    4. INSERT blackout reda (uvek, čak i ako 0 termina pogođeno —
       blackout je pravo profesora bez obzira na postojeće termine).

    ``redis`` parametar je optional zbog legacy poziva (test fixtures,
    seed scripts) koji možda neće imati Redis konekciju — u tom slučaju
    radi se samo bulk DB update bez Celery dispatcha i waitlist preliva
    (degraded mode, log-uje warning).
    """
    professor = await _get_professor_profile_or_404(db, current_user.id)

    # Date-only → datetime range (UTC, inclusive end of day).
    window_start = datetime.combine(
        data.start_date, time(0, 0, 0), tzinfo=timezone.utc
    )
    # end_date je INCLUSIVE u UI semantici — uključujemo ceo end_date dan.
    window_end = datetime.combine(
        data.end_date, time(23, 59, 59, 999999), tzinfo=timezone.utc
    )

    override_reason = (
        f"{BLACKOUT_OVERRIDE_REASON_PREFIX}. "
        f"Blackout period: {data.start_date.isoformat()} – "
        f"{data.end_date.isoformat()}."
    )

    affected_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.slot))
        .join(AvailabilitySlot, Appointment.slot_id == AvailabilitySlot.id)
        .where(
            Appointment.professor_id == professor.id,
            Appointment.status == AppointmentStatus.APPROVED,
            AvailabilitySlot.slot_datetime >= window_start,
            AvailabilitySlot.slot_datetime <= window_end,
        )
    )
    affected: list[Appointment] = list(affected_result.scalars().all())

    for appt in affected:
        appt.status = AppointmentStatus.CANCELLED
        appt.rejection_reason = override_reason

    blackout = BlackoutDate(
        professor_id=professor.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
    )
    db.add(blackout)
    await db.flush()
    await db.refresh(blackout)

    # ── Side-effects: notif fan-out + priority waitlist seed ──────────────
    # Komitujemo eksplicitno PRE Celery .delay() i Redis ZADD-a —
    # taskovi učitavaju appointment iz baze i očekuju da je status
    # CANCELLED commit-ovan (inače race: task vidi APPROVED i bunca).
    if affected:
        await db.commit()

        if redis is None:
            _log.warning(
                "availability_service.create_blackout: Redis nije prosleđen "
                "— preskačem priority waitlist seed za blackout=%s "
                "(degraded mode, %d termina otkazano)",
                blackout.id, len(affected),
            )
        else:
            for appt in affected:
                await waitlist_service.add_to_priority_waitlist(
                    redis,
                    student_id=appt.lead_student_id,
                    professor_id=professor.id,
                )

        # Lazy-import da bi se izbegli circular import-i (tasks importuje
        # services za _create_inapp; services bi importovao tasks za .delay).
        from app.tasks.notifications import (
            send_appointment_cancelled_by_override,
        )

        for appt in affected:
            try:
                send_appointment_cancelled_by_override.delay(
                    str(appt.id),
                    data.start_date.isoformat(),
                    data.end_date.isoformat(),
                )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "availability_service.create_blackout: Celery dispatch "
                    "failed appointment=%s err=%s — in-app će biti "
                    "isporučen pri sledećem reminder-u",
                    appt.id, exc,
                )

        _log.info(
            "availability_service.create_blackout: blackout=%s professor=%s "
            "override-cancelled %d APPROVED appointment(e)",
            blackout.id, professor.id, len(affected),
        )

    return blackout


async def list_blackouts(db: AsyncSession, current_user: User) -> list[BlackoutDate]:
    professor = await _get_professor_profile_or_404(db, current_user.id)
    result = await db.execute(
        select(BlackoutDate)
        .where(BlackoutDate.professor_id == professor.id)
        .order_by(BlackoutDate.start_date.asc(), BlackoutDate.end_date.asc())
    )
    return result.scalars().all()


async def delete_blackout(db: AsyncSession, current_user: User, blackout_id: UUID) -> None:
    professor = await _get_professor_profile_or_404(db, current_user.id)

    result = await db.execute(
        select(BlackoutDate).where(
            BlackoutDate.id == blackout_id,
            BlackoutDate.professor_id == professor.id,
        )
    )
    blackout = result.scalar_one_or_none()

    if not blackout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blackout period nije pronađen.",
        )

    await db.delete(blackout)
    await db.flush()
