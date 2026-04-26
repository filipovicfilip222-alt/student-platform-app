"""End-to-end integration test za KORAK 8 (Faza 4.6) — Reminder Celery beat + cancel flows.

Run protiv žive ``docker compose -f infra/docker-compose.yml --profile app up``
instance na localhost-u (kroz nginx port 80; override sa ``API_BASE``).

Pokriva 7 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_1 §8 +
ROADMAP §4.6 + PRD §5.2):

    1. Termin u 24h prozoru → ``dispatch_reminders_24h`` šalje fan-out
       (lead student + profesor dobijaju ``APPOINTMENT_REMINDER_24H``).
    2. Termin van prozora (u 10h) → dispatcher ne dispečuje, BEZ notifa.
    3. Termin status=PENDING u 24h prozoru → SQL guard u dispatcher-u
       filtrira (samo ``status=APPROVED``), BEZ notifa.
    4. Idempotency: drugi run dispatcher-a za isti appointment iz testa 1
       → Redis ``SET NX EX`` vraća ``None``, dispatcher skipuje, BEZ
       dodatnih notif redova.
    5. Termin u 1h prozoru → ``dispatch_reminders_1h`` šalje fan-out
       sa ``APPOINTMENT_REMINDER_1H`` tipom (grananje hours_before≥24
       vs <24 u :func:`send_appointment_reminder`).
    6. Student otkaže APPROVED termin → ``send_appointment_cancelled``
       dispečovan iz ``booking_service.cancel_appointment``, profesor
       dobija ``APPOINTMENT_CANCELLED`` notif sa ``cancelled_by_role=STUDENT``,
       student NE dobija notif samog sebe (excluded set).
    7. Profesor otkaže APPROVED termin → isti task dispečovan iz
       ``professor_portal_service.cancel_request``, lead student dobija
       ``APPOINTMENT_CANCELLED`` sa ``cancelled_by_role=PROFESOR``.

Setup: 6 fresh appointment redova sa eksplicitnim UUID-evima, svaki
sa svojim availability_slot redom (marker ``online_link='S46_E2E_TEST_SLOT'``
za cleanup); profesor je seed-ovani ``profesor1@fon.bg.ac.rs``, student
je dinamički registrovan kroz ``/auth/register``.

Cleanup: briše appointmente, slot-ove (po marker-u), useri sa prefiksom
``s46_e2e_``, i eksplicitno briše Redis idempotency ključeve za test
appointment-e da naredni run počinje sa praznim Redis state-om.

Referenca:
    backend/app/tasks/reminder_tasks.py — dispatcher async helper
    backend/app/tasks/notifications.py — send_appointment_reminder
        + send_appointment_cancelled task signatures
    backend/app/services/booking_service.py linija 200ish — student cancel
    backend/app/services/professor_portal_service.py linija 240ish — prof cancel
    docs/PRD_Studentska_Platforma.md §5.2 (reminder + cancel matrice)
    docs/ROADMAP.md §4.6 (acceptance)
"""

from __future__ import annotations

import os
import random
import string
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
PG_CONTAINER = os.getenv("PG_CONTAINER", "studentska_postgres")
PG_USER = os.getenv("POSTGRES_USER", "studentska")
PG_DB = os.getenv("POSTGRES_DB", "studentska_platforma")
BACKEND_CONTAINER = os.getenv("BACKEND_CONTAINER", "studentska_backend")
REDIS_CONTAINER = os.getenv("REDIS_CONTAINER", "studentska_redis")
REDIS_PW = os.getenv("REDIS_PASSWORD", "redis_pass")

ADMIN_EMAIL = "sluzba@fon.bg.ac.rs"
ADMIN_PW = "Seed@2024!"
PROF_EMAIL = "profesor1@fon.bg.ac.rs"

# Marker da bi cleanup mogao da identifikuje test slot-ove bez tagovanja
# user-a (slot nema FK na user-a). Vidi cleanup_test_rows().
SLOT_MARKER = "S46_E2E_TEST_SLOT"

