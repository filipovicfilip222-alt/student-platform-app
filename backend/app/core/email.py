"""
email.py — High-level email dispatch helpers.

All functions here enqueue a Celery task (never send synchronously from a
request handler). Import and call these from services, never from endpoints.
"""

from app.core.config import settings


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    """Queue a password-reset email."""
    from app.tasks.email_tasks import send_email_task  # late import avoids circular deps

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    subject = "Resetovanje lozinke — Konsultacije FON & ETF"
    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Resetovanje lozinke</h2>
      <p>Primili smo zahtev za resetovanje lozinke za Vaš nalog (<strong>{to_email}</strong>).</p>
      <p>Kliknite na link ispod da postavite novu lozinku. Link je važeći <strong>1 sat</strong>.</p>
      <p>
        <a href="{reset_url}"
           style="background:#2563eb;color:#fff;padding:12px 24px;
                  text-decoration:none;border-radius:6px;display:inline-block;">
          Resetuj lozinku
        </a>
      </p>
      <p style="color:#6b7280;font-size:0.875rem;">
        Ako niste Vi podneli ovaj zahtev, ignorišite ovaj email.
      </p>
      <hr/>
      <p style="color:#9ca3af;font-size:0.75rem;">
        {settings.EMAILS_FROM_NAME} · Ovaj email je automatski generisan.
      </p>
    </body></html>
    """

    send_email_task.delay(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
    )


def send_welcome_email(to_email: str, first_name: str) -> None:
    """Queue a welcome email after registration."""
    from app.tasks.email_tasks import send_email_task

    subject = f"Dobrodošli na {settings.EMAILS_FROM_NAME}!"
    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>Dobrodošli, {first_name}!</h2>
      <p>Vaš nalog na platformi <strong>{settings.EMAILS_FROM_NAME}</strong> je uspešno kreiran.</p>
      <p>Možete se prijaviti na:
        <a href="{settings.FRONTEND_URL}/login">{settings.FRONTEND_URL}</a>
      </p>
      <hr/>
      <p style="color:#9ca3af;font-size:0.75rem;">
        {settings.EMAILS_FROM_NAME} · Ovaj email je automatski generisan.
      </p>
    </body></html>
    """

    send_email_task.delay(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
    )


def send_generic_notification_email(
    to_email: str,
    subject: str,
    title: str,
    body_html: str,
) -> None:
    """Queue a generic notification email with a consistent layout."""
    from app.tasks.email_tasks import send_email_task

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>{title}</h2>
      {body_html}
      <hr/>
      <p style="color:#9ca3af;font-size:0.75rem;">
        {settings.EMAILS_FROM_NAME} · Ovaj email je automatski generisan.
      </p>
    </body></html>
    """

    send_email_task.delay(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
    )
