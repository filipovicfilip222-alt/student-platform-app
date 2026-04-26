"""End-to-end integration test for KORAK 3 (Faza 4.1) — chat WebSocket.

Runs against a live ``docker compose --profile app up`` stack on localhost
(through nginx on port 80 by default — set ``API_BASE`` / ``WS_BASE`` to
override). Exercises every close code from
``docs/websocket-schema.md §2.3`` plus the happy-path round-trip.

Tests (acceptance criteria from CURSOR_PROMPT_1 §3 / ROADMAP §4.1):
    1. Invalid JWT → close 4401.
    2. Non-participant → close 4403 (other-student token, valid appointment).
    3. Non-existent appointment → close 4404.
    4. Status PENDING (NOT_APPROVED) → ``chat.closed`` envelope with
       reason ``APPOINTMENT_CANCELLED`` + close 4430.
    5. WINDOW_EXPIRED — slot_datetime + 24h < now (set via direct
       ``docker exec studentska_postgres psql`` UPDATE because the API
       refuses to create slots in the past) → ``chat.closed`` reason
       ``WINDOW_EXPIRED`` + close 4430.
    6. 21st message → ``chat.limit_reached`` envelope + close 4409.
    7. Happy path round-trip: two WS clients on the same appointment;
       lead sends ``chat.send`` → professor receives ``chat.message``
       within 1 s.
    8. Per-sender rate limit (Redis SET NX PX 500) — second consecutive
       ``chat.send`` within 500 ms returns ``system.error RATE_LIMITED``
       with the connection still OPEN.

Idempotent: random suffix per run, isolated future dates per scenario.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import string
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import quote

# Force UTF-8 so prints with ≥ / Cyrillic don't crash on Windows cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import websockets
from websockets.exceptions import ConnectionClosed

API = os.getenv("API_BASE", "http://localhost/api/v1")
WS_BASE = os.getenv("WS_BASE", "ws://localhost/api/v1")
PG_CONTAINER = os.getenv("PG_CONTAINER", "studentska_postgres")
PG_USER = os.getenv("POSTGRES_USER", "studentska")
PG_DB = os.getenv("POSTGRES_DB", "studentska_platforma")

PROF_EMAIL = "profesor1@fon.bg.ac.rs"
SEED_PASSWORD = "Seed@2024!"


def rand_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@dataclass
class Result:
    name: str
    expected: str
    actual: str
    passed: bool


RESULTS: list[Result] = []


def record(name: str, expected: str, actual: str, passed: bool) -> None:
    icon = "[OK]" if passed else "[FAIL]"
    print(f"  {icon} {name}")
    print(f"      expected: {expected}")
    print(f"      actual:   {actual}")
    RESULTS.append(Result(name, expected, actual, passed))


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def post(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def login(email: str, password: str) -> str:
    r = post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def register_student(suffix: str) -> tuple[str, str]:
    email = f"qa_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": suffix.title(),
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


# ── Date helpers ──────────────────────────────────────────────────────────────


def first_monday_of_month(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(0 - d.weekday()) % 7)


def to_iso_utc(d: date, hour: int = 14, minute: int = 0) -> str:
    return datetime.combine(d, time(hour, minute), tzinfo=timezone.utc).isoformat()


# ── Booking helper: create slot, book, approve. Returns appointment_id. ──────


def create_approved_appointment(
    prof_token: str,
    student_token: str,
    slot_datetime_iso: str,
) -> str:
    """Create a new slot, book it as the student, approve as prof."""
    slot = post(
        "/professors/slots",
        token=prof_token,
        json={
            "slot_datetime": slot_datetime_iso,
            "duration_minutes": 30,
            "consultation_type": "UZIVO",
            "max_students": 1,
            "is_available": True,
        },
    )
    if slot.status_code != 201:
        raise RuntimeError(f"slot create {slot.status_code} {slot.text}")
    slot_payload = slot.json()
    slot_obj = slot_payload[0] if isinstance(slot_payload, list) else slot_payload

    book = post(
        "/students/appointments",
        token=student_token,
        json={
            "slot_id": slot_obj["id"],
            "topic_category": "ISPIT",
            "description": "QA chat WS test setup booking.",
        },
    )
    if book.status_code != 200:
        raise RuntimeError(f"book {book.status_code} {book.text}")
    appt = book.json()
    if appt["status"] != "APPROVED":
        ar = post(
            f"/professors/requests/{appt['id']}/approve",
            token=prof_token,
        )
        if ar.status_code != 200:
            raise RuntimeError(f"approve {ar.status_code} {ar.text}")
    return appt["id"]


def create_pending_appointment(
    prof_token: str,
    student_token: str,
    slot_datetime_iso: str,
) -> str:
    """Create a slot + book it, but do NOT approve. Returns appointment_id."""
    slot = post(
        "/professors/slots",
        token=prof_token,
        json={
            "slot_datetime": slot_datetime_iso,
            "duration_minutes": 30,
            "consultation_type": "UZIVO",
            "max_students": 1,
            "is_available": True,
        },
    )
    if slot.status_code != 201:
        raise RuntimeError(f"slot create {slot.status_code} {slot.text}")
    slot_payload = slot.json()
    slot_obj = slot_payload[0] if isinstance(slot_payload, list) else slot_payload

    book = post(
        "/students/appointments",
        token=student_token,
        json={
            "slot_id": slot_obj["id"],
            "topic_category": "ISPIT",
            "description": "QA chat WS test PENDING setup.",
        },
    )
    if book.status_code != 200:
        raise RuntimeError(f"book pending {book.status_code} {book.text}")
    return book.json()["id"]


def force_slot_into_past(appointment_id: str) -> None:
    """Run a raw UPDATE to push slot_datetime 25h into the past so the
    chat window has expired. Required because the public slot API rejects
    past datetimes (correctly), but we need the WINDOW_EXPIRED scenario.
    """
    sql = (
        "UPDATE availability_slots SET slot_datetime = NOW() - INTERVAL '25 hours' "
        "WHERE id = (SELECT slot_id FROM appointments WHERE id = '"
        + appointment_id
        + "');"
    )
    cmd = [
        "docker", "exec", PG_CONTAINER,
        "psql", "-U", PG_USER, "-d", PG_DB,
        "-c", sql,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(
            f"force_slot_into_past failed for {appointment_id}: {out.stderr}"
        )


# ── WebSocket helpers ─────────────────────────────────────────────────────────


def ws_url(appointment_id: str, token: str) -> str:
    return (
        f"{WS_BASE}/appointments/{appointment_id}/chat?token={quote(token, safe='')}"
    )


async def connect_and_observe(
    appointment_id: str,
    token: str,
    *,
    timeout: float = 5.0,
) -> tuple[int | None, str, list[dict]]:
    """Open WS, drain frames until close. Returns (close_code, reason, frames)."""
    frames: list[dict] = []
    try:
        async with websockets.connect(ws_url(appointment_id, token)) as ws:
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    try:
                        frames.append(json.loads(raw))
                    except Exception:  # noqa: BLE001
                        frames.append({"raw": raw})
            except ConnectionClosed as e:
                return e.code, e.reason or "", frames
            except asyncio.TimeoutError:
                return None, "timeout", frames
    except websockets.exceptions.InvalidStatus as e:
        return -1, f"http {e.response.status_code}", frames
    return None, "no close", frames


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_1_invalid_jwt(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — Invalid JWT → close 4401 ===\n")
    code, reason, _ = await connect_and_observe(
        ctx["appt_main"], "not.a.valid.jwt", timeout=2.0
    )
    record(
        "Invalid JWT closes 4401",
        "code=4401",
        f"code={code} reason={reason!r}",
        code == 4401,
    )


async def test_2_non_participant(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — Non-participant student → close 4403 ===\n")
    code, reason, _ = await connect_and_observe(
        ctx["appt_main"], ctx["other_token"], timeout=2.0
    )
    record(
        "Non-participant closes 4403",
        "code=4403",
        f"code={code} reason={reason!r}",
        code == 4403,
    )


async def test_3_not_found(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — Non-existent appointment id → close 4404 ===\n")
    bogus = "00000000-0000-0000-0000-000000000000"
    code, reason, _ = await connect_and_observe(
        bogus, ctx["lead_token"], timeout=2.0
    )
    record(
        "Bogus appointment id closes 4404",
        "code=4404",
        f"code={code} reason={reason!r}",
        code == 4404,
    )


async def test_4_pending_appointment(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — PENDING appointment → chat.closed APPOINTMENT_CANCELLED + close 4430 ===\n")
    code, reason, frames = await connect_and_observe(
        ctx["appt_pending"], ctx["lead_token"], timeout=2.0
    )
    closed_envs = [f for f in frames if f.get("event") == "chat.closed"]
    has_envelope = bool(closed_envs) and closed_envs[0]["data"]["reason"] == "APPOINTMENT_CANCELLED"
    record(
        "PENDING → chat.closed APPOINTMENT_CANCELLED + close 4430",
        "code=4430 + chat.closed{reason='APPOINTMENT_CANCELLED'}",
        f"code={code} reason={reason!r} closed_envs={closed_envs}",
        code == 4430 and has_envelope,
    )


async def test_5_window_expired(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — slot+24h elapsed → chat.closed WINDOW_EXPIRED + close 4430 ===\n")
    code, reason, frames = await connect_and_observe(
        ctx["appt_expired"], ctx["lead_token"], timeout=2.0
    )
    closed_envs = [f for f in frames if f.get("event") == "chat.closed"]
    has_envelope = bool(closed_envs) and closed_envs[0]["data"]["reason"] == "WINDOW_EXPIRED"
    record(
        "Expired window → chat.closed WINDOW_EXPIRED + close 4430",
        "code=4430 + chat.closed{reason='WINDOW_EXPIRED'}",
        f"code={code} reason={reason!r} closed_envs={closed_envs}",
        code == 4430 and has_envelope,
    )


async def test_6_message_limit(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — 21st message → chat.limit_reached + close 4409 ===\n")
    appt_id = ctx["appt_limit"]
    token = ctx["lead_token"]

    async with websockets.connect(ws_url(appt_id, token)) as ws:
        # Drain chat.history (should be empty for fresh appointment).
        history = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        if history.get("event") != "chat.history":
            record(
                "21st message close 4409",
                "first frame chat.history",
                f"got {history}",
                False,
            )
            return

        # Send 20 messages, spaced 600ms apart so the 500ms rate limit lets
        # them all through. Drain echoes inline so the recv buffer doesn't
        # backpressure the server.
        for i in range(20):
            await ws.send(
                json.dumps({"event": "chat.send", "data": {"content": f"msg #{i + 1}"}})
            )
            # Wait up to 2s for the chat.message echo
            got_msg = False
            for _ in range(3):
                try:
                    frame = json.loads(
                        await asyncio.wait_for(ws.recv(), timeout=2.0)
                    )
                except asyncio.TimeoutError:
                    break
                if frame.get("event") == "chat.message":
                    got_msg = True
                    break
                # otherwise ignore (could be a stray ping etc.)
            if not got_msg:
                record(
                    "21st message close 4409",
                    "all 20 sends produce chat.message echo",
                    f"send #{i + 1} did not echo",
                    False,
                )
                return
            await asyncio.sleep(0.6)

        # 21st send → expect chat.limit_reached + close 4409
        await ws.send(
            json.dumps({"event": "chat.send", "data": {"content": "msg #21"}})
        )

        got_limit = False
        close_code: int | None = None
        close_reason = ""
        try:
            for _ in range(5):
                frame = json.loads(
                    await asyncio.wait_for(ws.recv(), timeout=3.0)
                )
                if frame.get("event") == "chat.limit_reached":
                    got_limit = True
        except ConnectionClosed as e:
            close_code = e.code
            close_reason = e.reason or ""
        except asyncio.TimeoutError:
            pass

        record(
            "21st message → chat.limit_reached + close 4409",
            "chat.limit_reached envelope + code=4409",
            f"got_limit={got_limit} close_code={close_code} reason={close_reason!r}",
            got_limit and close_code == 4409,
        )


async def test_7_realtime_roundtrip(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 7 — Real-time round-trip (lead → prof < 1s) ===\n")
    appt_id = ctx["appt_roundtrip"]

    async with websockets.connect(ws_url(appt_id, ctx["lead_token"])) as lead_ws, \
            websockets.connect(ws_url(appt_id, ctx["prof_token"])) as prof_ws:
        # Drain initial chat.history on each side
        await asyncio.wait_for(lead_ws.recv(), timeout=5.0)
        await asyncio.wait_for(prof_ws.recv(), timeout=5.0)

        async def recv_chat_message(ws_, marker: str) -> tuple[float, dict]:
            t0 = asyncio.get_event_loop().time()
            for _ in range(5):
                frame = json.loads(
                    await asyncio.wait_for(ws_.recv(), timeout=3.0)
                )
                if (
                    frame.get("event") == "chat.message"
                    and frame["data"]["content"] == marker
                ):
                    return asyncio.get_event_loop().time() - t0, frame
            raise AssertionError(f"never received marker {marker}")

        marker = f"hello-{rand_suffix()}"
        # Send + measure prof receive latency
        prof_recv_task = asyncio.create_task(recv_chat_message(prof_ws, marker))
        lead_recv_task = asyncio.create_task(recv_chat_message(lead_ws, marker))
        send_t0 = asyncio.get_event_loop().time()
        await lead_ws.send(
            json.dumps({"event": "chat.send", "data": {"content": marker}})
        )
        prof_dt, prof_frame = await prof_recv_task
        lead_dt, lead_frame = await lead_recv_task
        elapsed = asyncio.get_event_loop().time() - send_t0

        record(
            "Lead → Prof round-trip < 1 s",
            f"prof receives '{marker}' as chat.message in < 1 s",
            f"elapsed_total={elapsed:.3f}s prof_dt={prof_dt:.3f}s lead_dt={lead_dt:.3f}s",
            prof_dt < 1.0
            and prof_frame["data"]["content"] == marker
            and lead_frame["data"]["content"] == marker,
        )


async def test_8_rate_limit(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 8 — Per-sender rate limit → system.error RATE_LIMITED (no close) ===\n")
    appt_id = ctx["appt_roundtrip"]

    async with websockets.connect(ws_url(appt_id, ctx["lead_token"])) as ws:
        # Drain history
        await asyncio.wait_for(ws.recv(), timeout=5.0)
        # Two consecutive sends within 500ms → second should be rate-limited
        await ws.send(
            json.dumps({"event": "chat.send", "data": {"content": "burst-1"}})
        )
        await ws.send(
            json.dumps({"event": "chat.send", "data": {"content": "burst-2"}})
        )

        rate_limited = False
        ws_still_open = True
        for _ in range(6):
            try:
                frame = json.loads(
                    await asyncio.wait_for(ws.recv(), timeout=2.0)
                )
            except asyncio.TimeoutError:
                break
            except ConnectionClosed:
                ws_still_open = False
                break
            if (
                frame.get("event") == "system.error"
                and frame["data"].get("code") == "RATE_LIMITED"
            ):
                rate_limited = True
                # don't break — confirm WS stays open
        try:
            ws_state = ws.state.value if hasattr(ws.state, "value") else str(ws.state)
        except Exception:  # noqa: BLE001
            ws_state = "?"

        record(
            "Per-sender rate limit → system.error RATE_LIMITED, no close",
            "system.error{code='RATE_LIMITED'} received AND ws stays open",
            f"rate_limited={rate_limited} ws_still_open={ws_still_open} state={ws_state}",
            rate_limited and ws_still_open,
        )


# ── Setup ─────────────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix()
    lead_email, lead_pw = register_student(f"chwsl{suffix}")
    other_email, other_pw = register_student(f"chwso{suffix}")
    print(f"  registered lead   {lead_email}")
    print(f"  registered other  {other_email}")

    prof_token = login(PROF_EMAIL, SEED_PASSWORD)
    lead_token = login(lead_email, lead_pw)
    other_token = login(other_email, other_pw)
    print("  logged in: prof, lead, other")

    base_month = first_monday_of_month(2031, 5)
    # Four appointments, each with its own slot at distinct times to avoid
    # the same-day conflict guard.
    print("  creating appt_main (APPROVED, used by tests 1/2/3) ...")
    appt_main = create_approved_appointment(
        prof_token, lead_token, to_iso_utc(base_month, hour=10)
    )
    print(f"    → {appt_main}")

    print("  creating appt_pending (PENDING, used by test 4) ...")
    appt_pending = create_pending_appointment(
        prof_token, lead_token, to_iso_utc(base_month, hour=11)
    )
    print(f"    → {appt_pending}")

    print("  creating appt_expired (APPROVED, slot pushed 25h into past) ...")
    appt_expired = create_approved_appointment(
        prof_token, lead_token, to_iso_utc(base_month, hour=12)
    )
    force_slot_into_past(appt_expired)
    print(f"    → {appt_expired}")

    print("  creating appt_limit (APPROVED, used by test 6 — 21st message) ...")
    appt_limit = create_approved_appointment(
        prof_token, lead_token, to_iso_utc(base_month, hour=13)
    )
    print(f"    → {appt_limit}")

    print("  creating appt_roundtrip (APPROVED, used by tests 7/8) ...")
    appt_roundtrip = create_approved_appointment(
        prof_token, lead_token, to_iso_utc(base_month, hour=14)
    )
    print(f"    → {appt_roundtrip}")

    return {
        "prof_token": prof_token,
        "lead_token": lead_token,
        "other_token": other_token,
        "appt_main": appt_main,
        "appt_pending": appt_pending,
        "appt_expired": appt_expired,
        "appt_limit": appt_limit,
        "appt_roundtrip": appt_roundtrip,
    }


# ── Main ──────────────────────────────────────────────────────────────────────


async def amain() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    await test_1_invalid_jwt(ctx)
    await test_2_non_participant(ctx)
    await test_3_not_found(ctx)
    await test_4_pending_appointment(ctx)
    await test_5_window_expired(ctx)
    await test_6_message_limit(ctx)
    await test_7_realtime_roundtrip(ctx)
    await test_8_rate_limit(ctx)

    print("\n=== SUMMARY ===\n")
    width = max(len(r.name) for r in RESULTS) if RESULTS else 0
    for r in RESULTS:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name:<{width}}")
    failed = sum(1 for r in RESULTS if not r.passed)
    print(f"\n  {len(RESULTS) - failed}/{len(RESULTS)} passed.")
    return 0 if failed == 0 else 1


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