# Worker fan-out kašnjenje (dispatch + sub-task pickup + DB insert).
# 4s je dovoljno na lokalnom Docker-u; CI bi mogao tražiti više.
WORKER_WAIT_SEC = float(os.getenv("WORKER_WAIT_SEC", "4"))


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


def delete(path: str, *, token: str | None = None) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.delete(f"{API}{path}", headers=headers, timeout=30)


def login(email: str, password: str) -> tuple[str, dict]:
    r = post("/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"login {email} failed: {r.status_code} {r.text}")
    body = r.json()
    return body["access_token"], body["user"]


def register_student(suffix: str) -> tuple[str, str]:
    email = f"s46_e2e_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"S46-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


def impersonate(admin_token: str, target_user_id: str) -> str:
    r = post(f"/admin/impersonate/{target_user_id}", token=admin_token)
    if r.status_code != 200:
        raise RuntimeError(f"impersonate {target_user_id}: {r.status_code} {r.text}")
    return r.json()["access_token"]


# ── Postgres helpers ──────────────────────────────────────────────────────────


def _psql(sql: str, timeout: int = 15) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
         "-tA", "-c", sql],
        capture_output=True, timeout=timeout,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def fetch_one(sql: str) -> str:
    rc, out, _ = _psql(sql)
    if rc != 0:
        return ""
    return out.strip()


def count_notifs(appointment_id: str, notif_type: str) -> int:
    return int(
        fetch_one(
            f"SELECT count(*) FROM notifications "
            f"WHERE data->>'appointment_id' = '{appointment_id}' "
            f"AND type = '{notif_type}';"
        )
        or "0"
    )


def cleanup_test_rows() -> None:
    """Briše appointmente sa test slot-om, slot-ove sa marker-om i
    useri sa prefiksom ``s46_e2e_``. Bezbedno pokrenuti i pre i posle
    test run-a (idempotentno).
    """
    sql = (
        f"DELETE FROM appointment_participants WHERE appointment_id IN ("
        f"  SELECT a.id FROM appointments a "
        f"  JOIN availability_slots s ON s.id = a.slot_id "
        f"  WHERE s.online_link = '{SLOT_MARKER}'); "
        f"DELETE FROM strike_records WHERE appointment_id IN ("
        f"  SELECT a.id FROM appointments a "
        f"  JOIN availability_slots s ON s.id = a.slot_id "
        f"  WHERE s.online_link = '{SLOT_MARKER}'); "
        f"DELETE FROM notifications WHERE data->>'appointment_id' IN ("
        f"  SELECT a.id::text FROM appointments a "
        f"  JOIN availability_slots s ON s.id = a.slot_id "
        f"  WHERE s.online_link = '{SLOT_MARKER}'); "
        f"DELETE FROM appointments WHERE slot_id IN ("
        f"  SELECT id FROM availability_slots WHERE online_link = '{SLOT_MARKER}'); "
        f"DELETE FROM availability_slots WHERE online_link = '{SLOT_MARKER}'; "
        f"DELETE FROM notifications WHERE user_id IN ("
        f"  SELECT id FROM users WHERE email LIKE 's46_e2e_%'); "
        f"DELETE FROM password_reset_tokens WHERE user_id IN ("
        f"  SELECT id FROM users WHERE email LIKE 's46_e2e_%'); "
        f"DELETE FROM users WHERE email LIKE 's46_e2e_%';"
    )
    _psql(sql, timeout=20)


# ── Redis helpers ─────────────────────────────────────────────────────────────


def redis_del(key: str) -> None:
    subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "redis-cli",
         "-a", REDIS_PW, "--no-auth-warning", "DEL", key],
        capture_output=True, timeout=5,
    )


def cleanup_redis_keys(appointment_ids: list[str]) -> None:
    for aid in appointment_ids:
        redis_del(f"reminder:24:{aid}")
        redis_del(f"reminder:1:{aid}")


# ── Celery dispatcher trigger (kroz docker exec) ──────────────────────────────


