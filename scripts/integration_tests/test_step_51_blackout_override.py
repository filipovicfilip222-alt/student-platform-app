"""End-to-end integration test za KORAK 2 Prompta 2 — Override notifikacije.

Run protiv žive ``docker compose --profile app up`` instance (host nginx :80,
override sa ``API_BASE``).

Pokriva 5 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_2_DEMO_READY.md
KORAK 2 + PRD §3.1):

  1. **Override cancel** — student ima APPROVED termin sutra, profesor
     kreira blackout za sutra → status appointment-a postaje CANCELLED,
     ``rejection_reason`` počinje sa "Profesor je rezervisao termin za
     drugu obavezu", in-app notif sa override-tekstom stiže studentu
     (poll-uje se /notifications za do 10s — Celery task radi async).
  2. **Idempotency** — drugi blackout za isti period: NEMA novog
     cancel-a (već je u CANCELLED), NEMA dodatne notifikacije
     (count_after == count_after_first).
  3. **Priority waitlist** — posle override cancel-a, student je u
     ``waitlist:priority:{professor_id}`` ZSET-i sa NEGATIVNIM score-om
     (verifikovano kroz docker exec ``ZRANGE ... WITHSCORES``).
  4. **Priority preliv pri novom slotu** — profesor kreira novi slot
     (POST /professors/slots sa redis dependency-jem) → priority
     student je u ``waitlist:{slot_id}`` ZSET sa istim negativnim
     score-om (PRVI kad waitlist offer task okine).
  5. **Drugi student bez blackout-a** — student koji NIJE bio u
     blackout periodu nije u priority listi (negativni control).

Cleanup po run-u: brišu se test appointment-i, slotovi, blackout-i,
priority ZSET-ovi i sve notif redove sa ``[I-51 SMOKE]`` prefiksom.
"""

from __future__ import annotations

import asyncio
import os
import random
import string
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
BACKEND_CONTAINER = os.getenv("BACKEND_CONTAINER", "studentska_backend")

PROFESOR_EMAIL = os.getenv("PROFESOR_EMAIL", "profesor1@fon.bg.ac.rs")
PROFESOR_PASSWORD = os.getenv("PROFESOR_PASSWORD", "Seed@2024!")

NOTIF_TITLE_PREFIX = "[I-51 SMOKE]"
SMOKE_TAG = "i51-blackout"


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


