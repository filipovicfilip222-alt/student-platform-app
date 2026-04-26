"""reminder_tasks.py — Celery beat dispatcher za 24h/1h reminder-e (Faza 4.6).

Dva sync wrapper task-a (``dispatch_reminders_24h``, ``dispatch_reminders_1h``)
koja celery-beat trigger-uje periodično (vidi ``celery_app.beat_schedule``).
Oba pozivaju isti async helper :func:`_dispatch_reminders_async` koji:

  1. Skenira ``appointments`` JOIN ``availability_slots`` za sve redove
     gde je ``status=APPROVED`` i ``slot_datetime`` u zadatom prozoru
     **iz sadašnjeg trenutka**.
  2. Za svaki appointment pokušava Redis ``SET NX EX`` na ključu
     ``reminder:{hours}:{appointment_id}`` — ako lock postoji (rezultat
     ``None``), preskoči (već dispečovan u ranijem tick-u). Ako uspe,
     dispečuje ``notifications.send_appointment_reminder.delay(...)``
     koji radi fan-out na lead studenta + profesora + sve CONFIRMED
     participants (videti :mod:`app.tasks.notifications` docstring).

Vremenski prozori (svaki je ŠIRI od beat tick interval-a → garancija
da se svaki termin poklopi sa BAR jednim tick-om):

  - ``dispatch_reminders_24h``: prozor ``[now+23h30m, now+24h30m]``
    (60 min širok), tick svakih 30 min.
  - ``dispatch_reminders_1h``: prozor ``[now+45m, now+1h15m]``
    (30 min širok), tick svakih 15 min.

Idempotency TTL:

  - 24h ključ ``EX=25h`` — pokriva ceo prozor + buffer da Redis sa
    eviction-om ne propusti ključ pre nego što slot startuje.
  - 1h ključ ``EX=2h`` — uži prozor, kraći TTL.

Status guard: i ovde u dispatcheru i u :func:`send_appointment_reminder`
sam check radimo (defense-in-depth — ako profesor otkaže termin između
dispatcher SELECT-a i task pickup-a, samo task će preskočiti slanje).
Redis ključ ostaje set (race protected), ali fan-out se ne dešava.

Cross-loop fix: koristimo :func:`_fresh_db_session` (NullPool) i
:func:`_new_redis` (fresh per-call client) iz :mod:`app.tasks.notifications`
— isti pattern uveden u Fazi 4.5 / KORAK 7 da bi se rešila greška
``RuntimeError: Task got Future attached to a different loop`` u
recurrent Celery beat tick-ovima.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.celery_app import celery_app
from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import AppointmentStatus
from app.tasks.notifications import (
    _fresh_db_session,
    _new_redis,
    send_appointment_reminder,
)

_log = logging.getLogger(__name__)


def _idempotency_key(hours_before: int, appointment_id: str) -> str:
    """Redis ključ za reminder dispatch dedupe.

    Format: ``reminder:{hours}:{appointment_id}``. Hours je integer
    (24 ili 1) bez sufiksa — ne ``24h`` — da bismo izbegli kolizije
    ako se kasnije doda npr. 12h reminder. Appointment_id je UUID
    string verbatim.
    """
    return f"reminder:{hours_before}:{appointment_id}"


async def _dispatch_reminders_async(
    hours_before: int,
    lower_offset: timedelta,
    upper_offset: timedelta,
    redis_ttl_seconds: int,
) -> dict[str, int]:
    """Skeniraj prozor + dispečuj reminder-e.

    Args:
        hours_before: Koji broj sati pre slot-a se odnosi reminder
            (24 ili 1). Prosleđuje se i u idempotency ključ i u
            :func:`send_appointment_reminder` argumente (potonji bira
            ``APPOINTMENT_REMINDER_24H`` vs ``REMINDER_1H`` notif tip).
        lower_offset: Donja granica prozora od trenutka (ekskl.
            inkluzivno: koristimo ``>=``).
        upper_offset: Gornja granica prozora (inkluzivno ``<=``).
        redis_ttl_seconds: TTL idempotency ključa u sekundama.

    Returns:
        Dict ``{"scanned", "dispatched", "skipped"}`` — scanned je
        broj appointment redova u prozoru, dispatched je broj uspešnih
        ``delay()`` poziva (lock acquired), skipped je broj appointmenta
        gde je Redis ključ već postojao (idempotency hit).
    """
    now = datetime.now(timezone.utc)
    lower = now + lower_offset
    upper = now + upper_offset

    async with _fresh_db_session() as db:
        result = await db.execute(
            select(Appointment.id)
            .join(AvailabilitySlot, Appointment.slot_id == AvailabilitySlot.id)
            .where(
                Appointment.status == AppointmentStatus.APPROVED,
                AvailabilitySlot.slot_datetime >= lower,
                AvailabilitySlot.slot_datetime <= upper,
            )
        )
        appointment_ids = [str(row[0]) for row in result.all()]

    scanned = len(appointment_ids)
    dispatched = 0
    skipped = 0

    if scanned == 0:
        _log.info(
            "reminder_tasks.dispatch_reminders_%dh: window=[%s, %s] scanned=0 "
            "(no APPROVED appointments)",
            hours_before, lower.isoformat(), upper.isoformat(),
        )
        return {"scanned": 0, "dispatched": 0, "skipped": 0}

    redis_client = _new_redis()
    try:
        for appointment_id in appointment_ids:
            key = _idempotency_key(hours_before, appointment_id)
            try:
                ok = await redis_client.set(key, "1", nx=True, ex=redis_ttl_seconds)
            except Exception as exc:  # noqa: BLE001
                # Redis ispad — radije propusti dispatch nego dupli send.
                # Worker log nosi appointment_id da admin može ručno re-trigger.
                _log.warning(
                    "reminder_tasks.dispatch_reminders_%dh: redis SET NX failed "
                    "appointment_id=%s err=%s (skipping dispatch)",
                    hours_before, appointment_id, exc,
                )
                continue

            if ok:
                send_appointment_reminder.delay(appointment_id, hours_before)
                dispatched += 1
            else:
                skipped += 1
    finally:
        try:
            await redis_client.close()
        except Exception:
            pass

    _log.info(
        "reminder_tasks.dispatch_reminders_%dh: window=[%s, %s] "
        "scanned=%d dispatched=%d skipped=%d",
        hours_before, lower.isoformat(), upper.isoformat(),
        scanned, dispatched, skipped,
    )
    return {"scanned": scanned, "dispatched": dispatched, "skipped": skipped}


# ── 24h reminder ──────────────────────────────────────────────────────────────


@celery_app.task(name="reminder_tasks.dispatch_24h")
def dispatch_reminders_24h() -> dict[str, int]:
    """Beat tick → 24h reminder fan-out (svakih 30 min).

    Prozor: ``[now+23h30m, now+24h30m]`` (60 min širok). TTL idempotency
    ključa: 25h (pokriva ceo prozor + 30 min buffer).

    Edge case verifikovan: termin sa ``slot_datetime = now + 24h05m``
    NEĆE ući u prozor [23h30m, 24h30m] u 24h05m sad — UČI će u sledećem
    tick-u 30 min kasnije kada je slot na ``now+23h35m`` što je u
    prozoru. Idempotency ključ TTL 25h sprečava da treći tick (60 min
    kasnije) ponovo dispečuje.
    """
    _log.info("reminder_tasks.dispatch_reminders_24h: started")
    return asyncio.run(
        _dispatch_reminders_async(
            hours_before=24,
            lower_offset=timedelta(hours=23, minutes=30),
            upper_offset=timedelta(hours=24, minutes=30),
            redis_ttl_seconds=25 * 3600,
        )
    )


# ── 1h reminder ──────────────────────────────────────────────────────────────


@celery_app.task(name="reminder_tasks.dispatch_1h")
def dispatch_reminders_1h() -> dict[str, int]:
    """Beat tick → 1h reminder fan-out (svakih 15 min).

    Prozor: ``[now+45m, now+1h15m]`` (30 min širok). TTL idempotency
    ključa: 2h (slot već prošao posle 1h, key visi još 1h kao buffer).
    """
    _log.info("reminder_tasks.dispatch_reminders_1h: started")
    return asyncio.run(
        _dispatch_reminders_async(
            hours_before=1,
            lower_offset=timedelta(minutes=45),
            upper_offset=timedelta(hours=1, minutes=15),
            redis_ttl_seconds=2 * 3600,
        )
    )