def trigger_dispatch_24h() -> None:
    """Trigger ``reminder_tasks.dispatch_reminders_24h.delay()``.

    Async — task ide na broker, worker pickup-uje. Caller mora da
    sleep(WORKER_WAIT_SEC) pre nego što čita DB rezultat (sub-task
    ``send_appointment_reminder`` se trigger-uje IZ dispatcher-a, pa
    mu treba još jedan worker hop).
    """
    proc = subprocess.run(
        ["docker", "exec", BACKEND_CONTAINER, "python", "-c",
         "from app.tasks.reminder_tasks import dispatch_reminders_24h; "
         "dispatch_reminders_24h.delay()"],
        capture_output=True, timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"dispatch_24h trigger failed: {proc.stderr.decode('utf-8', 'replace')}"
        )


def trigger_dispatch_1h() -> None:
    proc = subprocess.run(
        ["docker", "exec", BACKEND_CONTAINER, "python", "-c",
         "from app.tasks.reminder_tasks import dispatch_reminders_1h; "
         "dispatch_reminders_1h.delay()"],
        capture_output=True, timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"dispatch_1h trigger failed: {proc.stderr.decode('utf-8', 'replace')}"
        )


# ── Seed appointment helper ───────────────────────────────────────────────────


def seed_appointment(
    student_id: str,
    professor_id: str,
    slot_id: str,
    appt_id: str,
    *,
    minutes_until_slot: int,
    status: str,
) -> None:
    """Insertuj jedan slot + appointment red sa ``online_link='S46_E2E_TEST_SLOT'``
    marker-om. Sve što treba je status (APPROVED/PENDING) i offset slot
    vremena u minutama od trenutka.
    """
    sql = (
        f"INSERT INTO availability_slots "
        f"(id, professor_id, slot_datetime, duration_minutes, consultation_type, "
        f" max_students, online_link, is_available) VALUES ("
        f"'{slot_id}', '{professor_id}', "
        f"NOW() + INTERVAL '{minutes_until_slot} minutes', "
        f"30, 'UZIVO', 1, '{SLOT_MARKER}', false); "
        f"INSERT INTO appointments "
        f"(id, slot_id, professor_id, lead_student_id, topic_category, "
        f" description, status, consultation_type) VALUES ("
        f"'{appt_id}', '{slot_id}', '{professor_id}', '{student_id}', "
        f"'ISPIT', 'S46 e2e seed', '{status}', 'UZIVO');"
    )
    rc, _, err = _psql(sql)
    if rc != 0:
        raise RuntimeError(f"seed_appointment failed: {err}")


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_1_2_3_dispatch_24h_first_run(ctx: dict[str, Any]) -> None:
    print("\n=== TESTS 1+2+3 — dispatch_24h scan: in-window APPROVED → fan-out, "
          "out-of-window → skip, PENDING → skip ===\n")

    # Pre-state: očisti reminder Redis ključeve da prvi run sigurno
    # acquire-uje SET NX lock.
    cleanup_redis_keys([ctx["appt_in_24h"], ctx["appt_out_window"], ctx["appt_pending"]])

    trigger_dispatch_24h()
    time.sleep(WORKER_WAIT_SEC)

    # TEST 1 — appt_in_24h: lead + profesor su dobili REMINDER_24H notif (2 reda)
    in_window_count = count_notifs(ctx["appt_in_24h"], "APPOINTMENT_REMINDER_24H")
    record(
        "TEST 1 — Termin u 24h prozoru: 2 REMINDER_24H notifs (lead + profesor)",
        "count=2",
        f"count={in_window_count}",
        in_window_count == 2,
    )

    # TEST 2 — appt_out_window (slot @ now+10h): dispatcher SQL filter ga ne
    # vraća jer je slot_datetime van [now+23.5h, now+24.5h] prozora.
    out_window_count = count_notifs(ctx["appt_out_window"], "APPOINTMENT_REMINDER_24H")
    record(
        "TEST 2 — Termin van prozora (now+10h): 0 REMINDER_24H notifs",
        "count=0",
        f"count={out_window_count}",
        out_window_count == 0,
    )

    # TEST 3 — appt_pending (slot @ now+24h, ali status=PENDING): dispatcher
    # SQL filter zahteva status=APPROVED → ne vraća red, fan-out nema mesta.
    pending_count = count_notifs(ctx["appt_pending"], "APPOINTMENT_REMINDER_24H")
    record(
        "TEST 3 — Termin status=PENDING u 24h prozoru: 0 REMINDER_24H notifs (status guard)",
        "count=0",
        f"count={pending_count}",
        pending_count == 0,
    )


