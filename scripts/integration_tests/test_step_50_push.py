"""End-to-end integration test za KORAK 1 Prompta 2 — Web Push notifikacije.

Run protiv žive ``docker compose --profile app up`` instance na localhost-u
(kroz nginx port 80; override sa ``API_BASE``).

Pokriva 6 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_2_DEMO_READY.md
KORAK 1 + PRD §5.3). Svaki test funkcija beleži tačno jedan PASS/FAIL
rezultat — sumarni izveštaj je 6/6 kad cela faza prolazi.

    1. VAPID javni ključ ruta — auth obavezna; sa validnim tokenom vraća
       neprazan ``public_key`` (base64url ~87 chars). Bez tokena → 401.
    2. Subscribe UPSERT idempotency — drugi POST sa istim endpoint-om za
       istog korisnika ne kreira drugi red (UNIQUE ``(user_id, endpoint)``);
       vraća isti ``id``, DB COUNT ostaje 1.
    3. Subscribe validacija — http:// endpoint → 422 (Pydantic
       ``field_validator`` zahteva https://); kratki endpoint (< 20 chars)
       → 422 (min_length); malformed JSON keys → 422.
    4. Unsubscribe idempotency — prvi POST za postojeću pretplatu vraća
       "Pretplata uklonjena.", drugi POST za ne-postojeću vraća
       "Pretplata već nije postojala." (oba 200). DB COUNT = 0.
    5. Cross-user isolation — User A i User B oba subscribe-uju ISTI
       endpoint string (UNIQUE je per-user, ne globalan); A unsubscribe-uje
       svoj — B-ova pretplata ostaje netaknuta. DB count = 1 za B nakon
       cleanup-a A-a.
    6. Push fan-out hook — kreiranje notif-a za korisnika sa aktivnom
       pretplatom okida ``push_service.send_push`` u pozadini
       (``asyncio.create_task``). Sa lažnim endpoint-om dobijamo connection
       error (NE 410) — pretplata ostaje, in-app i Redis counter rade
       normalno. Verifikujemo: notification red ubeležen, unread count
       incremented, pretplata ostala u DB-u.

Idempotent: random suffix po run-u (registracija novih studenata),
pretplate prefiksovane sa ``https://qa-test.local/``, smoke notif title sa
``[I-50.4 SMOKE]`` da se mogu cleanup-ovati.

NB: Ne testiramo stvarni push delivery na FCM/Mozilla — to je non-deterministic
(zahteva permission grant u browseru, online VAPID handshake sa eksternim
servisom). Hook + DB ponašanje je dovoljan acceptance signal — manualna E2E
verifikacija (otvori app u Chrome-u, click bell, dozvoli notifikacije,
zatvori tab, drugi student kreira appointment, OS notification se pojavi)
ide u demo skriptu (CURSOR_PROMPT_2_DEMO_READY §5).
"""

from __future__ import annotations

import asyncio
import os
import random
import string
import sys
from dataclasses import dataclass
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
BACKEND_CONTAINER = os.getenv("BACKEND_CONTAINER", "studentska_backend")

NOTIF_TITLE_PREFIX = "[I-50.4 SMOKE]"
ENDPOINT_HOST_PREFIX = "https://qa-test-i504.local/push/"

# Fiksni format ključeva (base64url 65 i 16 bytes raw, isto kao realan
# Chrome PushSubscription.toJSON() output) — pywebpush ih parsuje pre
# nego što pokuša da otvori HTTP konekciju ka endpoint-u, pa moraju biti
# tehnički validni.
SAMPLE_P256DH = (
    "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCt-srSMyq6dHUuaeI8YQHjQ_3WC1f"
    "nkjStHrL8R5NtnJ_vIeS1tw"
)
SAMPLE_AUTH = "tBHItJI5svbpez7KI4CCXg"


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
    email = f"qa_p50_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"P50-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


def make_subscribe_payload(endpoint: str) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": SAMPLE_P256DH,
            "auth": SAMPLE_AUTH,
        },
        "user_agent": "QA-I504/1.0 (integration test)",
    }


# ── Backend ergonomics — direct-from-container helpers ──────────────────────


