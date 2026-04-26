"""End-to-end integration test za KORAK 6 (Faza 4.4) — Impersonation + Audit log.

Run protiv žive ``docker compose --profile app up`` instance na localhost-u
(kroz nginx port 80; override sa ``API_BASE``).

Pokriva 8 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_1 §4.4 +
ROADMAP §4.4 + user prompt I-5):

    1. RBAC — non-admin POST /admin/impersonate/{id} → 403, GET /admin/audit-log → 403.
    2. Happy path — admin → impersonira studenta → 200 + ImpersonationStartResponse
       shape + JWT claims (sub=student, imp=true, imp_email=admin, exp ~ 30min)
       + 1 audit row IMPERSONATION_START.
    3. End — POST /admin/impersonate/end sa imp tokenom → 200 + svež admin
       token (sub=admin, bez imp claim-a) + audit row IMPERSONATION_END.
    4. Re-impersonate (A → B bez Izađi) — admin u imp na A klikne impersonate na B
       (frontend pošalje original admin token iz useImpersonationStore.originalUser).
       Backend auto-zatvori sesiju za A (END entry) pa otvori START za B u istoj
       transakciji. Audit log: 4 reda (test 2 START + test 3 END + auto END + B START).
    5. Validation — admin ne sme da impersonira sam sebe (400), drugog admina (400),
       deaktiviranog korisnika (400), nepostojećeg user-a (404).
    6. IP capture — audit row ima validan IPv4 string iz X-Real-IP / XFF
       (nginx prosleđuje sa ``infra/nginx/nginx.conf``).
    7. Audit log filteri — admin_id, action, from_date/to_date isključuju neusklađene
       redove (exact match na action, ne ILIKE).
    8. Token expiration — istekao imp token vraća 401, NE auto-refresh-uje
       (impersonation NIJE u refresh rotaciji per CLAUDE.md §14).

Idempotent: TRUNCATE audit_log u setup-u garantuje deterministički ispis brojeva
(test 2 → 1 row, test 3 → 2 rows, test 4 → 4 rows). Cleanup briše test rows
prefikom ``imp_e2e_``.

Referenca:
    docs/websocket-schema.md §6 (impersonation transport contract)
    CLAUDE.md §14 (TTL=30min, no refresh) + §15 (audit log obavezan + IP)
    CURRENT_STATE2 §6.17 (frontend tipovi zaključani; backend prati ugovor)
"""

from __future__ import annotations

import base64
import json
import os
import random
import re
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

# Force UTF-8 ispis za Windows cp1252 konzole.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
BACKEND_CONTAINER = os.getenv("BACKEND_CONTAINER", "studentska_backend")
PG_CONTAINER = os.getenv("PG_CONTAINER", "studentska_postgres")
PG_USER = os.getenv("POSTGRES_USER", "studentska")
PG_DB = os.getenv("POSTGRES_DB", "studentska_platforma")

ADMIN_EMAIL = "sluzba@fon.bg.ac.rs"
ADMIN_PW = "Seed@2024!"

# Frontend ugovor (frontend/types/admin.ts::ImpersonationStartResponse).
START_KEYS = {
    "access_token",
    "token_type",
    "expires_in",
    "user",
    "impersonator",
    "imp_expires_at",
}
END_KEYS = {"access_token", "token_type", "expires_in", "user"}
AUDIT_KEYS = {
    "id",
    "admin_id",
    "admin_full_name",
    "impersonated_user_id",
    "impersonated_user_full_name",
    "action",
    "ip_address",
    "created_at",
}
USER_KEYS = {
    "id",
    "email",
    "first_name",
    "last_name",
    "role",
    "faculty",
    "is_active",
    "is_verified",
    "profile_image_url",
    "created_at",
}
IMPERSONATOR_KEYS = {"id", "email", "first_name", "last_name"}


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