def test_4_idempotency_second_dispatch(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — Idempotency: drugi dispatch_24h run → Redis SET NX skip, "
          "BEZ dodatnih notif redova ===\n")

    pre_count = count_notifs(ctx["appt_in_24h"], "APPOINTMENT_REMINDER_24H")

    # NE brišemo Redis ključeve — TEST 1 ih je upravo set-ovao. Drugi
    # dispatch_24h mora videti ``set(... nx=True)`` → None i skip.
    trigger_dispatch_24h()
    time.sleep(WORKER_WAIT_SEC)

    post_count = count_notifs(ctx["appt_in_24h"], "APPOINTMENT_REMINDER_24H")
    delta = post_count - pre_count

    record(
        "TEST 4 — Drugi dispatch isti broj notif redova (idempotency hit)",
        f"pre=2 post=2 delta=0 (Redis SET NX vraća None drugi put)",
        f"pre={pre_count} post={post_count} delta={delta}",
        delta == 0 and post_count == 2,
    )


def test_5_dispatch_1h(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — dispatch_1h: termin u [now+45m, now+1h15m] → "
          "REMINDER_1H type fan-out ===\n")

    cleanup_redis_keys([ctx["appt_in_1h"]])

    trigger_dispatch_1h()
    time.sleep(WORKER_WAIT_SEC)

    one_h_count = count_notifs(ctx["appt_in_1h"], "APPOINTMENT_REMINDER_1H")
    # data.hours_before mora biti tačno "1" (string posle JSONB extract-a).
    hb_value = fetch_one(
        f"SELECT DISTINCT data->>'hours_before' FROM notifications "
        f"WHERE data->>'appointment_id' = '{ctx['appt_in_1h']}' "
        f"AND type = 'APPOINTMENT_REMINDER_1H';"
    )

    record(
        "TEST 5 — Termin u 1h prozoru: 2 REMINDER_1H notifs sa data.hours_before=1",
        "count=2 + hours_before='1'",
        f"count={one_h_count} hours_before={hb_value!r}",
        one_h_count == 2 and hb_value == "1",
    )


def test_6_student_cancel(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — Student otkaže APPROVED termin → "
          "send_appointment_cancelled, profesor dobija notif (lead excluded) ===\n")

    appt_id = ctx["appt_student_cancel"]
    student_token = ctx["student_imp_token"]

    r = delete(f"/students/appointments/{appt_id}", token=student_token)
    delete_status = r.status_code

    # Worker pickup + DB insert delay.
    time.sleep(WORKER_WAIT_SEC)

    # Profesor (prof_user_id) treba da ima APPOINTMENT_CANCELLED notif sa
    # data.cancelled_by_role=STUDENT. Lead student NE sme da ima notif sa
    # ovim appointment-ID (excluded set u send_appointment_cancelled task-u).
    prof_count = int(fetch_one(
        f"SELECT count(*) FROM notifications "
        f"WHERE user_id = '{ctx['prof_user_id']}' "
        f"AND data->>'appointment_id' = '{appt_id}' "
        f"AND type = 'APPOINTMENT_CANCELLED' "
        f"AND data->>'cancelled_by_role' = 'STUDENT';"
    ) or "0")
    student_count = int(fetch_one(
        f"SELECT count(*) FROM notifications "
        f"WHERE user_id = '{ctx['student_id']}' "
        f"AND data->>'appointment_id' = '{appt_id}' "
        f"AND type = 'APPOINTMENT_CANCELLED';"
    ) or "0")
    # DB status mora biti CANCELLED.
    db_status = fetch_one(f"SELECT status FROM appointments WHERE id='{appt_id}';")

    record(
        "TEST 6 — Student cancel: HTTP 200, profesor 1 CANCELLED notif, lead 0 (excluded), "
        "appointment.status=CANCELLED",
        "delete=200 + prof_count=1 + student_count=0 + db=CANCELLED",
        f"delete={delete_status} prof_count={prof_count} student_count={student_count} "
        f"db={db_status}",
        delete_status == 200
        and prof_count == 1
        and student_count == 0
        and db_status == "CANCELLED",
    )


