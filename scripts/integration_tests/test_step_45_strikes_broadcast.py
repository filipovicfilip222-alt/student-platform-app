"""End-to-end integration test za KORAK 7 (Faza 4.5) — Admin strikes + broadcast fan-out.

Run protiv žive ``docker compose -f infra/docker-compose.yml --profile app up``
instance na localhost-u (kroz nginx port 80; override sa ``API_BASE``).

Pokriva 7 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_1 §4.5 +
ROADMAP §4.5):

    1. RBAC — student NE sme GET /admin/strikes, POST /strikes/{id}/unblock,
       POST /admin/broadcast, GET /admin/broadcast → svi 403.
    2. GET /admin/strikes — vraća listu sa total_points >= 1, sortirano
       (aktivne blokade prve, pa total_points DESC). Studenti bez strike-a
       NE smeju biti u listi.
    3. POST /admin/strikes/{id}/unblock — happy path: blokada postavljena
       na now() (efektivno otključana), audit log STRIKE_UNBLOCKED dodaje
       1 red, BLOCK_LIFTED notif u DB-u stvorena Celery task-om.
    4. POST /admin/strikes/{id}/unblock — idempotent na ne-blokiranog
       studenta: 200 + MessageResponse "nije bio blokiran", BEZ audit log
       reda i BEZ notifikacije.
    5. POST /admin/broadcast (target=STAFF, channels=[IN_APP]) — 201 +
       BroadcastResponse shape, 1 broadcasts row sa target=STAFF i
       recipient_count=N (samo PROFESOR+ASISTENT useri), per-user BROADCAST
       notif kreiran za sve target-ovane (svi imaju role IN PROFESOR/ASISTENT,
       NEMA STUDENT/ADMIN), 1 audit log BROADCAST_SENT red.
    6. POST /admin/broadcast (target=BY_FACULTY, faculty=FON,
       channels=[IN_APP]) — 201, recipient_count odgovara samo FON useri-ma
       (NEMA ETF user-a u target-u). Resolve query striktno filtrira.
    7. POST /admin/broadcast (target=BY_FACULTY bez faculty) — 422
       (Pydantic model_validator). Prazan channels [] → 422.

Idempotent: TRUNCATE broadcasts + TRUNCATE audit_log + DELETE strike test
redovi u setup-u garantuje deterministički ispis brojeva (test 3 → 1
broadcast row, test 5 → 2 broadcast rows, test 6 → 3 broadcast rows).
Cleanup briše test rows prefikom ``s45_e2e_`` i resetuje audit + broadcasts.

Referenca:
    frontend/types/admin.ts (StrikeRow / UnblockRequest / BroadcastRequest /
    BroadcastResponse / BroadcastTarget / BroadcastChannel)
    backend/app/api/v1/admin.py (rute /admin/strikes, /admin/broadcast)
    CLAUDE.md §11 (forbidden) + §15 (audit log) + §17 (frontend tipovi)
"""

from __future__ import annotations

import os
import random
import string
import subprocess
import sys
import time
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

ADMIN_EMAIL = "sluzba@fon.bg.ac.rs"
ADMIN_PW = "Seed@2024!"

# Frontend ugovor (frontend/types/admin.ts).
STRIKE_KEYS = {
    "student_id",
    "student_full_name",
    "email",
    "faculty",
    "total_points",
    "blocked_until",
    "last_strike_at",
}
BROADCAST_KEYS = {
    "id",
    "title",
    "body",
    "target",
    "faculty",
    "channels",
    "sent_by",
    "sent_at",
    "recipient_count",
}


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


