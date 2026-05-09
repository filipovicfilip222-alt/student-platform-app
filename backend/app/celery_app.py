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
        # ──────────────────────────────────────────────────────────────
        # Auto-NO_SHOW detekcija je PRIVREMENO ISKLJUČENA.
        #
        # Razlog: trenutna implementacija (`strike_tasks.detect_no_show`)
        # automatski postavlja `appointment.status = NO_SHOW` (i dodeljuje
        # 2 strike poena) za svaki APPROVED termin čiji je kraj prošao
        # > 30 min, BEZ flow-a u kome profesor potvrđuje da li je student
        # došao. Posledica: svaki termin koji profesor zaboravi da
        # markira kao COMPLETED automatski kažnjava studenta — false
        # positive masakr.
        #
        # Dodatno, do migracije 0006 PG enum `appointmentstatus` nije
        # imao `NO_SHOW` vrednost, pa je `add_strike` flush + Celery
        # `send_strike_added.delay()` punio notifikacije ali bi commit
        # padao na enum violation → strike rollback, notifikacija već
        # u Redisu — student dobija fantomske strike notifikacije bez
        # ijednog reda u `strike_records`.
        #
        # Ponovo uključiti TEK kada postoji „professor confirms attendance"
        # akcija (PRD §5.3): COMPLETED ili NO_SHOW manuelno; auto-task
        # ostaje samo kao safety net posle X dana profesorove neaktivnosti.
        # ──────────────────────────────────────────────────────────────
        # "detect-no-show-every-30-minutes": {
        #     "task": "strike_tasks.detect_no_show",
        #     "schedule": crontab(minute="*/30"),
        # },
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
