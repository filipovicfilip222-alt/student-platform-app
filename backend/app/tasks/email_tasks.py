"""
email_tasks.py — Celery tasks for outbound email.

Uses Python's stdlib smtplib so there are no async issues inside a
synchronous Celery worker. TLS is negotiated via STARTTLS.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="email_tasks.send_email",
)
def send_email_task(
    self,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict:
    """
    Send a single email.

    Retried up to 3 times (60 s apart) on transient SMTP errors.
    Returns a status dict that is stored in the Celery result backend.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, [to_email], msg.as_string())

        logger.info("Email sent to %s | subject=%r", to_email, subject)
        return {"status": "sent", "to": to_email}

    except smtplib.SMTPException as exc:
        logger.warning(
            "SMTP error sending to %s (attempt %d/%d): %s",
            to_email,
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc)

    except Exception as exc:
        logger.error("Unexpected error sending email to %s: %s", to_email, exc)
        raise
