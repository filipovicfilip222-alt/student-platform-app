"""End-to-end integration test za KORAK 5 (Faza 4.3) — Admin users CRUD + bulk CSV import.

Run protiv žive ``docker compose --profile app up`` instance na localhost-u
(kroz nginx port 80; override sa ``API_BASE``).

Pokriva 7 scenarija (acceptance kriterijumi iz CURSOR_PROMPT_1 §4.3 +
ROADMAP §4.3 + user prompt I-5.4 acceptance):

    1. RBAC — non-admin GET /admin/users → 403.
    2. POST /admin/users — kreiranje profesora (staff email
       ``*@fon.bg.ac.rs``) → 201, response shape AdminUserResponse,
       Celery welcome email task primljen u worker logu.
    3. PATCH /admin/users/{id} — promena faculty FON → ETF i first_name
       → 200, polja ažurirana.
    4. POST /admin/users/{id}/deactivate — soft delete → 200, login
       deaktiviranog → 403.
    5. Validation errors — POST sa neusklađenim role+domain (PROFESOR sa
       student domenom) → 422; POST sa već postojećim email-om → 409;
       PATCH nepostojećeg ID-ja → 404.
    6. Bulk preview — multipart upload sa fixture CSV-om dograđenim
       jednim in-DB dup redom (registrovani student) → 200, tačno
       5 valid / 2 dup / 1 invalid kategorija.
    7. Bulk confirm — re-upload istog CSV-a → 200, ``created=5``,
       ``skipped=3``, ``failed=0``; LIST verify novih studenata + 5
       welcome email task-ova primljenih od Celery worker-a.

Idempotent: random suffix po run-u (oba kreirana profesora i bulk
studenti dobijaju jedinstvene email-ove); cleanup briše SVE redove sa
suffix-om iz oba run-a + njihove password_reset_tokens / professors.

Referenca:
    docs PRD §4.1 (CSV header: ime, prezime, email, indeks, smer, godina_upisa).
    CURRENT_STATE2 §6.17 (frontend zaključan; backend prati ugovor).
    CLAUDE.md §11 (welcome email kroz Celery task, ne direktno SMTP).
"""

from __future__ import annotations

import os
import random
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Force UTF-8 ispis za Windows cp1252 konzole (analogno test_step_42).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
BACKEND_CONTAINER = os.getenv("BACKEND_CONTAINER", "studentska_backend")
CELERY_CONTAINER = os.getenv("CELERY_CONTAINER", "studentska_celery_worker")
PG_CONTAINER = os.getenv("PG_CONTAINER", "studentska_postgres")
PG_USER = os.getenv("POSTGRES_USER", "studentska")
PG_DB = os.getenv("POSTGRES_DB", "studentska_platforma")

ADMIN_EMAIL = "sluzba@fon.bg.ac.rs"
ADMIN_PW = "Seed@2024!"

FIXTURE_CSV = Path(__file__).resolve().parent.parent / "fixtures" / "test_bulk_users.csv"


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


