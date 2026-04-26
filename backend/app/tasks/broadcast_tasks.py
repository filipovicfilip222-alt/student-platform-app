"""broadcast_tasks.py — Celery fan-out za globalni admin broadcast (Faza 4.5).

Jedan Celery task za ceo broadcast (NE per-user sub-task) — argumentacija
iz CURRENT_STATE2 §4.5 implementation note-a:

  - 1 task vs 200 sub-task-ova za broadcast od 200 user-a
  - 1 retry vs 200 retry-a
  - Izolacija per-user greške kroz try/except (5 failover od 200 ne ruši
    ostalih 195)
  - Niža Redis broker latencija (manje task push-eva)

Kritični invariant: per-user IN_APP create i EMAIL send su u try/except
sa per-user log-ovanjem grešaka. ``recipient_count`` u ``broadcasts``
tabeli je "ciljani" broj resolve-ovan PRE Celery task-a — NE smanjuje
se kad neki user padne (greške idu samo u worker log).

DB pristup: koristi ``_fresh_db_session`` iz ``notifications.py`` (NullPool
helper koji izbegava cross-loop grešku iz deljenog ``AsyncSessionLocal``
pool-a — vidi tamošnji docstring za detalje).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence
from uuid import UUID

from sqlalchemy import select

from app.celery_app import celery_app
from app.core.email import send_generic_notification_email
from app.models.broadcast import Broadcast
from app.models.enums import NotificationType
from app.models.user import User
from app.services import notification_service
from app.tasks.notifications import _fresh_db_session, _new_redis

_log = logging.getLogger(__name__)


@celery_app.task(name="broadcast_tasks.fanout_broadcast")
def fanout_broadcast(
    broadcast_id: str,
    user_ids: Sequence[str],
    channels: Sequence[str],
) -> dict[str, int]:
    """Fan-out IN_APP + EMAIL na ciljane korisnike.

    Args:
        broadcast_id: UUID stringa za ``Broadcast`` red (čita se title/body
            iz DB-a — ne prosleđujemo u task argumente da bi serijalizacija
            bila lakša i body od 5000 chars ne pretrpava broker poruku).
        user_ids: Lista UUID stringova primaoca (već resolve-ovana u
            ``broadcast_service.dispatch``).
        channels: Lista ``"IN_APP"`` / ``"EMAIL"`` — kanali na kojima šaljemo.

    Returns:
        Dict ``{"sent": int, "failed": int}`` — sent = uspešni per-user
        ciklusi, failed = ciklusi gde je BAR jedan kanal pucnuo. Korisno
        za Celery flower dashboard / debug; ne čuva se u DB-u.

    Raises:
        Ne raise-uje — sve per-user greške su swallow-ovane sa
        ``_log.warning``-om, da privremeni Redis/SMTP ispad NE oborujte
        ceo broadcast (5 fail-eva od 200 → 195 i dalje dobiju notif).
        Task pad-a samo ako je sam broadcast row obrisan između
        ``dispatch`` commit-a i task pickup-a (corner case; vraća
        ``failed=0, sent=0``).
    """
    async def _run() -> dict[str, int]:
        in_app = "IN_APP" in channels
        do_email = "EMAIL" in channels

        if not user_ids:
            return {"sent": 0, "failed": 0}

        # Učitaj broadcast (title/body/data za envelope) i mapping
        # ``user_id -> email`` u jednom query-u (selectuje samo potrebne
        # kolone, ne ceo User row).
        async with _fresh_db_session() as db:
            br_result = await db.execute(
                select(Broadcast).where(Broadcast.id == UUID(broadcast_id))
            )
            broadcast = br_result.scalar_one_or_none()
            if broadcast is None:
                _log.warning(
                    "broadcast_tasks.fanout_broadcast: broadcast_id=%s not found",
                    broadcast_id,
                )
                return {"sent": 0, "failed": 0}

            users_result = await db.execute(
                select(User.id, User.email).where(
                    User.id.in_([UUID(uid) for uid in user_ids])
                )
            )
            users = list(users_result.all())

        title = broadcast.title
        body = broadcast.body
        notif_data = {
            "broadcast_id": str(broadcast.id),
            "target": broadcast.target,
            "faculty": broadcast.faculty,
        }

        # Per-user fan-out — IN_APP create i EMAIL send su SVAKI u svom
        # try/except, da privremeni Redis ispad ne ostavi user-a bez
        # email-a (ili obrnuto). Per-user log-ovanje greške mora da nosi
        # user_id da admin može pokrenuti retry ručno (eventualno u
        # Prompt 2 — za sada admin samo gleda log).
        sent = 0
        failed = 0

        # Redis client: jedan po fan-out ciklusu (svi user-i ga dele;
        # NE per-user da ne otvaramo 200 Redis konekcija). ``_new_redis``
        # vraća asyncio Redis vezan za TRENUTNI event loop.
        redis_client = _new_redis()
        try:
            for user_id, email in users:
                user_ok = True

                if in_app:
                    try:
                        # Notification create otvara svoj fresh DB session
                        # interno (_create_inapp koristi _fresh_db_session) —
                        # ovde direktno zovemo notification_service.create
                        # sa svojim fresh sesijom da ne otvaramo 2 sesije
                        # po user-u.
                        async with _fresh_db_session() as user_db:
                            await notification_service.create(
                                user_db,
                                redis_client,
                                user_id=user_id,
                                type=NotificationType.BROADCAST,
                                title=title,
                                body=body,
                                data=notif_data,
                                # Celery context — sinhronizovan await za
                                # push (asyncio.run cancel-uje background
                                # taskove). Vidi notification_service.create
                                # docstring za režime.
                                dispatch_push_in_background=False,
                            )
                    except Exception as exc:  # noqa: BLE001
                        user_ok = False
                        _log.warning(
                            "broadcast_tasks.fanout_broadcast: IN_APP create failed "
                            "broadcast_id=%s user_id=%s err=%s",
                            broadcast_id, user_id, exc,
                        )

                if do_email:
                    try:
                        send_generic_notification_email(
                            to_email=email,
                            subject=title,
                            title=title,
                            body_html=f"<p>{body}</p>",
                        )
                    except Exception as exc:  # noqa: BLE001
                        user_ok = False
                        _log.warning(
                            "broadcast_tasks.fanout_broadcast: EMAIL send failed "
                            "broadcast_id=%s user_id=%s err=%s",
                            broadcast_id, user_id, exc,
                        )

                if user_ok:
                    sent += 1
                else:
                    failed += 1
        finally:
            try:
                await redis_client.close()
            except Exception:
                pass

        _log.info(
            "broadcast_tasks.fanout_broadcast: broadcast_id=%s targeted=%d sent=%d failed=%d",
            broadcast_id, len(users), sent, failed,
        )
        return {"sent": sent, "failed": failed}

    return asyncio.run(_run())
