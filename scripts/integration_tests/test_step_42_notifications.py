"""End-to-end integration test za KORAK 4 (Faza 4.2) — notifications REST + WS stream.

Run protiv žive ``docker compose --profile app up`` instance na localhost-u
(kroz nginx port 80; override sa ``API_BASE`` / ``WS_BASE``).

Pokriva 7 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_1 §4.2 + ROADMAP §4.2).
Svaki test funkcija beleži tačno jedan PASS/FAIL rezultat — sumarni izveštaj
je 7/7 kad cela faza prolazi.

    1. WS auth (no token + invalid JWT) — oba scenarija → close 4401.
    2. WS RBAC — kanal je iz JWT ``sub`` claim-a (nema URL parametra za
       user_id), pa user A ne može da osluškuje notifikacije za user B.
       Two-WS test: backend kreira notif za A → A prima ``notification.created``,
       B ne prima ništa osim svog initial snapshot-a.
    3. Real-time delivery — backend kreira notif za korisnika sa otvorenim
       WS-om → klijent prima initial ``notification.unread_count`` snapshot
       + ``notification.created`` envelope u manje od 2 s (acceptance
       kriterijum CURSOR_PROMPT_1 §4.2).
    4. REST endpointi — list / unread-count / mark-read (sa 404
       idempotency) / read-all sa proverom Redis counter konzistentnosti.
    5. Heartbeat — server šalje ``system.ping`` unutar 30 s prozora.
    6. WS validation — nepoznat event tip → server vraća
       ``system.error{code: "VALIDATION_FAILED"}``, socket OSTAJE OTVOREN.
    7. Reconnect (terminal vs non-terminal) — close 4401 je terminalni
       (klijent NE sme da reconnect-uje sa istim tokenom; novi token radi),
       dok normal close 1000 (klijentska strana) ne menja state servera
       (ponovni connect sa istim tokenom radi odmah).

Idempotent: random suffix po run-u (registracija novih studenata), test
notif-i prefixovani sa ``[I-4.2.6 SMOKE]`` da se mogu naknadno cleanup-ovati.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import string
import sys
import time
from dataclasses import dataclass
from typing import Any

# Force UTF-8 ispis za Windows cp1252 konzole.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import websockets
from websockets.exceptions import ConnectionClosed

API = os.getenv("API_BASE", "http://localhost/api/v1")
WS_BASE = os.getenv("WS_BASE", "ws://localhost/api/v1")
BACKEND_CONTAINER = os.getenv("BACKEND_CONTAINER", "studentska_backend")

NOTIF_TITLE_PREFIX = "[I-4.2.6 SMOKE]"


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


# ── HTTP helpers ─────────────────────────────────────────────────────────────


def post(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def get(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def login(email: str, password: str) -> tuple[str, str]:
    r = post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body["user"]["id"]


def register_student(suffix: str) -> tuple[str, str]:
    email = f"qa_n42_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"N42-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


def ws_url(token: str) -> str:
    return f"{WS_BASE}/notifications/stream?token={token}"


# ── Backend ergonomics: trigger create from inside the container ─────────────


def trigger_create_via_docker(user_id: str, title: str, body: str = "Smoke body") -> None:
    """Kreira notifikaciju kroz ``docker exec`` REPL — koristi se u testovima
    3 i 4 (real-time delivery, RBAC) gde nemamo REST endpoint za "kreiraj
    notif kao admin". Test ne koristi Celery taskove direktno (oni su
    zavisni od appointment/strike/document state-a) — najjednostavniji
    determinizam je direktan poziv ``notification_service.create()``."""
    import subprocess

    py = (
        "import asyncio\n"
        "from uuid import UUID\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.core.dependencies import get_redis\n"
        "from app.models.enums import NotificationType\n"
        "from app.services import notification_service\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        "        redis = await get_redis()\n"
        f"        await notification_service.create(db, redis,\n"
        f"            user_id=UUID('{user_id}'),\n"
        f"            type=NotificationType.NEW_APPOINTMENT_REQUEST,\n"
        f"            title='{title}', body='{body}', data={{}})\n"
        "asyncio.run(main())\n"
    )
    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "-c", py]
    proc = subprocess.run(cmd, capture_output=True, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(
            f"trigger_create failed: rc={proc.returncode}\n"
            f"stderr={proc.stderr.decode(errors='replace')}"
        )


def cleanup_smoke_rows() -> int:
    """Izbriši sve [I-4.2.6 SMOKE] redove + resetuj counter-e za sve user-e."""
    import subprocess

    py = (
        "import asyncio\n"
        "from sqlalchemy import select, delete\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.core.dependencies import get_redis\n"
        "from app.models.notification import Notification\n"
        "from app.services.notification_service import notif_unread_key\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        "        rows = (await db.execute(select(Notification.user_id).where("
        f"            Notification.title.like('{NOTIF_TITLE_PREFIX}%')))).scalars().all()\n"
        "        affected = await db.execute(delete(Notification).where("
        f"            Notification.title.like('{NOTIF_TITLE_PREFIX}%')))\n"
        "        await db.commit()\n"
        "        redis = await get_redis()\n"
        "        for uid in set(rows):\n"
        "            await redis.delete(notif_unread_key(uid))\n"
        "        print(affected.rowcount)\n"
        "asyncio.run(main())\n"
    )
    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "-c", py]
    proc = subprocess.run(cmd, capture_output=True, timeout=20)
    if proc.returncode != 0:
        return 0
    out = proc.stdout.decode(errors="replace").strip().splitlines()
    try:
        return int(out[-1])
    except (ValueError, IndexError):
        return 0


# ── Tests ────────────────────────────────────────────────────────────────────


async def _close_code(url: str) -> int | None:
    """Pomoćnik: vrati ``CloseEvent.code`` posle pokušaja konekcije."""
    try:
        async with websockets.connect(url) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=3)
            except ConnectionClosed as exc:
                return exc.code
    except ConnectionClosed as exc:
        return exc.code
    return None


async def test_1_auth() -> None:
    print("\n=== TEST 1 — WS auth (no token + invalid JWT → close 4401) ===\n")
    code_no = await _close_code(f"{WS_BASE}/notifications/stream")
    code_bad = await _close_code(ws_url("garbage.jwt.value"))

    record(
        "WS auth: no token AND invalid JWT → close 4401",
        "oba scenarija code=4401",
        f"no_token={code_no}, invalid={code_bad}",
        code_no == 4401 and code_bad == 4401,
    )


async def test_2_rbac_isolation(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — RBAC: kanal iz JWT sub-a (cross-user izolacija) ===\n")
    # Otvori dva WS-a paralelno: A i B.
    a_url = ws_url(ctx["a_token"])
    b_url = ws_url(ctx["b_token"])

    async with websockets.connect(a_url) as ws_a, websockets.connect(b_url) as ws_b:
        # Pojeđi initial unread_count snapshote.
        await asyncio.wait_for(ws_a.recv(), timeout=3)
        await asyncio.wait_for(ws_b.recv(), timeout=3)

        # Trigger create za korisnika A.
        title_a = f"{NOTIF_TITLE_PREFIX} test_3 RBAC A"
        trigger_create_via_docker(ctx["a_id"], title_a)

        # A mora dobiti notification.created sa naslovom title_a.
        a_got_event = False
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws_a.recv(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                break
            env = json.loads(raw)
            if env["event"] == "notification.created" and env["data"]["title"] == title_a:
                a_got_event = True
                break

        # B u istom prozoru NE sme dobiti notification.created (heartbeat
        # ping nije problem — filtriramo).
        b_leaked = False
        try:
            while True:
                raw = await asyncio.wait_for(ws_b.recv(), timeout=1.0)
                env = json.loads(raw)
                if env["event"] == "notification.created":
                    b_leaked = True
                    break
        except asyncio.TimeoutError:
            pass

    record(
        "RBAC: A prima sopstvenu, B NE prima A-ovu (per-user channel)",
        "a_got_event=True AND b_leaked=False",
        f"a_got_event={a_got_event} b_leaked={b_leaked}",
        a_got_event and not b_leaked,
    )


async def test_3_realtime_delivery(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — Real-time delivery < 2s + initial snapshot ===\n")
    async with websockets.connect(ws_url(ctx["a_token"])) as ws:
        snapshot_raw = await asyncio.wait_for(ws.recv(), timeout=3)
        snapshot = json.loads(snapshot_raw)

        snapshot_ok = (
            snapshot["event"] == "notification.unread_count"
            and isinstance(snapshot["data"].get("count"), int)
        )

        title = f"{NOTIF_TITLE_PREFIX} test_4 realtime"
        t_publish = time.monotonic()
        trigger_create_via_docker(ctx["a_id"], title)

        got_created = False
        got_count = False
        latency_ms: float | None = None
        deadline = time.monotonic() + 5
        while not (got_created and got_count) and time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                break
            env = json.loads(raw)
            if env["event"] == "notification.created" and env["data"]["title"] == title:
                got_created = True
                latency_ms = (time.monotonic() - t_publish) * 1000
            elif env["event"] == "notification.unread_count":
                got_count = True

    record(
        "Initial snapshot + real-time notification.created < 2s",
        "snapshot is notification.unread_count AND created < 2000ms",
        f"snapshot_ok={snapshot_ok} got_created={got_created} latency_ms={latency_ms}",
        snapshot_ok
        and got_created
        and latency_ms is not None
        and latency_ms < 2000,
    )


async def test_4_rest_endpoints(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — REST endpointi: list / unread-count / mark-read / read-all ===\n")
    token = ctx["a_token"]
    checks: list[tuple[str, bool]] = []

    # Baseline: read-all → counter = 0.
    r = post("/notifications/read-all", token=token)
    pre_count = get("/notifications/unread-count", token=token).json()["count"]
    checks.append(("read-all baseline", r.status_code == 200 and pre_count == 0))

    # Kreiraj 3 smoke notif-a.
    for i in range(3):
        trigger_create_via_docker(ctx["a_id"], f"{NOTIF_TITLE_PREFIX} test_4 #{i+1}")

    list_resp = get("/notifications", token=token)
    list_body = list_resp.json()
    list_smoke = [n for n in list_body if n["title"].startswith(NOTIF_TITLE_PREFIX)]
    checks.append((
        "list DESC po created_at",
        list_resp.status_code == 200
        and len(list_smoke) >= 3
        and list_smoke[0]["title"].endswith("#3"),
    ))

    cnt = get("/notifications/unread-count", token=token).json()["count"]
    checks.append(("unread-count >= 3", cnt >= 3))

    # mark-read prvog → counter -= 1
    first_id = list_smoke[0]["id"]
    mr = post(f"/notifications/{first_id}/read", token=token)
    cnt_after = get("/notifications/unread-count", token=token).json()["count"]
    checks.append((
        "mark-read 200 + counter -= 1",
        mr.status_code == 200 and cnt_after == cnt - 1,
    ))

    # Idempotency: drugi put 404
    mr2 = post(f"/notifications/{first_id}/read", token=token)
    checks.append(("mark-read idempotency → 404", mr2.status_code == 404))

    # read-all → counter = 0
    ra = post("/notifications/read-all", token=token)
    cnt_zero = get("/notifications/unread-count", token=token).json()["count"]
    checks.append((
        "read-all → counter=0",
        ra.status_code == 200 and cnt_zero == 0,
    ))

    failed = [name for name, ok in checks if not ok]
    record(
        "REST endpointi (list / unread-count / mark-read / read-all)",
        "all 6 sub-checks pass",
        f"failed={failed}" if failed else "all pass",
        not failed,
    )


async def test_5_heartbeat(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Heartbeat (system.ping unutar 30s prozora) ===\n")
    # Server šalje ping na svaki 25s; čekamo do 30s + grace.
    got_ping = False
    seq: int | None = None
    async with websockets.connect(ws_url(ctx["a_token"])) as ws:
        # Pojeđi initial snapshot.
        await asyncio.wait_for(ws.recv(), timeout=3)
        deadline = time.monotonic() + 32  # 25s + grace za jitter / startup
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(
                    ws.recv(), timeout=max(0.1, deadline - time.monotonic())
                )
            except asyncio.TimeoutError:
                break
            env = json.loads(raw)
            if env["event"] == "system.ping":
                got_ping = True
                seq = env["data"].get("seq")
                break

    record(
        "Server šalje system.ping unutar 30s",
        "system.ping{seq:int} pre 30s",
        f"got_ping={got_ping} seq={seq}",
        got_ping and isinstance(seq, int),
    )


async def test_6_unknown_event_no_close(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — Nepoznat event → system.error, socket OPEN ===\n")
    async with websockets.connect(ws_url(ctx["a_token"])) as ws:
        await asyncio.wait_for(ws.recv(), timeout=3)  # initial snapshot

        await ws.send(json.dumps({"event": "client.bogus", "data": {}}))

        err_received = False
        ws_still_open = True
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=3)
            env = json.loads(raw)
            if (
                env["event"] == "system.error"
                and env["data"].get("code") == "VALIDATION_FAILED"
            ):
                err_received = True
        except ConnectionClosed:
            ws_still_open = False

        # Bonus: posle error envelope-a, pošalji system.pong i potvrdi da
        # socket prima i normalan input.
        if ws_still_open:
            try:
                await ws.send(json.dumps({"event": "system.pong", "data": {}}))
                await asyncio.sleep(0.2)
            except ConnectionClosed:
                ws_still_open = False

    record(
        "Nepoznat event → system.error VALIDATION_FAILED, socket ostaje OPEN",
        "system.error received AND ws still open",
        f"err_received={err_received} ws_still_open={ws_still_open}",
        err_received and ws_still_open,
    )


async def test_7_reconnect_terminal_vs_normal(ctx: dict[str, Any]) -> None:
    """Terminal close (4401) i normal close (1000) imaju različite reconnect
    semantike na strani klijenta:

      * 4401 sa ISTIM tokenom → server bi opet zatvorio sa 4401 (token
        nije magicno postao validan). Klijent mora prvo da refresh-uje
        token. Verifikujemo: invalid_token connect → 4401, ponovni connect
        sa VALIDNIM tokenom → uspeh.
      * Normal close (klijentska strana 1000) NE ostavlja state na serveru
        — sledeći connect istim validnim tokenom uspeva odmah.
    """
    print("\n=== TEST 7 — Reconnect: terminal (4401) vs normal close ===\n")

    # 4401 putanja: invalid → 4401, pa sa validnim tokenom → uspeh + snapshot.
    bad_code = await _close_code(ws_url("garbage.jwt.value"))
    valid_after_bad_ok = False
    async with websockets.connect(ws_url(ctx["a_token"])) as ws:
        try:
            env = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            valid_after_bad_ok = env["event"] == "notification.unread_count"
        except (ConnectionClosed, asyncio.TimeoutError):
            pass

    # Normal close putanja: connect → close-by-client → reconnect istim
    # tokenom → uspeh.
    normal_path_ok = False
    async with websockets.connect(ws_url(ctx["a_token"])) as ws:
        await asyncio.wait_for(ws.recv(), timeout=3)  # initial snapshot
        await ws.close(code=1000)  # client-side normal close

    async with websockets.connect(ws_url(ctx["a_token"])) as ws2:
        try:
            env = json.loads(await asyncio.wait_for(ws2.recv(), timeout=3))
            normal_path_ok = env["event"] == "notification.unread_count"
        except (ConnectionClosed, asyncio.TimeoutError):
            pass

    record(
        "Reconnect: 4401 terminal, 1000 normal — oba ponašanja rade",
        "bad→4401, valid token connect after bad OK, normal close + reconnect OK",
        f"bad_code={bad_code} valid_after_bad_ok={valid_after_bad_ok} normal_path_ok={normal_path_ok}",
        bad_code == 4401 and valid_after_bad_ok and normal_path_ok,
    )


# ── Setup ────────────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix()
    a_email, a_pw = register_student(f"a{suffix}")
    b_email, b_pw = register_student(f"b{suffix}")
    print(f"  registered A {a_email}")
    print(f"  registered B {b_email}")

    a_token, a_id = login(a_email, a_pw)
    b_token, b_id = login(b_email, b_pw)
    print(f"  logged in A id={a_id}")
    print(f"  logged in B id={b_id}")

    return {
        "a_token": a_token,
        "a_id": a_id,
        "b_token": b_token,
        "b_id": b_id,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


async def amain() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    try:
        await test_1_auth()
        await test_2_rbac_isolation(ctx)
        await test_3_realtime_delivery(ctx)
        await test_4_rest_endpoints(ctx)
        await test_5_heartbeat(ctx)
        await test_6_unknown_event_no_close(ctx)
        await test_7_reconnect_terminal_vs_normal(ctx)
    finally:
        cleanup_count = cleanup_smoke_rows()
        print(f"\n[cleanup] obrisano {cleanup_count} smoke notif redova")

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