def test_7_professor_cancel(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 7 — Profesor otkaže APPROVED termin → "
          "send_appointment_cancelled, student dobija notif (profesor excluded) ===\n")

    appt_id = ctx["appt_prof_cancel"]
    prof_token = ctx["prof_imp_token"]

    r = post(
        f"/professors/requests/{appt_id}/cancel",
        token=prof_token,
        json={"reason": "Bolovanje — S46 e2e test."},
    )
    cancel_status = r.status_code

    time.sleep(WORKER_WAIT_SEC)

    # Lead student (student_id) treba da ima APPOINTMENT_CANCELLED notif sa
    # data.cancelled_by_role=PROFESOR. Profesor (prof_user_id) NE sme.
    student_count = int(fetch_one(
        f"SELECT count(*) FROM notifications "
        f"WHERE user_id = '{ctx['student_id']}' "
        f"AND data->>'appointment_id' = '{appt_id}' "
        f"AND type = 'APPOINTMENT_CANCELLED' "
        f"AND data->>'cancelled_by_role' = 'PROFESOR';"
    ) or "0")
    prof_count = int(fetch_one(
        f"SELECT count(*) FROM notifications "
        f"WHERE user_id = '{ctx['prof_user_id']}' "
        f"AND data->>'appointment_id' = '{appt_id}' "
        f"AND type = 'APPOINTMENT_CANCELLED';"
    ) or "0")
    # rejection_reason mora biti popunjen u DB-u.
    db_reason = fetch_one(
        f"SELECT rejection_reason FROM appointments WHERE id='{appt_id}';"
    )

    record(
        "TEST 7 — Profesor cancel: HTTP 200, student 1 CANCELLED notif, profesor 0 (excluded), "
        "rejection_reason zapisan",
        "cancel=200 + student_count=1 + prof_count=0 + reason!=''",
        f"cancel={cancel_status} student_count={student_count} prof_count={prof_count} "
        f"reason={db_reason!r}",
        cancel_status == 200
        and student_count == 1
        and prof_count == 0
        and db_reason.startswith("Bolovanje"),
    )


