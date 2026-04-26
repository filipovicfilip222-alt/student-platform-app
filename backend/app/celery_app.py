from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "studentska_platforma",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.broadcast_tasks",
        "app.tasks.email_tasks",
        "app.tasks.notifications",
        "app.tasks.reminder_tasks",
        "app.tasks.strike_tasks",
        "app.tasks.waitlist_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Belgrade",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "detect-no-show-every-30-minutes": {
            "task": "strike_tasks.detect_no_show",
            "schedule": crontab(minute="*/30"),
        },
        "process-waitlist-offers-every-5-minutes": {
            "task": "waitlist_tasks.process_waitlist_offers",
            "schedule": crontab(minute="*/5"),
        },
        # Faza 4.6 — reminder dispatcher-i. Tick interval JE UŽI od scan
        # window-a (30min < 60min za 24h, 15min < 30min za 1h) → svaki
        # APPROVED termin će bar jedanput biti pokriven barem jednim
        # tick-om. Idempotency Redis ključ ``reminder:{hours}:{id}``
        # sprečava duplikate kad se prozori preklope.
        "dispatch-reminders-24h-every-30-minutes": {
            "task": "reminder_tasks.dispatch_24h",
            "schedule": crontab(minute="*/30"),
        },
        "dispatch-reminders-1h-every-15-minutes": {
            "task": "reminder_tasks.dispatch_1h",
            "schedule": crontab(minute="*/15"),
        },
    },
)