def get(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def login(email: str, password: str) -> tuple[str, dict]:
    r = post("/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"login {email} failed: {r.status_code} {r.text}")
    body = r.json()
    return body["access_token"], body["user"]


def register_student(suffix: str, faculty: str = "fon") -> tuple[str, str]:
    domain = "student.fon.bg.ac.rs" if faculty == "fon" else "student.etf.bg.ac.rs"
    email = f"s45_e2e_{suffix}@{domain}"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"S45-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


# ── Postgres helpers ──────────────────────────────────────────────────────────


def _psql(sql: str, timeout: int = 15) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
         "-tA", "-c", sql],
        capture_output=True, timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def truncate_audit_log_and_broadcasts() -> None:
    rc, _, err = _psql("TRUNCATE audit_log; TRUNCATE broadcasts;")
    if rc != 0:
        raise RuntimeError(f"TRUNCATE failed: {err}")


def cleanup_test_rows(prefix: str) -> None:
    sql = (
        "DELETE FROM strike_records WHERE student_id IN "
        "(SELECT id FROM users WHERE email LIKE '%{p}%'); "
        "DELETE FROM student_blocks WHERE student_id IN "
        "(SELECT id FROM users WHERE email LIKE '%{p}%'); "
        "DELETE FROM notifications WHERE user_id IN "
        "(SELECT id FROM users WHERE email LIKE '%{p}%'); "
        "DELETE FROM password_reset_tokens WHERE user_id IN "
        "(SELECT id FROM users WHERE email LIKE '%{p}%'); "
        "DELETE FROM users WHERE email LIKE '%{p}%';"
    ).format(p=prefix)
    _psql(sql, timeout=20)


def seed_strike_block(student_id: str, points: int, blocked_days: int) -> None:
    """Seed StrikeRecord (sa nasumičnim appointment FK) + StudentBlock.

    Trebamo postojeći appointment_id (FK RESTRICT). Uzimamo prvi iz
    appointments tabele.
    """
    rc, out, err = _psql("SELECT id FROM appointments LIMIT 1;")
    if rc != 0 or not out.strip():
        raise RuntimeError(f"no seed appointment available: {err}")
    appt_id = out.strip().split("\n")[0]

    sql = (
        f"INSERT INTO strike_records (student_id, appointment_id, points, reason) "
        f"VALUES ('{student_id}', '{appt_id}', {points}, 'NO_SHOW'); "
    )
    if blocked_days > 0:
        sql += (
            f"INSERT INTO student_blocks (student_id, blocked_until) "
            f"VALUES ('{student_id}', now() + interval '{blocked_days} days') "
            f"ON CONFLICT (student_id) DO UPDATE SET blocked_until=EXCLUDED.blocked_until;"
        )
    rc, _, err = _psql(sql)
    if rc != 0:
        raise RuntimeError(f"seed strike failed: {err}")


def count_rows(sql_where: str) -> int:
    rc, out, err = _psql(f"SELECT count(*) FROM {sql_where};")
    if rc != 0:
        return -1
    return int(out.strip() or "0")


def fetch_one(sql: str) -> str:
    rc, out, _ = _psql(sql)
    if rc != 0:
        return ""
    return out.strip()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_1_rbac_non_admin_forbidden(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — RBAC: student NE sme strikes/broadcast rute ===\n")
    token = ctx["student_a_token"]
    target_id = ctx["student_a_id"]

    r_strikes = get("/admin/strikes", token=token)
    r_unblock = post(f"/admin/strikes/{target_id}/unblock",
                     token=token,
                     json={"removal_reason": "RBAC test - blokirano student-u."})
    r_bc_post = post("/admin/broadcast",
                     token=token,
                     json={"title": "T", "body": "Body dovoljno dugacko.",
                           "target": "ALL", "channels": ["IN_APP"]})
    r_bc_get = get("/admin/broadcast", token=token)

    record(
        "Student → 403 na strikes/broadcast rutama",
        "GET /strikes=403 + POST /unblock=403 + POST /broadcast=403 + GET /broadcast=403",
        f"strikes={r_strikes.status_code} unblock={r_unblock.status_code} "
        f"bc_post={r_bc_post.status_code} bc_get={r_bc_get.status_code}",
        r_strikes.status_code == 403
        and r_unblock.status_code == 403
        and r_bc_post.status_code == 403
        and r_bc_get.status_code == 403,
    )


def test_2_strikes_listing(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — GET /admin/strikes: lista sa total_points >= 1 ===\n")
    # Seed: A=blokiran 14 dana sa 3 poena, B=preventivno 1 poen (ne blokiran).
    seed_strike_block(ctx["student_a_id"], points=3, blocked_days=14)
    seed_strike_block(ctx["student_b_id"], points=1, blocked_days=0)

    r = get("/admin/strikes", token=ctx["admin_token"])
    rows = r.json() if r.status_code == 200 else []

    a_in = any(row["student_id"] == ctx["student_a_id"] for row in rows)
    b_in = any(row["student_id"] == ctx["student_b_id"] for row in rows)
    c_not_in = all(row["student_id"] != ctx["student_c_id"] for row in rows)

    # Shape check (svaki row mora imati STRIKE_KEYS)
    shape_ok = all(set(row.keys()) == STRIKE_KEYS for row in rows) if rows else False

    # Sortiranje: A (blokiran) mora biti pre B (nije blokiran).
    a_idx = next((i for i, row in enumerate(rows) if row["student_id"] == ctx["student_a_id"]), -1)
    b_idx = next((i for i, row in enumerate(rows) if row["student_id"] == ctx["student_b_id"]), -1)
    sort_ok = 0 <= a_idx < b_idx

    # A mora imati blocked_until populated, B mora imati None.
    a_row = next((row for row in rows if row["student_id"] == ctx["student_a_id"]), None)
    b_row = next((row for row in rows if row["student_id"] == ctx["student_b_id"]), None)
    a_blocked_ok = a_row is not None and a_row["blocked_until"] is not None
    b_blocked_ok = b_row is not None and b_row["blocked_until"] is None
    a_points_ok = a_row is not None and a_row["total_points"] == 3
    b_points_ok = b_row is not None and b_row["total_points"] == 1

    record(
        "GET /strikes vraća A (blokiran) + B (preventivno), C odsutan, sortirano blokirani prvi, shape OK",
        "200 + A+B prisutni + C odsutan + shape STRIKE_KEYS + A pre B + A.blocked_until!=None + B.blocked_until==None",
        f"status={r.status_code} a_in={a_in} b_in={b_in} c_not_in={c_not_in} shape_ok={shape_ok} "
        f"sort(A_idx={a_idx} < B_idx={b_idx})={sort_ok} a_points={a_row and a_row['total_points']} "
        f"b_points={b_row and b_row['total_points']} a_blocked={a_blocked_ok} b_blocked_none={b_blocked_ok}",
        r.status_code == 200
        and a_in
        and b_in
        and c_not_in
        and shape_ok
        and sort_ok
        and a_blocked_ok
        and b_blocked_ok
        and a_points_ok
        and b_points_ok,
    )


def test_3_unblock_happy_path(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — Unblock happy path: 200 + audit STRIKE_UNBLOCKED + BLOCK_LIFTED notif ===\n")
    target_id = ctx["student_a_id"]
    reason = "Sistem je pogresno detektovao no-show — admin override."

    r = post(f"/admin/strikes/{target_id}/unblock",
             token=ctx["admin_token"],
             json={"removal_reason": reason})
    body = r.json() if r.status_code == 200 else {}
    msg_ok = "odblokiran" in body.get("message", "")

    # Provera DB: blocked_until <= now (efektivno otključano)
    blocked_check = fetch_one(
        f"SELECT (blocked_until <= now()) FROM student_blocks "
        f"WHERE student_id='{target_id}';"
    )
    blocked_lifted_ok = blocked_check == "t"

    # Audit log
    audit_count = count_rows(
        f"audit_log WHERE action='STRIKE_UNBLOCKED' "
        f"AND impersonated_user_id='{target_id}'"
    )
    audit_ok = audit_count == 1

    # BLOCK_LIFTED notif (Celery task, čekaj malo da se izvrši)
    time.sleep(2)
    notif_count = count_rows(
        f"notifications WHERE user_id='{target_id}' AND type='BLOCK_LIFTED'"
    )
    notif_ok = notif_count >= 1

    record(
        "Unblock happy: 200 + msg + DB blocked_until<=now + 1 audit STRIKE_UNBLOCKED + BLOCK_LIFTED notif",
        "200 + msg contains 'odblokiran' + blocked_until<=now + 1 audit row + >=1 BLOCK_LIFTED notif",
        f"status={r.status_code} msg_ok={msg_ok} blocked_lifted={blocked_lifted_ok} "
        f"audit_count={audit_count} notif_count={notif_count}",
        r.status_code == 200 and msg_ok and blocked_lifted_ok and audit_ok and notif_ok,
    )


def test_4_unblock_idempotent(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — Unblock idempotent: ne-blokiran student → 200 'nije bio blokiran' ===\n")
    target_id = ctx["student_c_id"]  # nikad nije bio blokiran
    reason = "Idempotent test - ne sme da pravi audit niti notif."

    audit_before = count_rows(
        f"audit_log WHERE action='STRIKE_UNBLOCKED' AND impersonated_user_id='{target_id}'"
    )
    notif_before = count_rows(
        f"notifications WHERE user_id='{target_id}' AND type='BLOCK_LIFTED'"
    )

    r = post(f"/admin/strikes/{target_id}/unblock",
             token=ctx["admin_token"],
             json={"removal_reason": reason})
    body = r.json() if r.status_code == 200 else {}
    msg_ok = "nije bio blokiran" in body.get("message", "")

    time.sleep(2)
    audit_after = count_rows(
        f"audit_log WHERE action='STRIKE_UNBLOCKED' AND impersonated_user_id='{target_id}'"
    )
    notif_after = count_rows(
        f"notifications WHERE user_id='{target_id}' AND type='BLOCK_LIFTED'"
    )

    record(
        "Unblock ne-blokiranog: 200 'nije bio blokiran' + 0 audit + 0 notif (no-op)",
        "status=200 + msg contains 'nije bio blokiran' + audit_diff=0 + notif_diff=0",
        f"status={r.status_code} msg_ok={msg_ok} audit_diff={audit_after - audit_before} "
        f"notif_diff={notif_after - notif_before}",
        r.status_code == 200
        and msg_ok
        and audit_after == audit_before
        and notif_after == notif_before,
    )


def test_5_broadcast_staff(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Broadcast STAFF: 201 + recipient_count=N (samo PROFESOR/ASISTENT) ===\n")

    # Očekivani recipient_count = svi aktivni PROFESOR + ASISTENT u DB-u
    expected_count = int(fetch_one(
        "SELECT count(*) FROM users WHERE is_active=true "
        "AND role IN ('PROFESOR', 'ASISTENT');"
    ) or "0")

    payload = {
        "title": "S45 Broadcast STAFF",
        "body": "Body za broadcast STAFF integration test scenario.",
        "target": "STAFF",
        "channels": ["IN_APP"],
    }
    r = post("/admin/broadcast", token=ctx["admin_token"], json=payload)
    body = r.json() if r.status_code == 201 else {}

    keys_ok = set(body.keys()) == BROADCAST_KEYS if body else False
    target_ok = body.get("target") == "STAFF"
    faculty_ok = body.get("faculty") is None
    sent_by_ok = body.get("sent_by") == ctx["admin_id"]
    count_ok = body.get("recipient_count") == expected_count
    bc_id = body.get("id", "")
    ctx["broadcast_staff_id"] = bc_id

    # Čekaj fan-out task pa proveri DB
    time.sleep(3)

    # DB row
    bc_row_ok = count_rows(
        f"broadcasts WHERE id='{bc_id}' AND target='STAFF' "
        f"AND recipient_count={expected_count}"
    ) == 1

    # Audit log BROADCAST_SENT
    audit_count = count_rows("audit_log WHERE action='BROADCAST_SENT'")
    audit_ok = audit_count == 1

    # BROADCAST notifs: svi target useri imaju BROADCAST notif sa ovim title-om
    notifs_for_staff_only = int(fetch_one(
        f"SELECT count(*) FROM notifications n JOIN users u ON u.id=n.user_id "
        f"WHERE n.type='BROADCAST' AND n.title='{payload['title']}' "
        f"AND u.role IN ('PROFESOR', 'ASISTENT');"
    ) or "0")
    no_notifs_for_students = int(fetch_one(
        f"SELECT count(*) FROM notifications n JOIN users u ON u.id=n.user_id "
        f"WHERE n.type='BROADCAST' AND n.title='{payload['title']}' "
        f"AND u.role='STUDENT';"
    ) or "0")
    no_notifs_for_admins = int(fetch_one(
        f"SELECT count(*) FROM notifications n JOIN users u ON u.id=n.user_id "
        f"WHERE n.type='BROADCAST' AND n.title='{payload['title']}' "
        f"AND u.role='ADMIN';"
    ) or "0")

    fan_out_ok = (
        notifs_for_staff_only == expected_count
        and no_notifs_for_students == 0
        and no_notifs_for_admins == 0
    )

    record(
        "Broadcast STAFF: 201 + shape + recipient_count=N PROFESOR+ASISTENT + DB row + audit + per-user BROADCAST notif (samo staff)",
        f"status=201 + BROADCAST_KEYS + target=STAFF + recipient_count={expected_count} "
        f"+ DB row + 1 audit + {expected_count} BROADCAST notifs (samo PROFESOR/ASISTENT)",
        f"status={r.status_code} keys_ok={keys_ok} target_ok={target_ok} faculty_ok={faculty_ok} "
        f"sent_by_ok={sent_by_ok} recipient_count={body.get('recipient_count')} "
        f"bc_row_ok={bc_row_ok} audit_count={audit_count} "
        f"staff_notifs={notifs_for_staff_only} student_notifs={no_notifs_for_students} "
        f"admin_notifs={no_notifs_for_admins}",
        r.status_code == 201
        and keys_ok
        and target_ok
        and faculty_ok
        and sent_by_ok
        and count_ok
        and bc_row_ok
        and audit_ok
        and fan_out_ok,
    )


def test_6_broadcast_by_faculty_fon(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — Broadcast BY_FACULTY=FON: samo FON useri (NEMA ETF) ===\n")

    expected_count = int(fetch_one(
        "SELECT count(*) FROM users WHERE is_active=true "
        "AND role != 'ADMIN' AND faculty='FON';"
    ) or "0")

    payload = {
        "title": "S45 Broadcast FON",
        "body": "Body za broadcast BY_FACULTY=FON test.",
        "target": "BY_FACULTY",
        "faculty": "FON",
        "channels": ["IN_APP"],
    }
    r = post("/admin/broadcast", token=ctx["admin_token"], json=payload)
    body = r.json() if r.status_code == 201 else {}

    target_ok = body.get("target") == "BY_FACULTY"
    faculty_ok = body.get("faculty") == "FON"
    count_ok = body.get("recipient_count") == expected_count

    time.sleep(3)

    notifs_fon = int(fetch_one(
        f"SELECT count(*) FROM notifications n JOIN users u ON u.id=n.user_id "
        f"WHERE n.type='BROADCAST' AND n.title='{payload['title']}' "
        f"AND u.faculty='FON';"
    ) or "0")
    notifs_etf = int(fetch_one(
        f"SELECT count(*) FROM notifications n JOIN users u ON u.id=n.user_id "
        f"WHERE n.type='BROADCAST' AND n.title='{payload['title']}' "
        f"AND u.faculty='ETF';"
    ) or "0")

    fan_out_ok = notifs_fon == expected_count and notifs_etf == 0

    record(
        "Broadcast BY_FACULTY=FON: 201 + recipient_count=FON_only + svi BROADCAST notifs FON, 0 ETF",
        f"status=201 + target=BY_FACULTY + faculty=FON + recipient_count={expected_count} + "
        f"{expected_count} FON notifs + 0 ETF notifs",
        f"status={r.status_code} target_ok={target_ok} faculty_ok={faculty_ok} "
        f"recipient_count={body.get('recipient_count')} (expected {expected_count}) "
        f"notifs_fon={notifs_fon} notifs_etf={notifs_etf}",
        r.status_code == 201
        and target_ok
        and faculty_ok
        and count_ok
        and fan_out_ok,
    )


def test_7_broadcast_validation_errors(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 7 — Broadcast 422: BY_FACULTY bez faculty + prazan channels ===\n")

    # Sluc 1: BY_FACULTY bez faculty → 422
    r1 = post("/admin/broadcast",
              token=ctx["admin_token"],
              json={"title": "x", "body": "Dovoljno dugacko telo broadcast-a.",
                    "target": "BY_FACULTY", "channels": ["IN_APP"]})

    # Sluc 2: prazan channels → 422
    r2 = post("/admin/broadcast",
              token=ctx["admin_token"],
              json={"title": "x", "body": "Dovoljno dugacko telo broadcast-a.",
                    "target": "ALL", "channels": []})

    # Sluc 3: nepoznat target (npr. "YEAR" ne postoji u Literal) → 422
    r3 = post("/admin/broadcast",
              token=ctx["admin_token"],
              json={"title": "x", "body": "Dovoljno dugacko telo broadcast-a.",
                    "target": "YEAR", "channels": ["IN_APP"]})

    record(
        "Validation: BY_FACULTY bez faculty=422 + prazan channels=422 + invalid target=422",
        "r1=422 + r2=422 + r3=422",
        f"by_faculty_no_fac={r1.status_code} empty_channels={r2.status_code} invalid_target={r3.status_code}",
        r1.status_code == 422 and r2.status_code == 422 and r3.status_code == 422,
    )


# ── Setup / Main ──────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    cleanup_test_rows("s45_e2e_")
    truncate_audit_log_and_broadcasts()
    print("  audit_log + broadcasts truncated, prior s45_e2e_ rows removed")

    suffix = rand_suffix()
    print(f"  suffix={suffix}")

    admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PW)
    print(f"  admin login OK ({admin_user['email']})")

    a_email, a_pw = register_student(suffix + "a", faculty="fon")
    b_email, _ = register_student(suffix + "b", faculty="fon")
    c_email, _ = register_student(suffix + "c", faculty="fon")

    a_token, a_user = login(a_email, a_pw)
    r_b = get("/admin/users", token=admin_token, params={"q": b_email}).json()
    r_c = get("/admin/users", token=admin_token, params={"q": c_email}).json()
    b_user = next(u for u in r_b if u["email"] == b_email)
    c_user = next(u for u in r_c if u["email"] == c_email)

    print(f"  student A id={a_user['id']} email={a_email}")
    print(f"  student B id={b_user['id']} email={b_email}")
    print(f"  student C id={c_user['id']} email={c_email}")

    return {
        "suffix": suffix,
        "admin_token": admin_token,
        "admin_id": admin_user["id"],
        "student_a_token": a_token,
        "student_a_id": a_user["id"],
        "student_b_id": b_user["id"],
        "student_c_id": c_user["id"],
    }


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    try:
        test_1_rbac_non_admin_forbidden(ctx)
        test_2_strikes_listing(ctx)
        test_3_unblock_happy_path(ctx)
        test_4_unblock_idempotent(ctx)
        test_5_broadcast_staff(ctx)
        test_6_broadcast_by_faculty_fon(ctx)
        test_7_broadcast_validation_errors(ctx)
    finally:
        cleanup_test_rows("s45_e2e_")
        truncate_audit_log_and_broadcasts()
        print("\n[cleanup] obrisani test studenti (s45_e2e_) + audit_log + broadcasts truncated")

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
