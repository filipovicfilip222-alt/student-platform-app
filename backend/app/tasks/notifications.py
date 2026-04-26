"""Celery taskovi: email + in-app notif (Faza 4.2 proširenje).

Svaki task pored slanja email-a sad i kreira in-app notifikaciju kroz
``notification_service.create()`` — taj poziv vrši INSERT u DB,
INCR Redis countera i publish-uje ``notification.created`` /
``notification.unread_count`` envelope na ``notif:pub:{user_id}`` kanal.
Tako se otvoreni WS-ovi tog korisnika ažuriraju u realnom vremenu, a
korisnici koji nisu trenutno povezani vide notifikaciju pri sledećem
REST GET-u.

Pattern:
    - Svaki task ima async ``_run()`` closure i zove ``asyncio.run(_run())``
      iz sync Celery wrapper-a (postojeći stil).
    - In-app create se izvršava i ako email padne (i obrnuto) — failure
      jednog kanala ne sme da blokira drugi (notif je krit, email je nice
      to have).
    - Redis konekcija se otvara per-task (fresh ``aioredis.from_url``) i
      zatvara u finally, identično ``waitlist_tasks.py`` patternu — Celery
      worker proces živi duže od jednog event loop-a, pa nema deljenog
      pool-a između ``asyncio.run()`` invokacija (cross-loop greška).

Mapping task → NotificationType (8 taskova, 8 vrednosti enum-a):

    send_appointment_confirmed         → APPOINTMENT_CONFIRMED
    send_appointment_rejected          → APPOINTMENT_REJECTED
    send_appointment_reminder(24)      → APPOINTMENT_REMINDER_24H
    send_appointment_reminder(<24)     → APPOINTMENT_REMINDER_1H
    send_strike_added                  → STRIKE_ADDED
    send_block_activated               → BLOCK_ACTIVATED
    send_block_lifted                  → BLOCK_LIFTED      (Faza 4.5)
    send_waitlist_offer                → WAITLIST_OFFER
    send_document_request_approved     → DOCUMENT_REQUEST_APPROVED
    send_document_request_rejected     → DOCUMENT_REQUEST_REJECTED

Ostale ``NotificationType`` vrednosti (BROADCAST, NEW_*,
APPOINTMENT_CANCELLED/DELEGATED, DOCUMENT_REQUEST_COMPLETED) kreiraju se
direktno iz REST handler-a u trenutku akcije — nemaju email pandan, pa
ne pripadaju ovom modulu. Broadcast fan-out (Faza 4.5) ima svoj zaseban
modul ``app.tasks.broadcast_tasks`` jer per-user IN_APP+EMAIL ide u
istom Celery task-u (vidi taj fajl za argumentaciju).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.email import send_generic_notification_email
from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import AppointmentStatus, DocumentType, NotificationType
from app.models.professor import Professor
from app.models.user import User
from app.services import notification_service

_log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _new_redis() -> aioredis.Redis:
    """Fresh Redis client za jedan ``asyncio.run()`` poziv.

    Ne koristimo singleton iz ``dependencies.get_redis`` jer je on vezan
    za FastAPI event loop; Celery svaki task pokreće u svom event loop-u
    (kroz ``asyncio.run``), a aioredis konekcije ne mogu da pređu loop
    granicu (asyncio runtime baca ``RuntimeError: got Future attached
    to a different loop``)."""
    return aioredis.from_url(
        settings.REDIS_URL, encoding="utf-8", decode_responses=True
    )


@asynccontextmanager
async def _fresh_db_session() -> AsyncIterator[AsyncSession]:
    """Per-task fresh ``AsyncEngine`` + ``AsyncSession`` sa ``NullPool``.

    Zašto NullPool umesto deljenog ``AsyncSessionLocal`` engine-a:
    Celery worker proces pokreće ``asyncio.run(_run())`` koji svaki put
    kreira novi event loop. ``create_async_engine`` (default ``QueuePool``
    sa ``pool_pre_ping=True``) pool-uje konekcije po procesu — ali
    asyncpg konekcije su VEZANE za event loop u kome su otvorene, pa
    sledeći ``asyncio.run`` pokušava da ih reuse-uje i dobija
    ``RuntimeError: Task got Future attached to a different loop``.

    NullPool ne kešira konekcije — svaki ``checkout`` kreira fresh
    konekciju u **trenutnom** event loop-u, a ``release`` je odmah
    zatvara. Plus ``await engine.dispose()`` u finally-ju cisti sve
    rezidualne resurse pre nego što ``asyncio.run()`` ugasi loop.

    Worker-prefetch-multiplier=1 (vidi ``celery_app.py``) garantuje da
    nema paralelnih taskova u istom procesu, pa NullPool overhead je
    zanemarljiv (1 connection per task, zatvorena na izlasku).
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    SessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    try:
        async with SessionLocal() as session:
            yield session
    finally:
        await engine.dispose()