def delete(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.delete(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def login(email: str, password: str) -> tuple[str, str]:
    r = post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body["user"]["id"]


def register_student(suffix: str) -> tuple[str, str]:
    email = f"qa_p51_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA51",
            "last_name": f"P51-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


# ── Backend ergonomics ───────────────────────────────────────────────────────


def _docker_run_python(py: str, *, timeout: int = 30) -> tuple[int, str, str]:
    import subprocess

    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "-c", py]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return (
        proc.returncode,
        proc.stdout.decode(errors="replace").strip(),
        proc.stderr.decode(errors="replace").strip(),
    )


def get_professor_id_for_user(user_id: str) -> str:
    """Vrati Professor.id za User.id (PROFESOR rola)."""
    py = (
        "import asyncio\n"
        "from sqlalchemy import select\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.models.professor import Professor\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        f"        r = await db.execute(select(Professor.id).where(Professor.user_id == '{user_id}'))\n"
        "        v = r.scalar_one_or_none()\n"
        "        print(f'PROF_RESULT:{v if v else \"\"}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"get_professor_id failed: rc={rc} stderr={err}")
    for line in out.splitlines():
        if line.startswith("PROF_RESULT:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"PROF_RESULT not in output: {out}")


def create_approved_appointment(
    *,
    professor_id: str,
    student_id: str,
    slot_datetime_utc: str,
) -> tuple[str, str]:
    """Direktno INSERT slot + APPROVED appointment.

    Vraća (slot_id, appointment_id). Bypass-uje booking flow jer test
    fokus je na blackout override-u, ne na booking-u (covered drugim
    testom).

    NB: Frontend booking flow pravi PENDING; ovde direkno APPROVED da
    blackout query nađe ovaj termin (filter ``status == APPROVED``).
    """
    py = (
        "import asyncio, uuid\n"
        "from datetime import datetime\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.models.availability_slot import AvailabilitySlot\n"
        "from app.models.appointment import Appointment\n"
        "from app.models.enums import AppointmentStatus, ConsultationType, TopicCategory\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        "        slot = AvailabilitySlot(\n"
        f"            professor_id='{professor_id}',\n"
        f"            slot_datetime=datetime.fromisoformat('{slot_datetime_utc}'),\n"
        "            duration_minutes=30,\n"
        "            consultation_type=ConsultationType.UZIVO,\n"
        "            max_students=1,\n"
        "            is_available=True,\n"
        "        )\n"
        "        db.add(slot)\n"
        "        await db.flush()\n"
        "        appt = Appointment(\n"
        "            slot_id=slot.id,\n"
        f"            professor_id='{professor_id}',\n"
        f"            lead_student_id='{student_id}',\n"
        "            topic_category=TopicCategory.OSTALO,\n"
        f"            description='I-51 smoke termin {SMOKE_TAG}',\n"
        "            status=AppointmentStatus.APPROVED,\n"
        "            consultation_type=ConsultationType.UZIVO,\n"
        "        )\n"
        "        db.add(appt)\n"
        "        await db.flush()\n"
        "        await db.commit()\n"
        "        print(f'APPT_RESULT:{slot.id} {appt.id}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"create_appointment failed: rc={rc} stderr={err}")
    for line in out.splitlines():
        if line.startswith("APPT_RESULT:"):
            slot_id, appt_id = line.split(":", 1)[1].strip().split()
            return slot_id, appt_id
    raise RuntimeError(f"APPT_RESULT not in output: {out}")


def get_appointment_state(appt_id: str) -> tuple[str, str]:
    """Vrati (status, rejection_reason) za appointment."""
    py = (
        "import asyncio\n"
        "from sqlalchemy import select\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.models.appointment import Appointment\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        f"        r = await db.execute(select(Appointment.status, Appointment.rejection_reason).where(Appointment.id == '{appt_id}'))\n"
        "        row = r.first()\n"
        "        if row is None:\n"
        "            print('STATE_RESULT:NONE|')\n"
        "            return\n"
        "        st = row[0].value if row[0] is not None else 'NULL'\n"
        "        rr = (row[1] or '').replace('\\n', ' ')\n"
        "        print(f'STATE_RESULT:{st}|{rr}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"get_appointment_state failed: rc={rc} stderr={err}")
    for line in out.splitlines():
        if line.startswith("STATE_RESULT:"):
            payload = line.split(":", 1)[1]
            if "|" in payload:
                st, rr = payload.split("|", 1)
                return st, rr
    raise RuntimeError(f"STATE_RESULT not in output: {out}")


def get_priority_zset(professor_id: str) -> list[tuple[str, float]]:
    """ZRANGE waitlist:priority:{professor_id} 0 -1 WITHSCORES."""
    py = (
        "import asyncio\n"
        "from app.core.dependencies import get_redis\n"
        "async def main():\n"
        "    redis = await get_redis()\n"
        f"    raw = await redis.zrange('waitlist:priority:{professor_id}', 0, -1, withscores=True)\n"
        "    print(f'ZSET_RESULT:{len(raw)}')\n"
        "    for member, score in raw:\n"
        "        print(f'ZSET_MEMBER:{member} {score}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"get_priority_zset failed: rc={rc} stderr={err}")
    members: list[tuple[str, float]] = []
    for line in out.splitlines():
        if line.startswith("ZSET_MEMBER:"):
            payload = line.split(":", 1)[1].strip()
            uid, score_str = payload.rsplit(" ", 1)
            members.append((uid, float(score_str)))
    return members


def get_slot_zset(slot_id: str) -> list[tuple[str, float]]:
    """ZRANGE waitlist:{slot_id} 0 -1 WITHSCORES."""
    py = (
        "import asyncio\n"
        "from app.core.dependencies import get_redis\n"
        "async def main():\n"
        "    redis = await get_redis()\n"
        f"    raw = await redis.zrange('waitlist:{slot_id}', 0, -1, withscores=True)\n"
        "    print(f'ZSET_RESULT:{len(raw)}')\n"
        "    for member, score in raw:\n"
        "        print(f'ZSET_MEMBER:{member} {score}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"get_slot_zset failed: rc={rc} stderr={err}")
    members: list[tuple[str, float]] = []
    for line in out.splitlines():
        if line.startswith("ZSET_MEMBER:"):
            payload = line.split(":", 1)[1].strip()
            uid, score_str = payload.rsplit(" ", 1)
            members.append((uid, float(score_str)))
    return members


def cleanup_smoke(*, suffix: str, professor_id: str | None) -> None:
    """Briše sve I-51 smoke artefakte: appointmente, slotove, blackouts,
    notif redove (po naslovu), Redis priority ZSET, sve waitlist ZSET-ove
    pravljenih test slotova (jer mi nemamo direct hook — brišemo per
    professor)."""
    py = (
        "import asyncio\n"
        "from sqlalchemy import select, delete\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.core.dependencies import get_redis\n"
        "from app.models.appointment import Appointment\n"
        "from app.models.availability_slot import AvailabilitySlot, BlackoutDate\n"
        "from app.models.notification import Notification\n"
        "from app.services.notification_service import notif_unread_key\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        f"        appts = (await db.execute(select(Appointment.id, Appointment.lead_student_id, Appointment.slot_id).where(Appointment.description.like('%{SMOKE_TAG}%')))).all()\n"
        "        slot_ids = list({row[2] for row in appts})\n"
        "        student_ids = list({row[1] for row in appts})\n"
        f"        n_appt = (await db.execute(delete(Appointment).where(Appointment.description.like('%{SMOKE_TAG}%')))).rowcount\n"
        "        if slot_ids:\n"
        "            for sid in slot_ids:\n"
        "                await db.execute(delete(AvailabilitySlot).where(AvailabilitySlot.id == sid))\n"
        f"        n_blackout = (await db.execute(delete(BlackoutDate).where(BlackoutDate.reason.like('%{suffix}%')))).rowcount\n"
        f"        n_notif = (await db.execute(delete(Notification).where(Notification.title.like('%{NOTIF_TITLE_PREFIX}%')))).rowcount\n"
        "        notif_users = (await db.execute(select(Notification.user_id).where(Notification.user_id.in_(student_ids)))).scalars().all()\n"
        "        await db.commit()\n"
        "        redis = await get_redis()\n"
    )
    if professor_id:
        py += f"        await redis.delete('waitlist:priority:{professor_id}')\n"
    py += (
        "        for uid in set(student_ids + list(notif_users)):\n"
        "            await redis.delete(notif_unread_key(uid))\n"
        "        for sid in slot_ids:\n"
        "            await redis.delete(f'waitlist:{sid}')\n"
        "        print(f'CLEANUP_RESULT:{n_appt} {n_blackout} {n_notif}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py, timeout=60)
    if rc != 0:
        print(f"  [warn] cleanup failed: rc={rc} stderr={err}")
        return
    for line in out.splitlines():
        if line.startswith("CLEANUP_RESULT:"):
            print(f"  [cleanup] {line.split(':', 1)[1].strip()}")


def poll_for_notif(token: str, contains: str, timeout_s: float = 12.0) -> dict | None:
    """Poll-uj /notifications dok ne nađeš red sa title koji sadrži
    ``contains``. Celery task je async, treba do 5-10s."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        r = get("/notifications", token=token)
        if r.status_code == 200:
            try:
                payload = r.json()
                items = payload.get("items") if isinstance(payload, dict) else payload
                if isinstance(items, list):
                    for n in items:
                        if contains.lower() in (
                            (n.get("title") or "") + (n.get("body") or "")
                        ).lower():
                            return n
            except Exception:
                pass
        time.sleep(0.5)
    return None


# ── Tests ────────────────────────────────────────────────────────────────────


def test_1_blackout_override_cancels_appointment(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — blackout override → APPROVED postaje CANCELLED + override reason ===\n")

    # Sutra 12:00 UTC — appointment unutar blackout-a (sutra ceo dan).
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    slot_dt = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
    slot_id, appt_id = create_approved_appointment(
        professor_id=ctx["pro_prof_id"],
        student_id=ctx["s1_id"],
        slot_datetime_utc=slot_dt.isoformat(),
    )
    ctx["slot_id"] = slot_id
    ctx["appt_id"] = appt_id

    # Profesor kreira blackout sutra (1 dan).
    blackout_payload = {
        "start_date": tomorrow.date().isoformat(),
        "end_date": tomorrow.date().isoformat(),
        "reason": f"I-51 test blackout {ctx['suffix']}",
    }
    r_bl = post(
        "/professors/blackout",
        token=ctx["pro_token"],
        json=blackout_payload,
    )
    create_ok = r_bl.status_code == 201
    ctx["first_blackout_id"] = r_bl.json().get("id") if create_ok else None

    # Status appointmenta posle blackout-a.
    state, reason = get_appointment_state(appt_id)
    cancelled_ok = state == "CANCELLED"
    reason_ok = "Profesor je rezervisao termin za drugu obavezu" in reason

    record(
        "Blackout INSERT (POST /professors/blackout)",
        "201 Created",
        f"status={r_bl.status_code} body={r_bl.text[:200]}",
        create_ok,
    )
    record(
        "APPROVED termin u blackout periodu prebačen u CANCELLED + override reason",
        "status=CANCELLED, reason='Profesor je rezervisao termin...'",
        f"status={state} reason={reason[:80]}",
        cancelled_ok and reason_ok,
    )

    # In-app notif preko Celery taska (poll do 12s).
    notif = poll_for_notif(ctx["s1_token"], contains="otkazan", timeout_s=15.0)
    notif_ok = notif is not None and "override" in str(notif.get("data") or "").lower()
    record(
        "Override notif stiže studentu (in-app, async kroz Celery)",
        "notif sa title 'Termin je otkazan (override)' + data.override=true",
        f"found={notif is not None} title={(notif or {}).get('title', '')[:60]}",
        notif_ok,
    )


def test_2_idempotency(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — drugi blackout za isti period: NEMA dvostrukih cancel-a ===\n")

    if not ctx.get("first_blackout_id"):
        record("Idempotency", "first blackout ok", "first blackout missing", False)
        return

    # Snimi unread count pre 2. blackout-a.
    c_before = get("/notifications/unread-count", token=ctx["s1_token"])
    count_before = c_before.json().get("count", -1) if c_before.status_code == 200 else -1

    # Drugi blackout (isti period).
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    r_bl2 = post(
        "/professors/blackout",
        token=ctx["pro_token"],
        json={
            "start_date": tomorrow.date().isoformat(),
            "end_date": tomorrow.date().isoformat(),
            "reason": f"I-51 test blackout dup {ctx['suffix']}",
        },
    )
    second_create_ok = r_bl2.status_code == 201

    # Sačekaj 4s da Celery task ne bi slučajno stigao kasnije.
    time.sleep(4.0)

    c_after = get("/notifications/unread-count", token=ctx["s1_token"])
    count_after = c_after.json().get("count", -1) if c_after.status_code == 200 else -1

    state_after, _ = get_appointment_state(ctx["appt_id"])

    same_count = count_before == count_after
    still_cancelled = state_after == "CANCELLED"

    record(
        "Drugi blackout INSERT (idempotency check)",
        "201 Created (blackout reci se uvek smeju ponoviti)",
        f"status={r_bl2.status_code}",
        second_create_ok,
    )
    record(
        "Idempotency — drugi blackout NE okida dodatni cancel/notif",
        f"unread_count nepromenjen (before={count_before}, after=isto), "
        "appointment ostaje CANCELLED",
        f"count {count_before}→{count_after} status={state_after}",
        same_count and still_cancelled,
    )


def test_3_priority_waitlist_populated(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — priority waitlist ZSET populated sa override studentom ===\n")

    members = get_priority_zset(ctx["pro_prof_user_id"])  # by USER.id of profesora? NEEDS Professor.id
    # Ispravka: ZSET je keyed po Professor.id (ne User.id)
    members = get_priority_zset(ctx["pro_prof_id"])

    found = any(uid == ctx["s1_id"] for uid, _ in members)
    has_negative_score = any(uid == ctx["s1_id"] and score < 0 for uid, score in members)

    record(
        "Priority waitlist ZSET sadrži override studenta",
        f"member={ctx['s1_id']} prisutan u 'waitlist:priority:{ctx['pro_prof_id']}'",
        f"members={len(members)} contains_s1={found}",
        found,
    )
    record(
        "Priority score je NEGATIVAN (negativan = prioritet ispred regular waitlist-a)",
        "score < 0 (npr. -1738000000.0)",
        f"score(s1)={[s for u, s in members if u == ctx['s1_id']]}",
        has_negative_score,
    )


def test_4_new_slot_seeds_priority(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — novi slot pri/profesora preliva priority članove ===\n")

    # Profesor kreira novi slot za sledeći petak.
    next_week = datetime.now(timezone.utc) + timedelta(days=7)
    new_slot_dt = next_week.replace(hour=14, minute=0, second=0, microsecond=0)
    r_slot = post(
        "/professors/slots",
        token=ctx["pro_token"],
        json={
            "slot_datetime": new_slot_dt.isoformat(),
            "duration_minutes": 30,
            "consultation_type": "UZIVO",
            "max_students": 1,
        },
    )
    create_ok = r_slot.status_code == 201
    new_slot_id = ""
    if create_ok:
        body = r_slot.json()
        if isinstance(body, list) and body:
            new_slot_id = body[0].get("id", "")
        ctx["new_slot_id"] = new_slot_id

    # Verifikuj ZRANGE waitlist:{new_slot_id} 0 -1 WITHSCORES.
    members: list[tuple[str, float]] = []
    if new_slot_id:
        members = get_slot_zset(new_slot_id)
    found = any(uid == ctx["s1_id"] for uid, _ in members)
    has_negative_score = any(uid == ctx["s1_id"] and score < 0 for uid, score in members)

    record(
        "Novi slot kreiran (POST /professors/slots)",
        "201 Created sa redis hook-om za priority preliv",
        f"status={r_slot.status_code} slot_id={new_slot_id[:8]}…",
        create_ok and bool(new_slot_id),
    )
    record(
        "Priority student preliven u waitlist:{slot_id} ZSET sa NEGATIVNIM score-om",
        "ZRANGE asc → s1 prvi, score < 0",
        f"members={len(members)} contains_s1={found} negative_score={has_negative_score}",
        found and has_negative_score,
    )


def test_5_unaffected_student_not_in_priority(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — drugi student bez blackout cancel-a NIJE u priority listi ===\n")

    members = get_priority_zset(ctx["pro_prof_id"])
    s2_present = any(uid == ctx["s2_id"] for uid, _ in members)

    record(
        "Negativni control — s2 (nije imao termin u blackout periodu) NIJE u priority listi",
        "s2 NOT IN priority ZSET",
        f"members={[u for u, _ in members]} contains_s2={s2_present}",
        not s2_present,
    )


# ── Setup ────────────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix()

    pro_token, pro_user_id = login(PROFESOR_EMAIL, PROFESOR_PASSWORD)
    print(f"  logged in PROFESOR {PROFESOR_EMAIL} user_id={pro_user_id}")
    pro_prof_id = get_professor_id_for_user(pro_user_id)
    if not pro_prof_id:
        raise RuntimeError(
            f"Professor profile za {PROFESOR_EMAIL} ne postoji u bazi — "
            "pokrenite python scripts/seed_db.py prvo."
        )
    print(f"  PROFESOR Professor.id={pro_prof_id}")

    s1_email, _ = register_student(f"s1{suffix}")
    s2_email, _ = register_student(f"s2{suffix}")
    s1_token, s1_id = login(s1_email, "TestPass1!")
    s2_token, s2_id = login(s2_email, "TestPass1!")
    print(f"  registered s1 {s1_email} id={s1_id}")
    print(f"  registered s2 {s2_email} id={s2_id}")

    return {
        "suffix": suffix,
        "pro_token": pro_token,
        "pro_prof_id": pro_prof_id,
        "pro_prof_user_id": pro_user_id,
        "s1_token": s1_token,
        "s1_id": s1_id,
        "s2_token": s2_token,
        "s2_id": s2_id,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


async def amain() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    pro_id = None
    try:
        pro_id = ctx.get("pro_prof_id")
        test_1_blackout_override_cancels_appointment(ctx)
        test_2_idempotency(ctx)
        test_3_priority_waitlist_populated(ctx)
        test_4_new_slot_seeds_priority(ctx)
        test_5_unaffected_student_not_in_priority(ctx)
    finally:
        cleanup_smoke(suffix=ctx["suffix"], professor_id=pro_id)

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