def register_student(suffix: str) -> tuple[str, str]:
    email = f"imp_e2e_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"IMP-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Unsafe decode (bez signature verify) — samo za inspekciju claim-ova."""
    body = token.split(".")[1]
    pad = "=" * (-len(body) % 4)
    return json.loads(base64.urlsafe_b64decode(body + pad))


# ── Postgres helpers ──────────────────────────────────────────────────────────


def truncate_audit_log() -> None:
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
         "-c", "TRUNCATE audit_log;"],
        capture_output=True, timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"TRUNCATE audit_log failed: {proc.stderr.decode('utf-8','replace')}"
        )


def deactivate_user_in_db(email: str) -> None:
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
         "-c", f"UPDATE users SET is_active=false WHERE email='{email}';"],
        capture_output=True, timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"deactivate {email} failed: {proc.stderr.decode('utf-8','replace')}"
        )


def cleanup_test_rows(prefix: str) -> int:
    sql = (
        "DELETE FROM password_reset_tokens "
        "WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%{p}%'); "
        "DELETE FROM users WHERE email LIKE '%{p}%';"
    ).format(p=prefix)
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB,
         "-c", sql],
        capture_output=True, timeout=15,
    )
    return proc.returncode


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_1_rbac_non_admin_forbidden(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — RBAC: student NE sme impersonate ni audit-log ===\n")
    target_id = ctx["student_a_id"]

    r_imp = post(f"/admin/impersonate/{target_id}", token=ctx["student_a_token"])
    r_log = get("/admin/audit-log", token=ctx["student_a_token"])
    r_end = post("/admin/impersonate/end", token=ctx["student_a_token"])

    record(
        "Student → 403 na sve 3 impersonation rute",
        "imp=403 + audit-log=403 + end=403",
        f"imp={r_imp.status_code} audit-log={r_log.status_code} end={r_end.status_code}",
        r_imp.status_code == 403
        and r_log.status_code == 403
        and r_end.status_code == 403,
    )


def test_2_happy_path_start(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — Happy path: admin impersonira student A ===\n")
    target_id = ctx["student_a_id"]
    target_email = ctx["student_a_email"]

    r = post(f"/admin/impersonate/{target_id}", token=ctx["admin_token"])
    body = r.json() if r.status_code == 200 else {}

    keys_match = set(body.keys()) == START_KEYS
    user_keys_match = set(body.get("user", {}).keys()) == USER_KEYS if body else False
    imp_keys_match = (
        set(body.get("impersonator", {}).keys()) == IMPERSONATOR_KEYS if body else False
    )
    expires_in_ok = body.get("expires_in") == 1800
    target_email_ok = body.get("user", {}).get("email") == target_email
    impersonator_email_ok = (
        body.get("impersonator", {}).get("email") == ADMIN_EMAIL
    )

    # Decode claims
    claims = decode_jwt_payload(body["access_token"]) if body else {}
    sub_ok = claims.get("sub") == target_id
    imp_ok = claims.get("imp") is True
    imp_email_ok = claims.get("imp_email") == ADMIN_EMAIL
    imp_name_ok = claims.get("imp_name") == "Studentska Služba FON"
    role_ok = claims.get("role") == "STUDENT"

    if "exp" in claims:
        ttl_min = (claims["exp"] - int(datetime.now(timezone.utc).timestamp())) / 60
        ttl_ok = 29.0 <= ttl_min <= 30.5
    else:
        ttl_min = -1
        ttl_ok = False

    # Audit row (čitamo sa admin tokenom)
    r_log = get("/admin/audit-log", token=ctx["admin_token"])
    log = r_log.json() if r_log.status_code == 200 else []
    audit_ok = (
        len(log) == 1
        and log[0]["action"] == "IMPERSONATION_START"
        and log[0]["impersonated_user_id"] == target_id
        and log[0]["admin_id"] == ctx["admin_id"]
        and set(log[0].keys()) == AUDIT_KEYS
    )

    # Save imp token za naredne testove
    ctx["imp_token_a"] = body.get("access_token", "")

    record(
        "Start: 200 + shape + JWT claims (sub/imp/imp_email/imp_name) + TTL ~30min + 1 audit START row",
        "200 + START_KEYS == response keys + sub=student.id + imp=True + "
        f"imp_email={ADMIN_EMAIL} + imp_name='Studentska Služba FON' + role=STUDENT + "
        "TTL 29-30.5min + 1 audit row IMPERSONATION_START",
        f"status={r.status_code} keys_match={keys_match} user_keys={user_keys_match} "
        f"imp_keys={imp_keys_match} expires_in={body.get('expires_in')} "
        f"sub_ok={sub_ok} imp={claims.get('imp')} imp_email_ok={imp_email_ok} "
        f"imp_name_ok={imp_name_ok} role={claims.get('role')} ttl_min={ttl_min:.1f} "
        f"audit_rows={len(log)} audit_ok={audit_ok}",
        r.status_code == 200
        and keys_match
        and user_keys_match
        and imp_keys_match
        and expires_in_ok
        and target_email_ok
        and impersonator_email_ok
        and sub_ok
        and imp_ok
        and imp_email_ok
        and imp_name_ok
        and role_ok
        and ttl_ok
        and audit_ok,
    )


def test_3_end_returns_admin_token(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — End: imp token → svež admin token (bez imp claim-a) ===\n")
    r = post("/admin/impersonate/end", token=ctx["imp_token_a"])
    body = r.json() if r.status_code == 200 else {}

    keys_match = set(body.keys()) == END_KEYS
    user_keys_match = set(body.get("user", {}).keys()) == USER_KEYS if body else False
    user_email_ok = body.get("user", {}).get("email") == ADMIN_EMAIL

    claims = decode_jwt_payload(body["access_token"]) if body else {}
    sub_ok = claims.get("sub") == ctx["admin_id"]
    no_imp_claim = "imp" not in claims
    role_ok = claims.get("role") == "ADMIN"

    r_log = get("/admin/audit-log", token=ctx["admin_token"])
    log = r_log.json() if r_log.status_code == 200 else []
    end_rows = [r for r in log if r["action"] == "IMPERSONATION_END"]
    end_ok = (
        len(log) == 2
        and len(end_rows) == 1
        and end_rows[0]["impersonated_user_id"] == ctx["student_a_id"]
        and end_rows[0]["admin_id"] == ctx["admin_id"]
    )

    record(
        "End: 200 + admin token bez imp claim-a + 1 nov audit END row",
        "200 + END_KEYS == response keys + sub=admin + 'imp' not in claims + "
        "role=ADMIN + audit_log == 2 reda (1 START + 1 END za istog target-a)",
        f"status={r.status_code} keys_match={keys_match} user_email_ok={user_email_ok} "
        f"sub_ok={sub_ok} no_imp_claim={no_imp_claim} role={claims.get('role')} "
        f"audit_total={len(log)} end_count={len(end_rows)} end_ok={end_ok}",
        r.status_code == 200
        and keys_match
        and user_keys_match
        and user_email_ok
        and sub_ok
        and no_imp_claim
        and role_ok
        and end_ok,
    )


def test_4_reimpersonate_a_to_b(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — Re-impersonate: admin u imp(A) → impersonira B (auto END+START) ===\n")
    # Korak 1: admin impersonira A (svež start nakon test 3 koji je već zatvorio)
    r1 = post(
        f"/admin/impersonate/{ctx['student_a_id']}", token=ctx["admin_token"]
    )
    if r1.status_code != 200:
        record(
            "Re-impersonate prep (start A) bi trebalo 200",
            "200",
            f"{r1.status_code}",
            False,
        )
        return

    # Korak 2: admin sa REGULARNIM admin tokenom (kao da originalUser snapshot
    # iz useImpersonationStore služi za hot-swap) impersonira B → backend
    # auto-zatvori A i otvori START za B u istoj transakciji.
    r2 = post(
        f"/admin/impersonate/{ctx['student_b_id']}", token=ctx["admin_token"]
    )
    body2 = r2.json() if r2.status_code == 200 else {}
    new_target_email_ok = (
        body2.get("user", {}).get("email") == ctx["student_b_email"]
    )

    # Audit log treba da pokaže (od test 2): START_A + END_A + START_A_REOPEN +
    # AUTO_END_A + START_B = 5. Ali test 3 truncate-uje samo na startu test-a;
    # zato računamo: 2 (test 2/3) + 1 (test 4 step1 START_A) + 2 (test 4 step2
    # AUTO_END_A + START_B) = 5 redova ukupno.
    r_log = get("/admin/audit-log", token=ctx["admin_token"])
    log = r_log.json() if r_log.status_code == 200 else []

    # Napomena: PG ``func.now()`` je transaction-stable — auto-END(A) i START(B)
    # u koraku 2 dobijaju identičan ``created_at``, pa DESC sort ne garantuje
    # njihov insertion order. Zato proveravamo skup, ne tuple, za ovaj par.
    total_ok = len(log) == 5
    counts = {"START": 0, "END": 0}
    for r in log:
        if r["action"] == "IMPERSONATION_START":
            counts["START"] += 1
        elif r["action"] == "IMPERSONATION_END":
            counts["END"] += 1
    counts_ok = counts == {"START": 3, "END": 2}

    # Najnovija 2 reda (po DESC) imaju isti created_at (auto-END + START iz step 2).
    # Po sadržaju moraju biti: jedan END za A, jedan START za B.
    if len(log) >= 2:
        last_two = log[:2]
        actions_set = {r["action"] for r in last_two}
        end_for_a = any(
            r["action"] == "IMPERSONATION_END"
            and r["impersonated_user_id"] == ctx["student_a_id"]
            for r in last_two
        )
        start_for_b = any(
            r["action"] == "IMPERSONATION_START"
            and r["impersonated_user_id"] == ctx["student_b_id"]
            for r in last_two
        )
        last_two_ok = (
            actions_set == {"IMPERSONATION_START", "IMPERSONATION_END"}
            and end_for_a
            and start_for_b
        )
    else:
        last_two_ok = False

    ctx["imp_token_b"] = body2.get("access_token", "")

    record(
        "Re-impersonate: A→B u istoj transakciji (auto END(A) + START(B))",
        "5 audit redova ukupno (3 START + 2 END), poslednja 2 = {END(A), START(B)} "
        "(skup, jer dele timestamp), novi imp token za B uspešno izdat",
        f"status={r2.status_code} new_target_ok={new_target_email_ok} "
        f"total={len(log)} counts={counts} last_two_ok={last_two_ok}",
        r2.status_code == 200
        and new_target_email_ok
        and total_ok
        and counts_ok
        and last_two_ok,
    )


def test_5_validation_errors(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Validation: self / admin-on-admin / inactive / 404 ===\n")
    # Self-impersonate
    r_self = post(
        f"/admin/impersonate/{ctx['admin_id']}", token=ctx["admin_token"]
    )
    # Admin-on-admin (sluzba ETF)
    r_admin = post(
        f"/admin/impersonate/{ctx['other_admin_id']}", token=ctx["admin_token"]
    )
    # Inactive user (deaktivirali smo student_b u setup-u? Ne — deaktiviraćemo ga ovde)
    # Da bi bili nezavisni od test 4, kreiramo trećeg test studenta i deaktiviramo.
    deactivate_user_in_db(ctx["student_c_email"])
    r_inactive = post(
        f"/admin/impersonate/{ctx['student_c_id']}", token=ctx["admin_token"]
    )
    # Non-existent UUID
    fake_id = str(uuid4())
    r_404 = post(f"/admin/impersonate/{fake_id}", token=ctx["admin_token"])

    record(
        "Validation: self=400, admin-on-admin=400, inactive=400, 404=404",
        "self=400 + admin=400 + inactive=400 + non-existent=404",
        f"self={r_self.status_code} admin={r_admin.status_code} "
        f"inactive={r_inactive.status_code} 404={r_404.status_code}",
        r_self.status_code == 400
        and r_admin.status_code == 400
        and r_inactive.status_code == 400
        and r_404.status_code == 404,
    )


def test_6_ip_capture(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — IP capture: ip_address validan IPv4 / IPv6 ===\n")
    r_log = get("/admin/audit-log", token=ctx["admin_token"])
    log = r_log.json() if r_log.status_code == 200 else []

    ipv4_re = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    ipv6_re = re.compile(r"^[0-9a-fA-F:]+$")

    valid_ips = [
        r["ip_address"]
        for r in log
        if r["ip_address"]
        and (ipv4_re.match(r["ip_address"]) or ipv6_re.match(r["ip_address"]))
    ]
    all_have_ip = all(r.get("ip_address") for r in log)
    ip_set = sorted({r["ip_address"] for r in log if r.get("ip_address")})

    record(
        "Svi audit redovi imaju validan IP adresa (X-Real-IP od nginx-a)",
        f"all rows have ip_address + matches IPv4 or IPv6 + len(ips)={len(log)}",
        f"audit_rows={len(log)} all_have_ip={all_have_ip} valid={len(valid_ips)} "
        f"distinct_ips={ip_set}",
        len(log) > 0 and all_have_ip and len(valid_ips) == len(log),
    )


def test_7_audit_log_filters(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 7 — Audit log filteri: admin_id / action / from_date ===\n")
    # Filter by action=IMPERSONATION_START → samo START redovi
    r_start = get(
        "/admin/audit-log",
        token=ctx["admin_token"],
        params={"action": "IMPERSONATION_START"},
    )
    starts = r_start.json() if r_start.status_code == 200 else []
    only_starts = all(r["action"] == "IMPERSONATION_START" for r in starts)

    # Filter by admin_id postojeće → vraća redove
    r_admin = get(
        "/admin/audit-log",
        token=ctx["admin_token"],
        params={"admin_id": ctx["admin_id"]},
    )
    admin_rows = r_admin.json() if r_admin.status_code == 200 else []
    admin_match = all(r["admin_id"] == ctx["admin_id"] for r in admin_rows)

    # Filter by admin_id koji ne postoji → 0 redova
    r_other = get(
        "/admin/audit-log",
        token=ctx["admin_token"],
        params={"admin_id": str(uuid4())},
    )
    other = r_other.json() if r_other.status_code == 200 else []

    # Filter by from_date u budućnosti → 0 redova
    future = "2099-01-01"
    r_future = get(
        "/admin/audit-log",
        token=ctx["admin_token"],
        params={"from_date": future},
    )
    future_rows = r_future.json() if r_future.status_code == 200 else []

    # Invalid action (frontend ne sme da pošalje, ali validacija nas štiti)
    r_bad = get(
        "/admin/audit-log",
        token=ctx["admin_token"],
        params={"action": "NOT_AN_ACTION"},
    )

    record(
        "Filteri: action exact-match, admin_id, future from_date isključuje sve, invalid action=422",
        "action filter only START + admin_id match + non-existent admin=0 + "
        "from_date future=0 + invalid action=422",
        f"only_starts={only_starts} ({len(starts)} rows) "
        f"admin_match={admin_match} ({len(admin_rows)} rows) "
        f"other_admin={len(other)} future={len(future_rows)} "
        f"bad_action={r_bad.status_code}",
        only_starts
        and admin_match
        and len(other) == 0
        and len(future_rows) == 0
        and r_bad.status_code == 422,
    )


def test_8_expired_token(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 8 — Expired imp token → 401 (ne pokušava refresh) ===\n")
    # Forge expired imp token (exp u prošlosti) preko backend container Python-a.
    # Koristimo isti SECRET_KEY i jose.jwt — NE auth/refresh endpoint, jer
    # impersonation tokeni nemaju refresh par. Payload prosleđujemo kroz env
    # var (docker exec -e) jer Windows docker exec stdin attach ume da bude
    # nepouzdan bez ``-i`` flag-a.
    payload = {
        "sub": ctx["student_a_id"],
        "role": "STUDENT",
        "email": ctx["student_a_email"],
        "imp": True,
        "imp_email": ADMIN_EMAIL,
        "imp_name": "Studentska Služba FON",
        "exp": int(datetime.now(timezone.utc).timestamp()) - 60,
        "type": "access",
    }
    proc = subprocess.run(
        [
            "docker", "exec", "-e", f"PAYLOAD={json.dumps(payload)}",
            BACKEND_CONTAINER, "python", "-c",
            "import os, json; "
            "from jose import jwt; "
            "from app.core.config import settings; "
            "p = json.loads(os.environ['PAYLOAD']); "
            "print(jwt.encode(p, settings.SECRET_KEY, algorithm=settings.ALGORITHM), end='')",
        ],
        capture_output=True, timeout=10,
    )
    if proc.returncode != 0:
        record(
            "Forge expired imp token (helper)",
            "forge OK",
            f"forge failed: {proc.stderr.decode()}",
            False,
        )
        return
    expired_token = proc.stdout.decode().strip()

    # Pokušaj API poziva sa expired tokenom
    r_me = get("/auth/me", token=expired_token)
    r_log = get("/admin/audit-log", token=expired_token)
    r_end = post("/admin/impersonate/end", token=expired_token)

    record(
        "Expired imp token: 401 na svim API pozivima (no auto-refresh)",
        "auth/me=401 + audit-log=401 + impersonate/end=401",
        f"me={r_me.status_code} audit-log={r_log.status_code} end={r_end.status_code}",
        r_me.status_code == 401
        and r_log.status_code == 401
        and r_end.status_code == 401,
    )


# ── Setup / Main ──────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    truncate_audit_log()
    print("  audit_log truncated")

    suffix = rand_suffix()
    print(f"  suffix={suffix}")

    admin_token, admin_user = login(ADMIN_EMAIL, ADMIN_PW)
    other_admin_token, other_admin_user = login("sluzba@etf.bg.ac.rs", ADMIN_PW)
    print(f"  admin login OK ({admin_user['email']})")

    # 3 test studenta
    a_email, a_pw = register_student(suffix + "a")
    b_email, _ = register_student(suffix + "b")
    c_email, _ = register_student(suffix + "c")

    # Login student A za RBAC test
    a_token, a_user = login(a_email, a_pw)
    # Get B i C ID-jeve preko admin /admin/users?q=
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
        "other_admin_id": other_admin_user["id"],
        "student_a_token": a_token,
        "student_a_id": a_user["id"],
        "student_a_email": a_email,
        "student_b_id": b_user["id"],
        "student_b_email": b_email,
        "student_c_id": c_user["id"],
        "student_c_email": c_email,
    }


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    try:
        test_1_rbac_non_admin_forbidden(ctx)
        test_2_happy_path_start(ctx)
        test_3_end_returns_admin_token(ctx)
        test_4_reimpersonate_a_to_b(ctx)
        test_5_validation_errors(ctx)
        test_6_ip_capture(ctx)
        test_7_audit_log_filters(ctx)
        test_8_expired_token(ctx)
    finally:
        cleanup_test_rows("imp_e2e_")
        truncate_audit_log()
        print("\n[cleanup] obrisani test studenti (imp_e2e_) + audit_log truncated")

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