# ── Setup / Main ──────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    cleanup_test_rows()
    print(f"  prior s46_e2e_ rows + slots sa marker-om '{SLOT_MARKER}' obrisani")

    suffix = rand_suffix()
    print(f"  suffix={suffix}")

    admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PW)
    print(f"  admin login OK ({admin_user['email']})")

    student_email, student_pw = register_student(suffix)
    student_token, student_user = login(student_email, student_pw)
    student_id = student_user["id"]
    print(f"  student id={student_id} email={student_email}")

    # Resolve professor user_id + professor.id (FK iz appointments).
    prof_user_id = fetch_one(f"SELECT id FROM users WHERE email='{PROF_EMAIL}';")
    prof_id = fetch_one(f"SELECT id FROM professors WHERE user_id='{prof_user_id}';")
    if not prof_user_id or not prof_id:
        raise RuntimeError(
            f"professor seed missing: {PROF_EMAIL} (run scripts/seed_db.py first)"
        )
    print(f"  professor user_id={prof_user_id} prof_id={prof_id}")

    # Impersonation tokens (admin → student / profesor) — student samog
    # sebe može autentikovati password-om, ali profesor ne (seed password
    # je promenjen ili nije lokalno poznat). Student impersonation token
    # je važeći za DELETE /students/appointments/{id}.
    student_imp_token = impersonate(admin_token, student_id)
    prof_imp_token = impersonate(admin_token, prof_user_id)
    print("  impersonation tokens issued (student + profesor)")

    # 6 appointment-ova sa eksplicitnim UUID-evima:
    #   appt_in_24h        — slot @ now+24h, APPROVED → REMINDER_24H test 1, 4
    #   appt_out_window    — slot @ now+10h, APPROVED → test 2 (van prozora)
    #   appt_pending       — slot @ now+24h, PENDING  → test 3 (status guard)
    #   appt_in_1h         — slot @ now+1h,  APPROVED → REMINDER_1H test 5
    #   appt_student_cancel— slot @ now+48h, APPROVED → test 6 student cancel
    #   appt_prof_cancel   — slot @ now+48h, APPROVED → test 7 prof cancel
    appt_in_24h = str(uuid.uuid4())
    appt_out_window = str(uuid.uuid4())
    appt_pending = str(uuid.uuid4())
    appt_in_1h = str(uuid.uuid4())
    appt_student_cancel = str(uuid.uuid4())
    appt_prof_cancel = str(uuid.uuid4())

    # 6 distinct slot UUIDs (FK-evi iz appointment-a su 1:1).
    slot_in_24h = str(uuid.uuid4())
    slot_out_window = str(uuid.uuid4())
    slot_pending = str(uuid.uuid4())
    slot_in_1h = str(uuid.uuid4())
    slot_student_cancel = str(uuid.uuid4())
    slot_prof_cancel = str(uuid.uuid4())

    seed_appointment(student_id, prof_id, slot_in_24h, appt_in_24h,
                     minutes_until_slot=24 * 60, status="APPROVED")
    seed_appointment(student_id, prof_id, slot_out_window, appt_out_window,
                     minutes_until_slot=10 * 60, status="APPROVED")
    seed_appointment(student_id, prof_id, slot_pending, appt_pending,
                     minutes_until_slot=24 * 60, status="PENDING")
    seed_appointment(student_id, prof_id, slot_in_1h, appt_in_1h,
                     minutes_until_slot=60, status="APPROVED")
    seed_appointment(student_id, prof_id, slot_student_cancel, appt_student_cancel,
                     minutes_until_slot=48 * 60, status="APPROVED")
    seed_appointment(student_id, prof_id, slot_prof_cancel, appt_prof_cancel,
                     minutes_until_slot=48 * 60, status="APPROVED")

    print("  6 appointmenata seeded (in_24h, out_window, pending, in_1h, "
          "student_cancel, prof_cancel)")

    # Eksplicitan cleanup Redis idempotency ključeva za sve test appoint-
    # mente (paranoia — TRUNCATE neće ovo počistiti).
    cleanup_redis_keys([
        appt_in_24h, appt_out_window, appt_pending, appt_in_1h,
        appt_student_cancel, appt_prof_cancel,
    ])

    return {
        "suffix": suffix,
        "admin_token": admin_token,
        "student_token": student_token,
        "student_imp_token": student_imp_token,
        "prof_imp_token": prof_imp_token,
        "student_id": student_id,
        "prof_user_id": prof_user_id,
        "prof_id": prof_id,
        "appt_in_24h": appt_in_24h,
        "appt_out_window": appt_out_window,
        "appt_pending": appt_pending,
        "appt_in_1h": appt_in_1h,
        "appt_student_cancel": appt_student_cancel,
        "appt_prof_cancel": appt_prof_cancel,
    }


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    try:
        test_1_2_3_dispatch_24h_first_run(ctx)
        test_4_idempotency_second_dispatch(ctx)
        test_5_dispatch_1h(ctx)
        test_6_student_cancel(ctx)
        test_7_professor_cancel(ctx)
    finally:
        cleanup_redis_keys([
            ctx["appt_in_24h"], ctx["appt_out_window"], ctx["appt_pending"],
            ctx["appt_in_1h"], ctx["appt_student_cancel"], ctx["appt_prof_cancel"],
        ])
        cleanup_test_rows()
        print("\n[cleanup] obrisani test slotovi (marker), appointmenti, useri "
              "(s46_e2e_), Redis reminder ključevi")

    print("\n=== SUMMARY ===\n")
    width = max(len(r.name) for r in RESULTS) if RESULTS else 0
    for r in RESULTS:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name:<{width}}")
    failed = sum(1 for r in RESULTS if not r.passed)
    print(f"\n  {len(RESULTS) - failed}/{len(RESULTS)} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
