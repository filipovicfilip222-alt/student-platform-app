import asyncio
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.email import send_generic_notification_email
from app.models.appointment import Appointment
from app.models.availability_slot import AvailabilitySlot
from app.models.enums import DocumentType
from app.models.professor import Professor
from app.models.user import User


async def _get_appointment(appointment_id: UUID) -> Appointment | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.slot),
                selectinload(Appointment.professor).selectinload(Professor.user),
                selectinload(Appointment.lead_student),
            )
            .where(Appointment.id == appointment_id)
        )
        return result.scalar_one_or_none()


@celery_app.task(name="notifications.send_appointment_confirmed")
def send_appointment_confirmed(appointment_id: str) -> bool:
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            return False

        professor_name = appointment.professor.user.full_name
        send_generic_notification_email(
            to_email=appointment.lead_student.email,
            subject="Termin je potvrđen",
            title="Vaš termin je potvrđen",
            body_html=(
                f"<p>Termin kod profesora <strong>{professor_name}</strong> je potvrđen.</p>"
                f"<p>Datum i vreme: <strong>{appointment.slot.slot_datetime.isoformat()}</strong>.</p>"
            ),
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
        return True

    return asyncio.run(_run())


@celery_app.task(name="notifications.send_appointment_reminder")
def send_appointment_reminder(appointment_id: str, hours_before: int) -> bool:
    async def _run() -> bool:
        appointment = await _get_appointment(UUID(appointment_id))
        if appointment is None:
            return False

        professor_name = appointment.professor.user.full_name
        send_generic_notification_email(
            to_email=appointment.lead_student.email,
            subject="Podsetnik za termin",
            title="Podsetnik za zakazan termin",
            body_html=(
                f"<p>Vaš termin kod profesora <strong>{professor_name}</strong> počinje za "
                f"<strong>{hours_before}h</strong>.</p>"
                f"<p>Datum i vreme: <strong>{appointment.slot.slot_datetime.isoformat()}</strong>.</p>"
            ),
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
            send_generic_notification_email(
                to_email=user.email,
                subject="Waitlist ponuda za termin",
                title="Otvorilo se mesto za termin",
                body_html=(
                    f"<p>Otvorilo se mesto kod profesora <strong>{professor_name}</strong>.</p>"
                    f"<p>Termin: <strong>{slot.slot_datetime.isoformat()}</strong>.</p>"
                    f"<p>Ponuda važi do: <strong>{expires_at}</strong>.</p>"
                ),
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
            return True

    return asyncio.run(_run())
