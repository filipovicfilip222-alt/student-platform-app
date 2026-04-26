"""End-to-end test za I-4.2.5:

Profesor approve PENDING zahtev → Celery task `send_appointment_confirmed`
emit-uje email + in-app notif → student-ov otvoren WS prima
``notification.created`` envelope u realnom vremenu.

Cilj acceptance kriterijuma 4.2 §1:
    "Profesor odobri zahtev → student vidi novi notif badge < 2s bez reload-a"

Run:
    python scripts/e2e_approve_to_notification.py \\
        <STUDENT_TOKEN> <PROF_TOKEN> <APPOINTMENT_ID>
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx
import websockets

WS_URL = "ws://localhost:8000/api/v1/notifications/stream"
APPROVE_URL = "http://localhost:8000/api/v1/professors/requests/{aid}/approve"


async def listen_for_created(token: str, deadline: float) -> dict | None:
    async with websockets.connect(f"{WS_URL}?token={token}") as ws:
        # Pojeđi initial unread_count snapshot.
        await asyncio.wait_for(ws.recv(), timeout=3)
        print(f"[ws] connected, snapshot received at t+0.0s")

        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                break
            env = json.loads(raw)
            print(f"[ws] received event={env['event']} ts={env['ts']}")
            if env["event"] == "notification.created":
                return env
        return None


async def main():
    if len(sys.argv) < 4:
        print(
            "Usage: python scripts/e2e_approve_to_notification.py "
            "<STUDENT_TOKEN> <PROF_TOKEN> <APPOINTMENT_ID>"
        )
        sys.exit(1)

    student_token, prof_token, appointment_id = sys.argv[1], sys.argv[2], sys.argv[3]

    deadline = time.monotonic() + 10  # 10s upper bound (acceptance < 2s).

    # Listener task u pozadini.
    listener = asyncio.create_task(listen_for_created(student_token, deadline))

    # Sačekaj 1s da WS sigurno hvata događaje pre nego što okida approve.
    await asyncio.sleep(1.0)

    t_approve = time.monotonic()
    print(f"\n[approve] POST {APPROVE_URL.format(aid=appointment_id)}")
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(
            APPROVE_URL.format(aid=appointment_id),
            headers={"Authorization": f"Bearer {prof_token}"},
        )
        print(f"[approve] HTTP {r.status_code} body={r.json()}")

    env = await listener
    if env is None:
        print("\n[FAIL] Nije stigao notification.created u 10s prozoru.")
        sys.exit(2)

    elapsed_ms = (time.monotonic() - t_approve) * 1000
    print(f"\n[OK] notification.created stigao za {elapsed_ms:.0f}ms posle approve-a.")
    print(f"     type={env['data']['type']!r} title={env['data']['title']!r}")
    print(f"     data={env['data']['data']!r}")
    if elapsed_ms < 2000:
        print(f"[ACCEPTANCE] < 2s ✓")
    else:
        print(f"[ACCEPTANCE] ≥ 2s — proveri Celery worker performans.")


if __name__ == "__main__":
    asyncio.run(main())
