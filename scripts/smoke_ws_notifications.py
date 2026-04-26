"""Manual WS smoke for I-4.2.4.

Run from host:
    python scripts/smoke_ws_notifications.py <PROF_TOKEN>

Cilj:
  1. Bez tokena → 4401 close.
  2. Sa validnim tokenom → connect + initial ``notification.unread_count``.
  3. Server publish-uje notif (preko CLI) → klijent dobija ``notification.created``
     u realnom vremenu.
  4. Klijent šalje malformed JSON → ``system.error`` (socket ostaje otvoren).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

import websockets

WS_URL = "ws://localhost:8000/api/v1/notifications/stream"


async def test_no_token() -> None:
    print("\n[1] Bez tokena → očekujemo close 4401 posle accept-a")
    try:
        async with websockets.connect(WS_URL) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=2)
                print("    UNEXPECTED: dobili poruku umesto close")
            except websockets.exceptions.ConnectionClosed as exc:
                print(f"    OK: closed code={exc.code} reason={exc.reason!r}")
    except websockets.exceptions.InvalidStatus as exc:
        print(f"    OK: HTTP rejected (status {exc.response.status_code})")
    except websockets.exceptions.ConnectionClosed as exc:
        print(f"    OK: closed code={exc.code} reason={exc.reason!r}")


async def test_invalid_token() -> None:
    print("\n[2] Invalid token → očekujemo close 4401")
    try:
        async with websockets.connect(f"{WS_URL}?token=garbage.jwt.value") as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=2)
                print("    UNEXPECTED: dobili poruku")
            except websockets.exceptions.ConnectionClosed as exc:
                print(f"    OK: closed code={exc.code} reason={exc.reason!r}")
    except websockets.exceptions.ConnectionClosed as exc:
        print(f"    OK: closed code={exc.code} reason={exc.reason!r}")


async def test_valid_token(token: str) -> None:
    print("\n[3] Valid token → očekujemo notification.unread_count snapshot")
    async with websockets.connect(f"{WS_URL}?token={token}") as ws:
        first = await asyncio.wait_for(ws.recv(), timeout=3)
        env = json.loads(first)
        assert env["event"] == "notification.unread_count", env
        print(f"    OK: snapshot env={env}")

        # Šalji nepoznat event → očekujemo system.error, socket ostaje otvoren.
        await ws.send(json.dumps({"event": "client.bogus", "data": {}}))
        try:
            err_raw = await asyncio.wait_for(ws.recv(), timeout=2)
            err = json.loads(err_raw)
            assert err["event"] == "system.error", err
            print(f"    OK: validation error env={err}")
        except asyncio.TimeoutError:
            print("    UNEXPECTED: nije stigao system.error")

        # Šalji malformed JSON → opet system.error.
        await ws.send("{not-json")
        try:
            err_raw = await asyncio.wait_for(ws.recv(), timeout=2)
            err = json.loads(err_raw)
            assert err["event"] == "system.error", err
            print(f"    OK: malformed env={err}")
        except asyncio.TimeoutError:
            print("    UNEXPECTED: nije stigao system.error za malformed")

        # Pošalji system.pong → ne treba odgovor, samo ne sme da padne.
        await ws.send(json.dumps({"event": "system.pong", "data": {}}))
        await asyncio.sleep(0.1)
        print("    OK: system.pong sent (no response expected)")


async def test_realtime_publish(token: str, user_id: str) -> None:
    print("\n[4] Realtime: connect → backend kreira notif → očekujemo notification.created")
    async with websockets.connect(f"{WS_URL}?token={token}") as ws:
        # Pojeđi initial unread_count
        await asyncio.wait_for(ws.recv(), timeout=3)

        # Trigger create kroz docker exec — pošalji u pozadini
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "studentska_backend", "python", "-c",
            f"""
import asyncio
from uuid import UUID
from app.core.database import AsyncSessionLocal
from app.core.dependencies import get_redis
from app.models.enums import NotificationType
from app.services import notification_service

async def main():
    async with AsyncSessionLocal() as db:
        redis = await get_redis()
        await notification_service.create(
            db, redis,
            user_id=UUID('{user_id}'),
            type=NotificationType.NEW_APPOINTMENT_REQUEST,
            title='[WS-SMOKE] Real-time test',
            body='Trigger iz I-4.2.4 smoke skripte.',
            data={{'idx': 1}},
        )

asyncio.run(main())
""",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        # Ne čekamo proc — paralelno čitamo WS frame.

        t0 = time.monotonic()
        got_created = False
        got_count = False
        deadline = t0 + 5
        while not (got_created and got_count) and time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                break
            env = json.loads(raw)
            elapsed = time.monotonic() - t0
            if env["event"] == "notification.created":
                got_created = True
                print(
                    f"    OK: notification.created in {elapsed*1000:.0f}ms "
                    f"title={env['data'].get('title')!r}"
                )
            elif env["event"] == "notification.unread_count":
                got_count = True
                print(
                    f"    OK: notification.unread_count in {elapsed*1000:.0f}ms "
                    f"count={env['data'].get('count')}"
                )

        await proc.wait()
        if not got_created:
            print("    FAIL: nije stigao notification.created")
        if not got_count:
            print("    FAIL: nije stigao notification.unread_count")


async def main():
    token = sys.argv[1] if len(sys.argv) > 1 else None
    user_id = sys.argv[2] if len(sys.argv) > 2 else None
    if not token or not user_id:
        print("Usage: python scripts/smoke_ws_notifications.py <TOKEN> <USER_ID>")
        sys.exit(1)

    await test_no_token()
    await test_invalid_token()
    await test_valid_token(token)
    await test_realtime_publish(token, user_id)


if __name__ == "__main__":
    asyncio.run(main())