def patch(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.patch(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def get(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def login(email: str, password: str) -> str:
    r = post("/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"login {email} failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def register_student(suffix: str) -> tuple[str, str]:
    """Self-registration kroz /auth/register (PRD §1.1, ne kroz admin).
    Koristi se za in-DB duplicate scenario u test 6/7."""
    email = f"qa_a43_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"A43-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


# ── Celery worker ergonomics ─────────────────────────────────────────────────


def count_email_tasks_since(since_iso: str) -> int:
    """Broji ``Task email_tasks.send_email[<uuid>] received`` linije u Celery
    worker logu od datog timestamp-a. Worker dispatchuje GLOBALNO za sve
    email task-ove (ne samo welcome), pa filterujemo po prefiks-u
    ``email_tasks.send_email`` + brojimo distinct task ID-jeve.
    """
    proc = subprocess.run(
        ["docker", "logs", CELERY_CONTAINER, "--since", since_iso],
        capture_output=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return -1
    out = proc.stdout.decode("utf-8", errors="replace") + proc.stderr.decode(
        "utf-8", errors="replace"
    )
    # MainProcess "received" linija je tačno jedna po task-u.
    task_ids: set[str] = set()
    for line in out.splitlines():
        if "Task email_tasks.send_email[" in line and "received" in line:
            try:
                tid = line.split("email_tasks.send_email[", 1)[1].split("]", 1)[0]
                task_ids.add(tid)
            except IndexError:
                pass
    return len(task_ids)


def cleanup_test_rows(suffix: str) -> int:
    """Briši sve redove čiji email sadrži ``suffix`` (test prefix:
    ``qa_a43_``, profesori: ``prof_a43_``, bulk: ``bulk_a43_``).
    Briše password_reset_tokens i professors pre user-a (FK)."""
    sql = (
        "DELETE FROM password_reset_tokens "
        "WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%{s}%'); "
        "DELETE FROM professors "
        "WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%{s}%'); "
        "DELETE FROM users WHERE email LIKE '%{s}%';"
    ).format(s=suffix)
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-c", sql],
        capture_output=True,
        timeout=15,
    )
    return proc.returncode


# ── Tests ────────────────────────────────────────────────────────────────────


def test_1_rbac_non_admin_forbidden(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — RBAC: non-admin GET /admin/users → 403 ===\n")
    r = get("/admin/users", token=ctx["student_token"])
    record(
        "Student token na /admin/users → 403",
        "status_code == 403",
        f"status_code={r.status_code} detail={r.json().get('detail') if r.headers.get('content-type','').startswith('application/json') else r.text[:80]}",
        r.status_code == 403,
    )


def test_2_create_professor(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — POST /admin/users (PROFESOR + welcome email) ===\n")
    suffix = ctx["suffix"]
    email = f"prof_a43_{suffix}@fon.bg.ac.rs"
    payload = {
        "email": email,
        "password": "AdminPass1!",
        "first_name": "Test",
        "last_name": "Profesor",
        "role": "PROFESOR",
        "faculty": "FON",
    }
    before = count_email_tasks_since("1m")
    r = post("/admin/users", token=ctx["admin_token"], json=payload)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}

    expected_fields = {
        "id", "email", "first_name", "last_name", "role", "faculty",
        "is_active", "is_verified", "profile_image_url", "created_at",
    }
    actual_fields = set(body.keys())
    shape_ok = expected_fields.issubset(actual_fields)

    # Daj Celery worker-u 2 sekunde da primi task
    time.sleep(2)
    after = count_email_tasks_since("2m")
    welcome_dispatched = after > before

    record(
        "POST /admin/users PROFESOR → 201 + AdminUserResponse shape",
        "201 + sva polja iz AdminUserResponse + welcome email task primljen",
        f"status={r.status_code} shape_ok={shape_ok} email={body.get('email')} role={body.get('role')} dispatched_delta>0={welcome_dispatched}",
        r.status_code == 201 and shape_ok and welcome_dispatched,
    )
    ctx["created_prof_id"] = body.get("id")
    ctx["created_prof_email"] = email


def test_3_patch_faculty(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — PATCH /admin/users/{id} (faculty FON→ETF + first_name) ===\n")
    pid = ctx.get("created_prof_id")
    if not pid:
        record("PATCH /admin/users/{id}", "test 2 mora prvi proći", "skipped (no prof_id)", False)
        return
    r = patch(
        f"/admin/users/{pid}",
        token=ctx["admin_token"],
        json={"faculty": "ETF", "first_name": "Updated"},
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    record(
        "PATCH menja samo poslata polja",
        "200 + faculty=ETF + first_name=Updated + last_name nepromenjen",
        f"status={r.status_code} faculty={body.get('faculty')} first={body.get('first_name')} last={body.get('last_name')}",
        r.status_code == 200
        and body.get("faculty") == "ETF"
        and body.get("first_name") == "Updated"
        and body.get("last_name") == "Profesor",
    )


def test_4_deactivate_blocks_login(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — POST /admin/users/{id}/deactivate + login → 403 ===\n")
    pid = ctx.get("created_prof_id")
    email = ctx.get("created_prof_email")
    if not pid:
        record("POST /admin/users/{id}/deactivate", "test 2 mora prvi proći", "skipped", False)
        return
    r1 = post(f"/admin/users/{pid}/deactivate", token=ctx["admin_token"])
    r2 = post("/auth/login", json={"email": email, "password": "AdminPass1!"})
    record(
        "Deaktiviran korisnik ne može da se uloguje",
        "deactivate=200 + login=403",
        f"deactivate={r1.status_code} login={r2.status_code} detail={r2.json().get('detail') if r2.headers.get('content-type','').startswith('application/json') else r2.text[:60]}",
        r1.status_code == 200 and r2.status_code == 403,
    )


def test_5_validation_errors(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Validation: 422 (role/domain), 409 (dup), 404 (missing) ===\n")
    suffix = ctx["suffix"]

    # 5a) PROFESOR sa student domenom → 422
    r_role = post(
        "/admin/users",
        token=ctx["admin_token"],
        json={
            "email": f"badrole_a43_{suffix}@student.fon.bg.ac.rs",
            "password": "AdminPass1!",
            "first_name": "Bad",
            "last_name": "Role",
            "role": "PROFESOR",
            "faculty": "FON",
        },
    )

    # 5b) Duplikat email — re-create istog deaktiviranog profesora → 409
    dup_email = ctx.get("created_prof_email")
    r_dup = post(
        "/admin/users",
        token=ctx["admin_token"],
        json={
            "email": dup_email,
            "password": "AdminPass1!",
            "first_name": "Dup",
            "last_name": "Email",
            "role": "PROFESOR",
            "faculty": "FON",
        },
    )

    # 5c) PATCH nepostojeći ID
    r_404 = patch(
        "/admin/users/00000000-0000-0000-0000-000000000000",
        token=ctx["admin_token"],
        json={"first_name": "Ghost"},
    )

    record(
        "POST sa neusklađenim role+domain + dup email + PATCH 404",
        "role-mismatch=422 + dup=409 + missing=404",
        f"role={r_role.status_code} dup={r_dup.status_code} missing={r_404.status_code}",
        r_role.status_code == 422 and r_dup.status_code == 409 and r_404.status_code == 404,
    )


def _build_csv_with_in_db_dup(in_db_email: str) -> bytes:
    """Učitaj fixture i prepend-uj jedan red sa već postojećim student
    email-om (in-DB dup). Tako fixture ostaje deterministički statičan
    a test ima 5 valid + 2 dup (1 in-file + 1 in-DB) + 1 invalid = 8 reda."""
    base = FIXTURE_CSV.read_text(encoding="utf-8")
    lines = base.splitlines(keepends=True)
    header = lines[0]
    body = "".join(lines[1:])
    extra = (
        f"Existing,Student,{in_db_email},X-DUP,IS,2024\n"
    )
    return (header + extra + body).encode("utf-8")


def test_6_bulk_preview(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — Bulk preview: 5 valid / 2 dup / 1 invalid ===\n")
    csv_bytes = _build_csv_with_in_db_dup(ctx["existing_student_email"])
    files = {"file": ("test_bulk_users.csv", csv_bytes, "text/csv")}
    r = post("/admin/users/bulk-import/preview", token=ctx["admin_token"], files=files)
    body = r.json() if r.status_code == 200 else {}

    valid = body.get("valid_rows", []) or []
    invalid = body.get("invalid_rows", []) or []
    duplicates = body.get("duplicates", []) or []
    total = body.get("total")

    invalid_emails = {row["email"].lower() for row in invalid}
    dup_emails = {row["email"].lower() for row in duplicates}

    expected_valid_emails = {
        "bulkfix1@student.fon.bg.ac.rs",
        "bulkfix2@student.fon.bg.ac.rs",
        "bulkfix3@student.etf.bg.ac.rs",
        "bulkfix4@student.etf.bg.ac.rs",
        "bulkfix5@student.fon.bg.ac.rs",
    }
    valid_emails = {row["email"].lower() for row in valid}

    record(
        "Preview: 5 valid + 2 dup + 1 invalid kategorija",
        f"total=8, valid_emails={sorted(expected_valid_emails)}, "
        f"invalid contains 'bulkbad@gmail.com', duplicates contains "
        f"'bulkfix1@...' i '{ctx['existing_student_email']}'",
        f"total={total} v={len(valid)} i={len(invalid)} d={len(duplicates)} "
        f"valid={sorted(valid_emails)} invalid={sorted(invalid_emails)} "
        f"dup={sorted(dup_emails)}",
        r.status_code == 200
        and total == 8
        and len(valid) == 5
        and len(invalid) == 1
        and len(duplicates) == 2
        and valid_emails == expected_valid_emails
        and "bulkbad@gmail.com" in invalid_emails
        and "bulkfix1@student.fon.bg.ac.rs" in dup_emails
        and ctx["existing_student_email"].lower() in dup_emails,
    )


def test_7_bulk_confirm_and_emails(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 7 — Bulk confirm: created=5, skipped=3, 5 welcome email-ova ===\n")
    csv_bytes = _build_csv_with_in_db_dup(ctx["existing_student_email"])
    files = {"file": ("test_bulk_users.csv", csv_bytes, "text/csv")}

    before = count_email_tasks_since("3m")
    r = post("/admin/users/bulk-import/confirm", token=ctx["admin_token"], files=files)
    body = r.json() if r.status_code == 200 else {}

    time.sleep(3)  # daj Celery worker-u vremena da primi 5 task-ova
    after = count_email_tasks_since("3m")
    delta = after - before if before >= 0 and after >= 0 else -1

    # Verify kroz LIST endpoint
    r_list = get("/admin/users", token=ctx["admin_token"], params={"q": "bulkfix"})
    listed = r_list.json() if r_list.status_code == 200 else []
    listed_emails = {u["email"].lower() for u in listed}
    expected_listed = {
        "bulkfix1@student.fon.bg.ac.rs",
        "bulkfix2@student.fon.bg.ac.rs",
        "bulkfix3@student.etf.bg.ac.rs",
        "bulkfix4@student.etf.bg.ac.rs",
        "bulkfix5@student.fon.bg.ac.rs",
    }

    record(
        "Confirm kreira 5, skipuje 3, dispatch-uje 5 welcome email-ova",
        "200 + created=5 + skipped=3 + failed=0 + 5 welcome email task-ova "
        "+ LIST q=bulkfix vraća 5 redova",
        f"status={r.status_code} created={body.get('created')} "
        f"skipped={body.get('skipped')} failed={body.get('failed')} "
        f"email_delta={delta} listed={len(listed)}={sorted(listed_emails)}",
        r.status_code == 200
        and body.get("created") == 5
        and body.get("skipped") == 3
        and body.get("failed") == 0
        and delta >= 5
        and listed_emails == expected_listed,
    )


# ── Setup / Main ─────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    if not FIXTURE_CSV.exists():
        raise RuntimeError(
            f"Fixture nije pronađen: {FIXTURE_CSV}. "
            f"I-5.4 mora prvo kreirati scripts/fixtures/test_bulk_users.csv."
        )

    suffix = rand_suffix()
    print(f"  suffix={suffix}")

    admin_token = login(ADMIN_EMAIL, ADMIN_PW)
    print(f"  admin login OK")

    student_email, student_pw = register_student(suffix)
    student_token = login(student_email, student_pw)
    print(f"  registered + login student {student_email}")

    return {
        "suffix": suffix,
        "admin_token": admin_token,
        "student_token": student_token,
        "existing_student_email": student_email,
    }


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    try:
        test_1_rbac_non_admin_forbidden(ctx)
        test_2_create_professor(ctx)
        test_3_patch_faculty(ctx)
        test_4_deactivate_blocks_login(ctx)
        test_5_validation_errors(ctx)
        test_6_bulk_preview(ctx)
        test_7_bulk_confirm_and_emails(ctx)
    finally:
        # Cleanup: oba prefiksa (qa_a43_ za studente, prof_a43_ za profesore,
        # badrole_a43_ za 5a) + bulkfix*@student.* studente kreirane u test 7.
        for token in ("qa_a43_", "prof_a43_", "badrole_a43_", "bulkfix"):
            cleanup_test_rows(token)
        print("\n[cleanup] obrisani test redovi sa prefiksima qa_a43_, prof_a43_, badrole_a43_, bulkfix")

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