async def _create_inapp(
    *,
    user_id: UUID,
    type: NotificationType,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Bezbedni in-app create iz Celery taska.

    Otvara fresh DB session + Redis client, zove
    ``notification_service.create()``, gasi konekcije. Bilo koja greška
    je log-ovana i swallow-ovana — email kanal mora da nastavi i pri
    privremenom Redis ispadu, jer notif retry inače vodi do duplog email-a.

    DB sesija ide kroz :func:`_fresh_db_session` da bismo izbegli
    cross-loop grešku iz deljenog ``AsyncSessionLocal`` pool-a (vidi
    docstring helpera za detalje).
    """
    redis_client = _new_redis()
    try:
        async with _fresh_db_session() as db:
            await notification_service.create(
                db,
                redis_client,
                user_id=user_id,
                type=type,
                title=title,
                body=body,
                data=data,
                # Celery context — ``asyncio.run`` cancel-uje background
                # task-ove na cleanup-u. Sinhronizovan await da bi push
                # stigao do FCM/Mozilla pre nego što loop nestane (KORAK 1
                # Prompta 2 — push fan-out hook).
                dispatch_push_in_background=False,
            )
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "tasks.notifications._create_inapp: create failed user=%s type=%s err=%s",
            user_id, type.value, exc,
        )
    finally:
        try:
            await redis_client.close()
        except Exception:
            pass


async def _get_appointment(appointment_id: UUID) -> Appointment | None:
    """Učitaj appointment sa svim relacijama potrebnim za fan-out.

    Eager-load-uje:
      - ``slot`` — za ``slot_datetime`` u email/notif body-ju
      - ``professor.user`` — primalac reminder-a + ime u tekstu
      - ``lead_student`` — primalac reminder-a (i izvor email-a kad
        student otkaže)
      - ``participants.student`` — non-lead CONFIRMED useri dobijaju
        reminder za grupne konsultacije (Faza 4.6); ako booking flow
        još uvek pravi samo lead participant-a, lista je prazna i
        loop ne radi ništa.
    """
    from app.models.appointment import AppointmentParticipant

    async with _fresh_db_session() as db:
        result = await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.slot),
                selectinload(Appointment.professor).selectinload(Professor.user),
                selectinload(Appointment.lead_student),
                selectinload(Appointment.participants).selectinload(
                    AppointmentParticipant.student
                ),
            )
            .where(Appointment.id == appointment_id)
        )
        return result.scalar_one_or_none()


def _collect_recipients(
    appointment: Appointment,
    *,
    exclude_user_ids: set[UUID] | None = None,
) -> list[tuple[UUID, str, str]]:
    """Vrati listu ``(user_id, email, display_name)`` primaoca fan-out-a.

    Redosled:
      1. Lead student
      2. Profesor (preko ``professor.user``)
      3. Non-lead CONFIRMED participants (preko ``participants.student``)

    Deduplikacija po ``user_id`` (ako lead figuriše i kao participant
    sa statusom CONFIRMED — što je default flow iz
    ``booking_service.create_appointment`` linije 191–198 — neće biti
    duplo dispečovan). ``exclude_user_ids`` koristi
    ``send_appointment_cancelled`` da preskoči onog ko je inicirao
    otkazivanje (student samog sebe ne notifikuje).
    """
    from app.models.enums import ParticipantStatus

    excluded: set[UUID] = exclude_user_ids or set()
    seen: set[UUID] = set()
    recipients: list[tuple[UUID, str, str]] = []

    def _add(user_id: UUID, email: str, name: str) -> None:
        if user_id in excluded or user_id in seen:
            return
        seen.add(user_id)
        recipients.append((user_id, email, name))

    lead = appointment.lead_student
    if lead is not None:
        _add(lead.id, lead.email, lead.full_name)

    prof_user = appointment.professor.user if appointment.professor else None
    if prof_user is not None:
        _add(prof_user.id, prof_user.email, prof_user.full_name)

    for part in appointment.participants or []:
        if part.status != ParticipantStatus.CONFIRMED:
            continue
        student = part.student
        if student is None:
            continue
        _add(student.id, student.email, student.full_name)

    return recipients


# ── Tasks ────────────────────────────────────────────────────────────────────


@celery_app.task(name="notifications.send_appointment_confirmed")
def send_appointment_confirmed(appointment_id: str) -> bool:
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            return False

        professor_name = appointment.professor.user.full_name
        slot_iso = appointment.slot.slot_datetime.isoformat()

        send_generic_notification_email(
            to_email=appointment.lead_student.email,
            subject="Termin je potvrđen",
            title="Vaš termin je potvrđen",
            body_html=(
                f"<p>Termin kod profesora <strong>{professor_name}</strong> je potvrđen.</p>"
                f"<p>Datum i vreme: <strong>{slot_iso}</strong>.</p>"
            ),
        )

        await _create_inapp(
            user_id=appointment.lead_student.id,
            type=NotificationType.APPOINTMENT_CONFIRMED,
            title="Termin je potvrđen",
            body=f"Profesor {professor_name} je potvrdio termin {slot_iso}.",
            data={
                "appointment_id": str(appointment.id),
                "slot_datetime": slot_iso,
                "professor_name": professor_name,
            },
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_appointment_rejected")
def send_appointment_rejected(appointment_id: str, reason: str) -> bool:
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            return False

        professor_name = appointment.professor.user.full_name
        final_reason = reason or appointment.rejection_reason or "Bez dodatnog obrazloženja."

        send_generic_notification_email(
            to_email=appointment.lead_student.email,
            subject="Termin je odbijen",
            title="Vaš termin je odbijen",
            body_html=(
                f"<p>Termin kod profesora <strong>{professor_name}</strong> je odbijen.</p>"
                f"<p>Razlog: <strong>{final_reason}</strong></p>"
            ),
        )

        await _create_inapp(
            user_id=appointment.lead_student.id,
            type=NotificationType.APPOINTMENT_REJECTED,
            title="Termin je odbijen",
            body=f"Profesor {professor_name} je odbio termin. Razlog: {final_reason}",
            data={
                "appointment_id": str(appointment.id),
                "reason": final_reason,
                "professor_name": professor_name,
            },
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_appointment_reminder")
def send_appointment_reminder(appointment_id: str, hours_before: int) -> bool:
    """Reminder fan-out (Faza 4.6).

    Šalje email + in-app notifikaciju **svim učesnicima termina**:
    lead student, profesor (preko ``professor.user``), i svi
    ``participants`` sa ``status=CONFIRMED`` (grupne konsultacije).
    Lead se dedupliše ako figuriše i kao participant (videti
    :func:`_collect_recipients`).

    Status guard: ako između beat scan-a i task pickup-a profesor
    otkaže termin (``status != APPROVED``), task se odmah završava
    bez slanja. Idempotency Redis ključ iz ``reminder_tasks`` ostaje
    set-ovan da spreči ponovno dispečovanje, ali ovaj guard je
    dodatna defense-in-depth provera.

    Per-recipient try/except: SMTP ili Redis ispad za jednog primaoca
    ne sme da pokvari fan-out ostalim primaocima (isti pattern kao
    ``broadcast_tasks.fanout_broadcast`` iz Faze 4.5).

    Args:
        appointment_id: UUID stringa appointment reda.
        hours_before: 24 za 24h podsetnik, 1 za 1h podsetnik. Vrednosti
            ``>=24`` mapiraju se na ``APPOINTMENT_REMINDER_24H``, ispod
            na ``APPOINTMENT_REMINDER_1H``.

    Returns:
        ``True`` ako je BAR jedan primalac uspešno notifikovan; ``False``
        ako appointment ne postoji, status nije APPROVED, ili je lista
        primaoca prazna.
    """
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            _log.warning(
                "tasks.notifications.send_appointment_reminder: appointment_id=%s not found",
                appointment_id,
            )
            return False

        if appointment.status != AppointmentStatus.APPROVED:
            _log.info(
                "tasks.notifications.send_appointment_reminder: skip appointment_id=%s "
                "status=%s (only APPROVED reminders fire)",
                appointment_id, appointment.status.value,
            )
            return False

        professor_name = (
            appointment.professor.user.full_name if appointment.professor else "—"
        )
        slot_iso = appointment.slot.slot_datetime.isoformat()
        recipients = _collect_recipients(appointment)
        if not recipients:
            _log.warning(
                "tasks.notifications.send_appointment_reminder: appointment_id=%s "
                "no recipients (no lead, no professor, no participants)",
                appointment_id,
            )
            return False

        # 24h ili više → REMINDER_24H, ispod → REMINDER_1H. Granica je
        # postavljena tako da je standardni 24h reminder uvek 24h tip,
        # 1h reminder uvek 1h tip. Edge npr. 6h ide u 1H bucket što je OK
        # (frontend toast/icon copy generički — broj sati se prikazuje iz
        # ``data.hours_before``).
        notif_type = (
            NotificationType.APPOINTMENT_REMINDER_24H
            if hours_before >= 24
            else NotificationType.APPOINTMENT_REMINDER_1H
        )
        notif_data = {
            "appointment_id": str(appointment.id),
            "slot_datetime": slot_iso,
            "hours_before": int(hours_before),
            "professor_name": professor_name,
        }

        sent = 0
        for recipient_id, recipient_email, recipient_name in recipients:
            try:
                send_generic_notification_email(
                    to_email=recipient_email,
                    subject="Podsetnik za termin",
                    title="Podsetnik za zakazan termin",
                    body_html=(
                        f"<p>Poštovani/a <strong>{recipient_name}</strong>,</p>"
                        f"<p>Termin kod profesora <strong>{professor_name}</strong> "
                        f"počinje za <strong>{hours_before}h</strong>.</p>"
                        f"<p>Datum i vreme: <strong>{slot_iso}</strong>.</p>"
                    ),
                )
                await _create_inapp(
                    user_id=recipient_id,
                    type=notif_type,
                    title="Podsetnik za termin",
                    body=(
                        f"Termin kod profesora {professor_name} počinje za "
                        f"{hours_before}h ({slot_iso})."
                    ),
                    data=notif_data,
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "tasks.notifications.send_appointment_reminder: dispatch failed "
                    "appointment_id=%s recipient_id=%s hours_before=%s err=%s",
                    appointment_id, recipient_id, hours_before, exc,
                    extra={
                        "appointment_id": appointment_id,
                        "recipient_id": str(recipient_id),
                        "hours_before": int(hours_before),
                        "error": str(exc),
                    },
                )

        _log.info(
            "tasks.notifications.send_appointment_reminder: appointment_id=%s "
            "hours_before=%s targeted=%d sent=%d",
            appointment_id, hours_before, len(recipients), sent,
        )
        return sent > 0

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_appointment_cancelled")
def send_appointment_cancelled(
    appointment_id: str,
    cancelled_by_role: str,
    reason: str | None = None,
) -> bool:
    """Otkazani termin notifikacija (Faza 4.6 / PRD §5.2).

    Pre Faze 4.6 ovaj task NIJE postojao — ``booking_service.cancel_appointment``
    nije dispečovao nikakvu notifikaciju (latentni bug, profesor nikad
    nije saznavao da student otkazao), dok je ``professor_portal_service.cancel_request``
    reuse-ovao ``send_appointment_rejected`` (semantički nije odgovaralo
    PRD-u). Ovaj task popravlja oba flow-a.

    Args:
        appointment_id: UUID stringa.
        cancelled_by_role: ``"STUDENT"`` ili ``"PROFESOR"`` —
            string (ne enum) jer je task internal API. Određuje koga
            iz lead/professor para isključiti iz primaoca (onaj ko je
            otkazao ne dobija notif samog sebe).
        reason: Razlog otkazivanja (kod profesor flow-a se učitava
            iz ``Appointment.rejection_reason`` ako ovde nije prosleđen).

    Returns:
        ``True`` ako je BAR jedan primalac uspešno notifikovan.
    """
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            _log.warning(
                "tasks.notifications.send_appointment_cancelled: appointment_id=%s not found",
                appointment_id,
            )
            return False

        professor_name = (
            appointment.professor.user.full_name if appointment.professor else "—"
        )
        slot_iso = appointment.slot.slot_datetime.isoformat()
        final_reason = (
            (reason or appointment.rejection_reason or "").strip()
            or "Bez dodatnog obrazloženja."
        )

        # Isključujemo onoga ko je otkazao da ne dobije notif samog
        # sebe. Profesor uloga obuhvata i ASISTENT-a delegiranog na
        # termin — oba dispečuju kroz ``professor_portal_service.cancel_request``,
        # pa ``professor.user`` jeste lice koje je otkazalo.
        excluded: set[UUID] = set()
        role = (cancelled_by_role or "").upper()
        if role == "STUDENT" and appointment.lead_student is not None:
            excluded.add(appointment.lead_student.id)
        elif role == "PROFESOR" and appointment.professor and appointment.professor.user:
            excluded.add(appointment.professor.user.id)

        recipients = _collect_recipients(appointment, exclude_user_ids=excluded)
        if not recipients:
            _log.info(
                "tasks.notifications.send_appointment_cancelled: appointment_id=%s "
                "no recipients to notify (excluded=%s)",
                appointment_id, [str(uid) for uid in excluded],
            )
            return False

        cancelled_by_label = (
            "student" if role == "STUDENT"
            else ("profesor" if role == "PROFESOR" else "korisnik")
        )
        notif_data = {
            "appointment_id": str(appointment.id),
            "slot_datetime": slot_iso,
            "professor_name": professor_name,
            "cancelled_by_role": role or "UNKNOWN",
            "reason": final_reason,
        }

        sent = 0
        for recipient_id, recipient_email, recipient_name in recipients:
            try:
                send_generic_notification_email(
                    to_email=recipient_email,
                    subject="Termin je otkazan",
                    title="Vaš termin je otkazan",
                    body_html=(
                        f"<p>Poštovani/a <strong>{recipient_name}</strong>,</p>"
                        f"<p>Termin zakazan za <strong>{slot_iso}</strong> "
                        f"(profesor <strong>{professor_name}</strong>) je otkazan "
                        f"({cancelled_by_label}).</p>"
                        f"<p>Razlog: <strong>{final_reason}</strong></p>"
                    ),
                )
                await _create_inapp(
                    user_id=recipient_id,
                    type=NotificationType.APPOINTMENT_CANCELLED,
                    title="Termin je otkazan",
                    body=(
                        f"Termin {slot_iso} kod profesora {professor_name} "
                        f"je otkazan ({cancelled_by_label}). Razlog: {final_reason}"
                    ),
                    data=notif_data,
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "tasks.notifications.send_appointment_cancelled: dispatch failed "
                    "appointment_id=%s recipient_id=%s cancelled_by=%s err=%s",
                    appointment_id, recipient_id, role, exc,
                    extra={
                        "appointment_id": appointment_id,
                        "recipient_id": str(recipient_id),
                        "cancelled_by_role": role,
                        "error": str(exc),
                    },
                )

        _log.info(
            "tasks.notifications.send_appointment_cancelled: appointment_id=%s "
            "cancelled_by=%s targeted=%d sent=%d",
            appointment_id, role, len(recipients), sent,
        )
        return sent > 0

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_appointment_cancelled_by_override")
def send_appointment_cancelled_by_override(
    appointment_id: str,
    blackout_start: str,
    blackout_end: str,
) -> bool:
    """Override-cancel notif: profesor je blackout-om pregazio APPROVED termin.

    KORAK 2 Prompta 2 / PRD §3.1. Razlikuje se od regularnog
    ``send_appointment_cancelled`` po **email body-ju i in-app notif
    tekstu** — student dobija eksplicitnu poruku da je termin profesor
    rezervisao za drugu obavezu i da je AUTOMATSKI stavljen na
    prioritetnu listu za sledećih 14 dana (waitlist će ga ponuditi
    PRVO kad profesor sledeći put postavi novi slot).

    Argumenti:
        appointment_id: UUID stringa otkazanog termina (već u CANCELLED
            statusu — ovaj task je side-effect, ne menja status).
        blackout_start, blackout_end: ISO date stringovi blackout perioda
            (za informativni body). Duplicirana je rejection_reason
            kolona, ali frontend body-ju treba čisto formatiranje.

    Primalac: lead student (profesor je inicirao otkazivanje, on/ona ne
    dobija notif). Push fan-out je preko ``_create_inapp`` (kao i kod
    regularnog cancel taska — flag ``dispatch_push_in_background=False``).
    """
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            _log.warning(
                "tasks.notifications.send_appointment_cancelled_by_override: "
                "appointment_id=%s not found",
                appointment_id,
            )
            return False

        if appointment.lead_student is None:
            _log.warning(
                "tasks.notifications.send_appointment_cancelled_by_override: "
                "appointment_id=%s ima lead_student=None",
                appointment_id,
            )
            return False

        professor_name = (
            appointment.professor.user.full_name if appointment.professor else "—"
        )
        slot_iso = appointment.slot.slot_datetime.isoformat()
        student = appointment.lead_student

        notif_data = {
            "appointment_id": str(appointment.id),
            "slot_datetime": slot_iso,
            "professor_name": professor_name,
            "blackout_start": blackout_start,
            "blackout_end": blackout_end,
            "override": True,
            "priority_waitlist_days": 14,
        }

        body_text = (
            f"Vaš termin {slot_iso} kod profesora {professor_name} je otkazan jer je "
            "profesor rezervisao to vreme za drugu obavezu. Automatski ste "
            "dodati na prioritetnu listu — kad profesor sledeći put doda novi "
            "slot u narednih 14 dana, biće Vam ponuđen PRVO."
        )

        try:
            send_generic_notification_email(
                to_email=student.email,
                subject="Termin je otkazan — automatski ste na prioritetnoj listi",
                title="Profesor je rezervisao Vaš termin za drugu obavezu",
                body_html=(
                    f"<p>Poštovani/a <strong>{student.full_name}</strong>,</p>"
                    f"<p>Termin zakazan za <strong>{slot_iso}</strong> "
                    f"(profesor <strong>{professor_name}</strong>) je "
                    f"<strong>otkazan</strong> jer je profesor rezervisao to "
                    f"vreme za drugu obavezu (blackout period "
                    f"{blackout_start} – {blackout_end}).</p>"
                    "<p><strong>Automatski ste stavljeni na prioritetnu "
                    "listu za sledećih 14 dana.</strong> Čim profesor doda "
                    "novi slot u tom periodu, biće Vam ponuđen <em>pre</em> "
                    "ostalih studenata na waitlist-u.</p>"
                    "<p>Hvala na razumevanju.</p>"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "tasks.notifications.send_appointment_cancelled_by_override: "
                "email failed appointment_id=%s student=%s err=%s",
                appointment_id, student.id, exc,
            )

        try:
            await _create_inapp(
                user_id=student.id,
                type=NotificationType.APPOINTMENT_CANCELLED,
                title="Termin je otkazan (override)",
                body=body_text,
                data=notif_data,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "tasks.notifications.send_appointment_cancelled_by_override: "
                "in-app failed appointment_id=%s student=%s err=%s",
                appointment_id, student.id, exc,
            )
            return False

        _log.info(
            "tasks.notifications.send_appointment_cancelled_by_override: "
            "appointment_id=%s student=%s blackout=%s..%s",
            appointment_id, student.id, blackout_start, blackout_end,
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_strike_added")
def send_strike_added(student_id: str, points: int, total: int) -> bool:
    async def _run() -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == UUID(student_id)))
            user = result.scalar_one_or_none()
            if user is None:
                return False

        send_generic_notification_email(
            to_email=user.email,
            subject="Dodat je strike",
            title="Obaveštenje o strike poenima",
            body_html=(
                f"<p>Dodeljeno Vam je <strong>{points}</strong> poena.</p>"
                f"<p>Ukupan broj strike poena: <strong>{total}</strong>.</p>"
            ),
        )

        await _create_inapp(
            user_id=user.id,
            type=NotificationType.STRIKE_ADDED,
            title="Dodat je strike",
            body=f"Dobili ste {points} poena. Ukupno: {total}.",
            data={"points": int(points), "total": int(total)},
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_block_activated")
def send_block_activated(student_id: str, blocked_until: str) -> bool:
    async def _run() -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == UUID(student_id)))
            user = result.scalar_one_or_none()
            if user is None:
                return False

        send_generic_notification_email(
            to_email=user.email,
            subject="Aktivirana blokada naloga",
            title="Vaš nalog je privremeno blokiran",
            body_html=(
                "<p>Zbog broja prekršaja aktivirana je privremena blokada zakazivanja.</p>"
                f"<p>Blokada traje do: <strong>{blocked_until}</strong>.</p>"
            ),
        )

        await _create_inapp(
            user_id=user.id,
            type=NotificationType.BLOCK_ACTIVATED,
            title="Nalog je blokiran",
            body=f"Zbog prekršaja, zakazivanje je blokirano do {blocked_until}.",
            data={"blocked_until": blocked_until},
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_block_lifted")
def send_block_lifted(student_id: str, removal_reason: str) -> bool:
    """Admin override blokade (Faza 4.5).

    Trigeruje se iz ``POST /admin/strikes/{id}/unblock`` posle uspešnog
    ``strike_service.unblock_student`` poziva. Šalje email + in-app
    BLOCK_LIFTED notifikaciju studentu sa razlogom override-a u body-ju.

    ``removal_reason`` je obavezan (Pydantic ``UnblockRequest`` ga
    validira na min_length=10 — frontend zod schema je identičan).
    """
    async def _run() -> bool:
        async with _fresh_db_session() as db:
            result = await db.execute(select(User).where(User.id == UUID(student_id)))
            user = result.scalar_one_or_none()
            if user is None:
                return False

        reason = removal_reason.strip() if removal_reason else "Bez dodatnog obrazloženja."

        send_generic_notification_email(
            to_email=user.email,
            subject="Blokada naloga je skinuta",
            title="Vaš nalog je odblokiran",
            body_html=(
                "<p>Administrator je skinuo privremenu blokadu sa Vašeg naloga.</p>"
                f"<p>Razlog: <strong>{reason}</strong></p>"
                "<p>Možete ponovo da zakazujete termine.</p>"
            ),
        )

        await _create_inapp(
            user_id=user.id,
            type=NotificationType.BLOCK_LIFTED,
            title="Blokada naloga je skinuta",
            body=f"Administrator je odblokirao Vaš nalog. Razlog: {reason}",
            data={"removal_reason": reason},
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_waitlist_offer")
def send_waitlist_offer(student_id: str, slot_id: str, expires_at: str) -> bool:
    async def _run() -> bool:
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(select(User).where(User.id == UUID(student_id)))
            user = user_result.scalar_one_or_none()
            if user is None:
                return False

            slot_result = await db.execute(
                select(AvailabilitySlot)
                .options(selectinload(AvailabilitySlot.professor).selectinload(Professor.user))
                .where(AvailabilitySlot.id == UUID(slot_id))
            )
            slot = slot_result.scalar_one_or_none()
            if slot is None:
                return False

            professor_name = slot.professor.user.full_name
            slot_iso = slot.slot_datetime.isoformat()

        send_generic_notification_email(
            to_email=user.email,
            subject="Waitlist ponuda za termin",
            title="Otvorilo se mesto za termin",
            body_html=(
                f"<p>Otvorilo se mesto kod profesora <strong>{professor_name}</strong>.</p>"
                f"<p>Termin: <strong>{slot_iso}</strong>.</p>"
                f"<p>Ponuda važi do: <strong>{expires_at}</strong>.</p>"
            ),
        )

        await _create_inapp(
            user_id=user.id,
            type=NotificationType.WAITLIST_OFFER,
            title="Waitlist ponuda",
            body=f"Otvorilo se mesto kod profesora {professor_name} ({slot_iso}). Ponuda važi do {expires_at}.",
            data={
                "slot_id": str(slot.id),
                "slot_datetime": slot_iso,
                "expires_at": expires_at,
                "professor_name": professor_name,
            },
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_document_request_approved")
def send_document_request_approved(
    student_id: str,
    document_type: str,
    pickup_date: str,
    admin_note: str,
) -> bool:
    async def _run() -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == UUID(student_id)))
            user = result.scalar_one_or_none()
            if user is None:
                return False

        doc_label = DocumentType(document_type).value if document_type else "DOKUMENT"
        note = admin_note.strip() if admin_note and admin_note.strip() else "Studentska služba"

        send_generic_notification_email(
            to_email=user.email,
            subject="Zahtev za dokument je odobren",
            title="Vaš zahtev je odobren",
            body_html=(
                f"<p>Vaš zahtev za dokument tipa <strong>{doc_label}</strong> je odobren.</p>"
                f"<p>Dokument možete preuzeti <strong>{pickup_date}</strong>.</p>"
                f"<p>Napomena: <strong>{note}</strong>.</p>"
            ),
        )

        await _create_inapp(
            user_id=user.id,
            type=NotificationType.DOCUMENT_REQUEST_APPROVED,
            title="Zahtev odobren",
            body=f"Dokument {doc_label} se preuzima {pickup_date}. Napomena: {note}",
            data={
                "document_type": doc_label,
                "pickup_date": pickup_date,
                "admin_note": note,
            },
        )
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_document_request_rejected")
def send_document_request_rejected(
    student_id: str,
    document_type: str,
    admin_note: str,
) -> bool:
    async def _run() -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == UUID(student_id)))
            user = result.scalar_one_or_none()
            if user is None:
                return False

        doc_label = DocumentType(document_type).value if document_type else "DOKUMENT"
        note = admin_note.strip() if admin_note and admin_note.strip() else "Bez dodatnog obrazloženja."

        send_generic_notification_email(
            to_email=user.email,
            subject="Zahtev za dokument je odbijen",
            title="Vaš zahtev je odbijen",
            body_html=(
                f"<p>Vaš zahtev za dokument tipa <strong>{doc_label}</strong> je odbijen.</p>"
                f"<p>Razlog: <strong>{note}</strong>.</p>"
            ),
        )

        await _create_inapp(
            user_id=user.id,
            type=NotificationType.DOCUMENT_REQUEST_REJECTED,
            title="Zahtev odbijen",
            body=f"Dokument {doc_label} je odbijen. Razlog: {note}",
            data={
                "document_type": doc_label,
                "admin_note": note,
            },
        )
        return True

    return asyncio.run(_run())