def _docker_run_python(py: str, *, timeout: int = 20) -> tuple[int, str, str]:
    """Helper za izvršavanje Python snippet-a unutar backend kontejnera."""
    import subprocess

    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "-c", py]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return (
        proc.returncode,
        proc.stdout.decode(errors="replace").strip(),
        proc.stderr.decode(errors="replace").strip(),
    )


def count_subs_for_user(user_id: str) -> int:
    """COUNT ``push_subscriptions`` redova za zadatog korisnika.

    Backend kontejner ima ``echo=True`` na engine-u (vidi
    ``app/core/database.py``), pa SQLAlchemy curi ``BEGIN/ROLLBACK`` log
    linije u stdout posle našeg ``print``-a. Zato koristimo tagged prefix
    (``COUNT_RESULT:``) i grep-ujemo prvu match liniju, umesto da
    uzimamo zadnju liniju output-a.
    """
    py = (
        "import asyncio\n"
        "from sqlalchemy import select, func\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.models.push_subscription import PushSubscription\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        f"        n = await db.scalar(select(func.count()).select_from(PushSubscription).where(PushSubscription.user_id == '{user_id}'))\n"
        "        print(f'COUNT_RESULT:{int(n or 0)}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"count_subs_for_user failed: rc={rc} stderr={err}")
    for line in out.splitlines():
        if line.startswith("COUNT_RESULT:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"count_subs_for_user: COUNT_RESULT line not found in:\n{out}")


def trigger_create_via_docker(
    user_id: str,
    title: str,
    body: str = "Smoke body",
    notif_type: str = "APPOINTMENT_CONFIRMED",
) -> str:
    """Kreira notifikaciju kroz ``docker exec``. Koristi
    ``dispatch_push_in_background=False`` da bi push fan-out bio
    **await-ovan** (ne fire-and-forget): unutar
    ``docker exec ... asyncio.run(main())`` event loop se zatvara čim
    main korutina vrati, pa bi ``asyncio.create_task(_safe_push())``
    bio otkazan i nikad ne bi pokrenuo push servis. Sa flag-om False,
    isti pattern koji koristimo u Celery taskovima
    (``app/tasks/notifications.py``), push poziv se kompletno izvrši pre
    nego što process izađe — pa stderr-snimak može da pokaže
    ``push_service`` log linije kao dokaz da je hook stvarno okinut.

    Tip je ``APPOINTMENT_CONFIRMED`` jer je u ``_URGENT_PUSH_TYPES``
    (probija quiet hours) i ``data={'appointment_id': '<uuid>'}``
    aktivira deep-link granu u ``push_service._build_deep_link``.

    Vraća stderr Python snippet-a (sadrži ``logging`` izlaz) — caller
    grep-uje za signal ``push_service`` poziva.
    """
    import subprocess
    import uuid as uuidlib

    fake_appt = str(uuidlib.uuid4())
    py = (
        "import asyncio, logging, sys\n"
        "logging.basicConfig(level=logging.INFO, stream=sys.stderr)\n"
        "from uuid import UUID\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.core.dependencies import get_redis\n"
        "from app.models.enums import NotificationType\n"
        "from app.services import notification_service\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        "        redis = await get_redis()\n"
        "        await notification_service.create(db, redis,\n"
        f"            user_id=UUID('{user_id}'),\n"
        f"            type=NotificationType.{notif_type},\n"
        f"            title='{title}', body='{body}',\n"
        f"            data={{'appointment_id': '{fake_appt}'}},\n"
        "            dispatch_push_in_background=False)\n"
        "asyncio.run(main())\n"
    )
    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "-c", py]
    # 30s budget — pywebpush blokirajući poziv na ne-postojeći host
    # rešava se DNS-NXDOMAIN ili connection refused za <2s; +threshold.
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(
            f"trigger_create failed: rc={proc.returncode}\n"
            f"stderr={proc.stderr.decode(errors='replace')}"
        )
    return proc.stderr.decode(errors="replace")


def cleanup_smoke_state() -> tuple[int, int]:
    """Izbriši sve I-50.4 smoke notif redove i sve test pretplate
    (one koje počinju sa ``ENDPOINT_HOST_PREFIX``). Resetuj unread
    countere za pogođene user-e da Redis ne ostane "prljav"."""
    py = (
        "import asyncio\n"
        "from sqlalchemy import select, delete\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.core.dependencies import get_redis\n"
        "from app.models.notification import Notification\n"
        "from app.models.push_subscription import PushSubscription\n"
        "from app.services.notification_service import notif_unread_key\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        "        rows = (await db.execute(select(Notification.user_id).where("
        f"            Notification.title.like('{NOTIF_TITLE_PREFIX}%')))).scalars().all()\n"
        f"        n_notif = (await db.execute(delete(Notification).where(Notification.title.like('{NOTIF_TITLE_PREFIX}%')))).rowcount\n"
        f"        n_subs = (await db.execute(delete(PushSubscription).where(PushSubscription.endpoint.like('{ENDPOINT_HOST_PREFIX}%')))).rowcount\n"
        "        await db.commit()\n"
        "        redis = await get_redis()\n"
        "        for uid in set(rows):\n"
        "            await redis.delete(notif_unread_key(uid))\n"
        "        print(f'CLEANUP_RESULT:{n_notif} {n_subs}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, _err = _docker_run_python(py, timeout=30)
    if rc != 0:
        return (0, 0)
    for line in out.splitlines():
        if line.startswith("CLEANUP_RESULT:"):
            try:
                a, b = line.split(":", 1)[1].split()
                return int(a), int(b)
            except (ValueError, IndexError):
                break
    return (0, 0)


# ── Test 1 — VAPID public key endpoint ───────────────────────────────────────


def test_1_vapid_public_key(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — GET /vapid-public-key (auth + non-empty) ===\n")

    r_anon = get("/notifications/vapid-public-key")
    anon_ok = r_anon.status_code == 401

    r_auth = get("/notifications/vapid-public-key", token=ctx["a_token"])
    auth_status_ok = r_auth.status_code == 200
    public_key = ""
    if auth_status_ok:
        try:
            public_key = r_auth.json().get("public_key", "")
        except Exception:
            public_key = ""
    key_ok = bool(public_key) and len(public_key) >= 80 and "=" not in public_key

    record(
        "VAPID GET — bez auth-a → 401",
        "401 Unauthorized",
        f"status={r_anon.status_code}",
        anon_ok,
    )
    record(
        "VAPID GET — sa auth-om vraća neprazan public_key (~87 chars base64url)",
        "200 + public_key length>=80, no '=' (base64url, not standard b64)",
        f"status={r_auth.status_code} len={len(public_key)} sample={public_key[:24]}…",
        auth_status_ok and key_ok,
    )


# ── Test 2 — Subscribe UPSERT idempotency ────────────────────────────────────


def test_2_subscribe_upsert(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — POST /subscribe UPSERT idempotency ===\n")

    endpoint = f"{ENDPOINT_HOST_PREFIX}upsert-{ctx['suffix']}"
    payload = make_subscribe_payload(endpoint)

    r1 = post("/notifications/subscribe", token=ctx["a_token"], json=payload)
    r2 = post("/notifications/subscribe", token=ctx["a_token"], json=payload)

    id1 = r1.json().get("id") if r1.status_code == 201 else None
    id2 = r2.json().get("id") if r2.status_code == 201 else None
    same_id = id1 is not None and id1 == id2

    try:
        n_subs = count_subs_for_user(ctx["a_id"])
    except Exception as exc:
        print(f"      [warn] count_subs_for_user failed: {exc}")
        n_subs = -1

    record(
        "Subscribe UPSERT — drugi POST istog endpoint-a vraća isti id",
        "r1.status=201, r2.status=201, id1==id2, db_count=1",
        f"r1={r1.status_code} r2={r2.status_code} id1={id1} id2={id2} db_count={n_subs}",
        r1.status_code == 201
        and r2.status_code == 201
        and same_id
        and n_subs == 1,
    )


# ── Test 3 — Subscribe validation ────────────────────────────────────────────


def test_3_subscribe_validation(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — POST /subscribe validacija (HTTPS, min_length) ===\n")

    http_payload = make_subscribe_payload("http://insecure.example.com/push/abc-xyz-123-456")
    r_http = post("/notifications/subscribe", token=ctx["a_token"], json=http_payload)

    short_payload = make_subscribe_payload("https://x")
    r_short = post("/notifications/subscribe", token=ctx["a_token"], json=short_payload)

    missing_keys_payload = {
        "endpoint": f"{ENDPOINT_HOST_PREFIX}missing-keys-{ctx['suffix']}",
        "keys": {"p256dh": SAMPLE_P256DH},
    }
    r_missing = post(
        "/notifications/subscribe",
        token=ctx["a_token"],
        json=missing_keys_payload,
    )

    record(
        "Subscribe validacija — sva 3 zlonamerna payload-a → 422",
        "422 za http://, 422 za <20 chars, 422 za missing 'auth' key",
        f"http={r_http.status_code} short={r_short.status_code} missing_auth={r_missing.status_code}",
        r_http.status_code == 422
        and r_short.status_code == 422
        and r_missing.status_code == 422,
    )


# ── Test 4 — Unsubscribe idempotency ────────────────────────────────────────


def test_4_unsubscribe_idempotent(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — POST /unsubscribe idempotency ===\n")

    endpoint = f"{ENDPOINT_HOST_PREFIX}unsub-{ctx['suffix']}"

    r_sub = post(
        "/notifications/subscribe",
        token=ctx["a_token"],
        json=make_subscribe_payload(endpoint),
    )
    sub_ok = r_sub.status_code == 201

    r_first = post(
        "/notifications/unsubscribe",
        token=ctx["a_token"],
        json={"endpoint": endpoint},
    )
    first_msg = r_first.json().get("message", "") if r_first.status_code == 200 else ""

    r_second = post(
        "/notifications/unsubscribe",
        token=ctx["a_token"],
        json={"endpoint": endpoint},
    )
    second_msg = r_second.json().get("message", "") if r_second.status_code == 200 else ""

    try:
        n_subs = count_subs_for_user(ctx["a_id"])
    except Exception:
        n_subs = -1

    record(
        "Unsubscribe — prvi briše ('uklonjena'), drugi vraća 'već nije postojala'",
        "sub=201, first=200 'uklonjena' substring, second=200 'već nije postojala' substring, db_count_after=1 (preostala iz testa 2)",
        f"sub={r_sub.status_code} first={r_first.status_code}/{first_msg!r} second={r_second.status_code}/{second_msg!r} db_count={n_subs}",
        sub_ok
        and r_first.status_code == 200
        and "uklonjena" in first_msg.lower()
        and r_second.status_code == 200
        and "već nije postojala" in second_msg.lower()
        and n_subs == 1,
    )


# ── Test 5 — Cross-user isolation ────────────────────────────────────────────


def test_5_cross_user_isolation(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Cross-user isolation (UNIQUE per-user, ne global) ===\n")

    shared_endpoint = f"{ENDPOINT_HOST_PREFIX}shared-{ctx['suffix']}"
    payload = make_subscribe_payload(shared_endpoint)

    r_a = post("/notifications/subscribe", token=ctx["a_token"], json=payload)
    r_b = post("/notifications/subscribe", token=ctx["b_token"], json=payload)

    both_ok = r_a.status_code == 201 and r_b.status_code == 201

    r_a_unsub = post(
        "/notifications/unsubscribe",
        token=ctx["a_token"],
        json={"endpoint": shared_endpoint},
    )

    try:
        n_a = count_subs_for_user(ctx["a_id"])
        n_b = count_subs_for_user(ctx["b_id"])
    except Exception:
        n_a, n_b = -1, -1

    record(
        "Cross-user — A i B mogu imati isti endpoint kao zasebne pretplate; A.unsub ne dira B",
        "both subscribe=201, A.unsub=200, A.count=1 (test 2 leftover), B.count=1 (shared sub preostala)",
        f"r_a={r_a.status_code} r_b={r_b.status_code} a_unsub={r_a_unsub.status_code} a_count={n_a} b_count={n_b}",
        both_ok and r_a_unsub.status_code == 200 and n_a == 1 and n_b == 1,
    )


# ── Test 6 — Push fan-out hook (notification_service.create dispatch) ───────


def test_6_push_hook_dispatched(ctx: dict[str, Any]) -> None:
    """Kreira notif za korisnika sa aktivnom pretplatom — verifikuje da:
      - in-app red je ubeležen,
      - unread count se povećao,
      - pretplata ostaje (connection error nije 410, ne briše se).

    NB: Sa lažnim ``qa-test-i504.local`` endpoint-om, ``pywebpush`` će
    failovati u ``asyncio.to_thread`` (DNS resolution / connection refused).
    To je **očekivano** ponašanje za integration test — push_service.send_push
    ulovi izuzetak i log-uje warning bez padanja request-a. Realan test
    delivery-ja (FCM/Mozilla) ide u manuelnu E2E demo skriptu, NE ovde.
    """
    print("\n=== TEST 6 — push fan-out hook iz notification_service.create ===\n")

    fresh_endpoint = f"{ENDPOINT_HOST_PREFIX}hook-{ctx['suffix']}"
    r_sub = post(
        "/notifications/subscribe",
        token=ctx["b_token"],
        json=make_subscribe_payload(fresh_endpoint),
    )
    sub_ok = r_sub.status_code == 201

    count_before = -1
    try:
        c = get("/notifications/unread-count", token=ctx["b_token"])
        count_before = c.json().get("count", -1) if c.status_code == 200 else -1
    except Exception:
        pass

    title = f"{NOTIF_TITLE_PREFIX} fan-out {ctx['suffix']}"
    push_log_signal = ""
    try:
        push_log_signal = trigger_create_via_docker(
            ctx["b_id"],
            title=title,
            body="Push fan-out smoke verifikacija",
            notif_type="APPOINTMENT_CONFIRMED",
        )
        trigger_ok = True
    except Exception as exc:
        print(f"      [warn] trigger_create_via_docker failed: {exc}")
        trigger_ok = False

    count_after = -1
    try:
        c2 = get("/notifications/unread-count", token=ctx["b_token"])
        count_after = c2.json().get("count", -1) if c2.status_code == 200 else -1
    except Exception:
        pass

    list_resp = get("/notifications", token=ctx["b_token"])
    found_in_list = False
    if list_resp.status_code == 200:
        for n in list_resp.json():
            if n.get("title") == title:
                found_in_list = True
                break

    try:
        n_subs_after = count_subs_for_user(ctx["b_id"])
    except Exception:
        n_subs_after = -1

    expected_min_count_after = (count_before + 1) if count_before >= 0 else 1

    # Hook signal: stderr Python snippet-a sadrži ``logging`` izlaz iz
    # push_service-a kad se ``send_push`` pokrene. Sa fake hostom
    # ``qa-test-i504.local``, dobijamo "WebPushException" ili
    # "unexpected error" warning — bilo koji od dva potvrđuje da je
    # hook stvarno pozvan (NIJE samo silent skip zbog praznog VAPID-a
    # ili zbog quiet hours-a).
    hook_invoked = (
        "push_service.send_push" in push_log_signal
        or "WebPushException" in push_log_signal
        or "push_service" in push_log_signal
    )

    record(
        "Push hook — notif kreiran in-app + counter +1 + pretplata ostaje + push_service log signal",
        "sub=201, trigger=ok, in_app_found=True, count_after >= count_before+1, b_subs >= 1, push_service log present",
        f"sub={r_sub.status_code} trigger={trigger_ok} found={found_in_list} "
        f"count {count_before}→{count_after} (expected ≥ {expected_min_count_after}) "
        f"b_subs={n_subs_after} hook_signal={hook_invoked}",
        sub_ok
        and trigger_ok
        and found_in_list
        and count_after >= expected_min_count_after
        and n_subs_after >= 1
        and hook_invoked,
    )


# ── Setup ────────────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix()
    a_email, _ = register_student(f"a{suffix}")
    b_email, _ = register_student(f"b{suffix}")
    print(f"  registered A {a_email}")
    print(f"  registered B {b_email}")

    a_token, a_id = login(a_email, "TestPass1!")
    b_token, b_id = login(b_email, "TestPass1!")
    print(f"  logged in A id={a_id}")
    print(f"  logged in B id={b_id}")

    return {
        "suffix": suffix,
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
        test_1_vapid_public_key(ctx)
        test_2_subscribe_upsert(ctx)
        test_3_subscribe_validation(ctx)
        test_4_unsubscribe_idempotent(ctx)
        test_5_cross_user_isolation(ctx)
        test_6_push_hook_dispatched(ctx)
    finally:
        n_notif, n_subs = cleanup_smoke_state()
        print(
            f"\n[cleanup] obrisano {n_notif} smoke notif redova "
            f"+ {n_subs} test pretplata"
        )

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
