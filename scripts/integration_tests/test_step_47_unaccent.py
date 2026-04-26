"""End-to-end integration test za KORAK 10 — diakritik-insensitive search
(migracija 0004 ``unaccent`` + ``pg_trgm``).

Pokriva acceptance kriterijume iz CURSOR_PROMPT_1 §10:

    1. Sanity — ``public.f_unaccent('Đorđević') = 'Djordjevic'`` u psql-u.
       Verifikuje da je migracija primenjena i da ``replace`` + ``unaccent``
       kompozicija radi za srpski ``đ → dj`` slučaj.
    2. Student search „Petrovic" (bez dijakritika) → matchuje seed
       profesora ``profesor1@fon.bg.ac.rs`` čije pravo prezime je
       „Petrović". Verifikuje da ``func.f_unaccent`` wrapper u
       ``search_service.search_professors`` radi.
    3. Student search „djordjevic" → matchuje TEST profesora
       „Đorđe Đorđević". Cilj: dokazati da ``đ → dj`` zaista hvata,
       što je razlog zbog kog je u migraciji 0004 dodat ``replace``
       korak pre ``unaccent``.
    4. Search ASCII no-op „Stefan" — kreiramo test prof-a sa imenom
       „Stefan", search ga vrati nepromenjenog. Verifikuje da ne
       lomimo postojeći flow.
    5. Search po ``professors.areas_of_interest`` — kreiramo prof-a sa
       ``areas_of_interest = ['Veštačka inteligencija']`` (TEXT[]),
       search „vestacka" ga vrati. Verifikuje ``f_unaccent_array``
       wrapper + GIN trigram indeks nad TEXT[] kolonom.
    6. Admin ``/users`` search „petrovic" — kao admin token, isti hit
       set kao student search. Verifikuje da i ``admin_user_service
       .list_users`` koristi ``f_unaccent`` (KORAK 5 deo dograđen u
       KORAKU 10).
    7. EXPLAIN ANALYZE — direktni psql poziv pokazuje
       ``Bitmap Index Scan on ix_users_first_name_unaccent_trgm``
       (NE ``Seq Scan``). Bez ``pg_trgm`` GIN indeksa, leading-wildcard
       ILIKE bi UVEK išao kroz Seq Scan.

Run protiv žive ``docker compose --profile app up`` instance:

    python scripts/integration_tests/test_step_47_unaccent.py

Idempotent: random suffix po run-u; cleanup briše SVE redove sa prefiksom
``qa_a47_`` (student) i ``prof_a47_`` (test profesori) iz oba run-a.

Referenca:
    CURSOR_PROMPT_1 §10 (acceptance lista).
    backend/alembic/versions/20260427_0004_unaccent.py (migracija).
    backend/app/services/search_service.py (refactor).
    backend/app/services/admin_user_service.py (refactor).
    CLAUDE.md §3 (sve async, ORM only) — ovde se ne tiče testa, ali
    podseća zašto je migracija raw SQL (DDL, ne ORM).
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

# Force UTF-8 ispis za Windows cp1252 konzole (analogno test_step_43).
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

# Seed profesor sa dijakritičkim prezimenom — postoji u svakom okruženju
# (vidi scripts/seed_db.py + CURRENT_STATE2 §8 seed users).
SEED_PROF_EMAIL = "profesor1@fon.bg.ac.rs"
SEED_PROF_LAST_NAME = "Petrović"


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


def login(email: str, password: str) -> str:
    r = post("/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"login {email} failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def register_student(suffix: str) -> tuple[str, str]:
    """Self-registration kroz /auth/register — samo da bismo imali student
    token za RBAC-protected ``/students/professors/search`` endpoint.
    Cleanup ga briše po prefiksu ``qa_a47_``."""
    email = f"qa_a47_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA",
            "last_name": f"A47-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    return email, password


# ── psql helpers ─────────────────────────────────────────────────────────────


def psql(sql: str, *, capture: bool = True) -> tuple[int, str]:
    """Run psql -c and vrati (returncode, stdout+stderr)."""
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-c", sql],
        capture_output=capture,
        timeout=15,
    )
    out = (proc.stdout or b"").decode("utf-8", errors="replace") + (
        proc.stderr or b""
    ).decode("utf-8", errors="replace")
    return proc.returncode, out


def cleanup_test_rows(suffix_or_prefix: str) -> int:
    """Briši sve redove čiji email sadrži ``suffix_or_prefix`` (test
    prefix: ``qa_a47_``, ``prof_a47_``). Briše password_reset_tokens i
    professors pre user-a (FK)."""
    sql = (
        "DELETE FROM password_reset_tokens "
        "WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%{s}%'); "
        "DELETE FROM professors "
        "WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%{s}%'); "
        "DELETE FROM users WHERE email LIKE '%{s}%';"
    ).format(s=suffix_or_prefix)
    rc, _ = psql(sql)
    return rc


# ── Test prof setup ──────────────────────────────────────────────────────────


def create_test_professor(
    admin_token: str,
    *,
    suffix: str,
    handle: str,
    first_name: str,
    last_name: str,
    department: str,
    areas_of_interest: list[str],
) -> str:
    """Kreira test profesora kroz POST /admin/users + nadgrađuje
    ``professors`` red (department + areas_of_interest) direktnim SQL-om
    jer ``AdminUserCreate`` ugovor ne pokriva ta polja (admin ih posle
    dopunjava preko ``PUT /professors/profile`` u stvarnom flow-u).

    Vraća email kreiranog profesora (za debug/logging; ID nam ne treba
    za search testove).
    """
    email = f"prof_a47_{handle}_{suffix}@fon.bg.ac.rs"
    payload = {
        "email": email,
        "password": "AdminPass1!",
        "first_name": first_name,
        "last_name": last_name,
        "role": "PROFESOR",
        "faculty": "FON",
    }
    r = post("/admin/users", token=admin_token, json=payload)
    if r.status_code != 201:
        raise RuntimeError(
            f"create_test_professor({email}) failed: {r.status_code} {r.text}"
        )

    # SQL escape za apostrofe i ASCII array literal — areas_of_interest
    # ulazi kao PG ARRAY['x','y'] preko psql-a. Kvotujemo svaki element.
    aoi_sql_array = "ARRAY[" + ",".join(
        f"'{a.replace(chr(39), chr(39) + chr(39))}'" for a in areas_of_interest
    ) + "]::text[]"
    dept_sql = department.replace("'", "''")
    update_sql = (
        f"UPDATE professors SET department = '{dept_sql}', "
        f"areas_of_interest = {aoi_sql_array} "
        f"WHERE user_id = (SELECT id FROM users WHERE email = '{email}');"
    )
    rc, out = psql(update_sql)
    if rc != 0:
        raise RuntimeError(f"update professor metadata failed: {out}")
    return email


# ── Tests ────────────────────────────────────────────────────────────────────


def test_1_sanity_psql_unaccent() -> None:
    print("\n=== TEST 1 — Sanity: psql f_unaccent kompozicija (đ→dj + dijakritici) ===\n")
    rc, out = psql(
        "SELECT public.f_unaccent('Đorđević') AS djordj, "
        "public.f_unaccent('Šljivić') AS sljiv, "
        "public.f_unaccent('Stefan') AS no_op;"
    )
    djordj_ok = "Djordjevic" in out
    sljiv_ok = "Sljivic" in out
    no_op_ok = "Stefan" in out
    record(
        "f_unaccent('Đorđević')='Djordjevic', f_unaccent('Šljivić')='Sljivic', no-op",
        "Djordjevic + Sljivic + Stefan u outputu",
        f"rc={rc} djordj_ok={djordj_ok} sljiv_ok={sljiv_ok} no_op_ok={no_op_ok}",
        rc == 0 and djordj_ok and sljiv_ok and no_op_ok,
    )


def test_2_student_search_petrovic(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — Student search 'Petrovic' → matchuje seed 'Milovan Petrović' ===\n")
    r = get(
        "/students/professors/search",
        token=ctx["student_token"],
        params={"q": "Petrovic"},
    )
    body = r.json() if r.status_code == 200 else []
    matched = [
        p for p in body
        if SEED_PROF_LAST_NAME in p.get("full_name", "")
    ]
    record(
        "Search 'Petrovic' (no diacritic) → seed prof sa 'Petrović'",
        f"200 + bar 1 hit sa '{SEED_PROF_LAST_NAME}' u full_name",
        f"status={r.status_code} total={len(body)} matched={len(matched)} "
        f"first_full_name={matched[0]['full_name'] if matched else None}",
        r.status_code == 200 and len(matched) >= 1,
    )


def test_3_student_search_djordjevic(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — Student search 'djordjevic' → matchuje 'Đorđe Đorđević' ===\n")
    r = get(
        "/students/professors/search",
        token=ctx["student_token"],
        params={"q": "djordjevic"},
    )
    body = r.json() if r.status_code == 200 else []
    matched = [
        p for p in body
        if "Đorđević" in p.get("full_name", "")
    ]
    record(
        "Search 'djordjevic' (sve ASCII) → 'Đorđe Đorđević' (đ→dj + unaccent)",
        "200 + bar 1 hit sa 'Đorđević' u full_name",
        f"status={r.status_code} total={len(body)} matched={len(matched)} "
        f"first_full_name={matched[0]['full_name'] if matched else None}",
        r.status_code == 200 and len(matched) >= 1,
    )


def test_4_student_search_ascii_noop(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — Search ASCII 'Stefan' → no-op (matchuje 'Stefan Mladenovic') ===\n")
    r = get(
        "/students/professors/search",
        token=ctx["student_token"],
        params={"q": "Stefan"},
    )
    body = r.json() if r.status_code == 200 else []
    matched = [p for p in body if "Stefan" in p.get("full_name", "")]
    record(
        "Search 'Stefan' (ASCII) → matchuje test prof-a sa 'Stefan'",
        "200 + bar 1 hit sa 'Stefan' u full_name",
        f"status={r.status_code} total={len(body)} matched={len(matched)}",
        r.status_code == 200 and len(matched) >= 1,
    )


def test_5_search_areas_of_interest(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Search 'vestacka' po areas_of_interest → 'Veštačka inteligencija' ===\n")
    r = get(
        "/students/professors/search",
        token=ctx["student_token"],
        params={"q": "vestacka"},
    )
    body = r.json() if r.status_code == 200 else []
    # Naš test prof se zove "Stefan Mladenović" ali ima areas_of_interest =
    # ['Veštačka inteligencija']. Match dolazi iz areas, ne iz imena.
    matched = [
        p for p in body
        if "Stefan" in p.get("full_name", "") or "Mladenov" in p.get("full_name", "")
    ]
    record(
        "Search 'vestacka' (ASCII) → match preko areas_of_interest 'Veštačka inteligencija'",
        "200 + bar 1 hit (test prof Stefan Mladenović sa AI oblasti)",
        f"status={r.status_code} total={len(body)} matched={len(matched)}",
        r.status_code == 200 and len(matched) >= 1,
    )


def test_6_admin_search_petrovic(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — Admin /users search 'petrovic' → matchuje 'Petrović' ===\n")
    r = get(
        "/admin/users",
        token=ctx["admin_token"],
        params={"q": "petrovic"},
    )
    body = r.json() if r.status_code == 200 else []
    matched = [
        u for u in body
        if SEED_PROF_LAST_NAME in u.get("last_name", "")
    ]
    record(
        "Admin search 'petrovic' → seed prof sa 'Petrović'",
        f"200 + bar 1 hit sa last_name='{SEED_PROF_LAST_NAME}'",
        f"status={r.status_code} total={len(body)} matched={len(matched)} "
        f"first_last={matched[0]['last_name'] if matched else None}",
        r.status_code == 200 and len(matched) >= 1,
    )


def test_7_explain_uses_index() -> None:
    print("\n=== TEST 7 — EXPLAIN ANALYZE pokazuje Bitmap Index Scan (NE Seq Scan) ===\n")
    # ``SET enable_seqscan = off`` forsira planera da bira indeks čak i na
    # malom dataset-u (gde bi inače mogao izabrati Seq Scan iz cost
    # razloga). Test verifikuje da je INDEX ISKORISTIV — što je suština
    # acceptance-a (na produkcijskom load-u sa 10K+ user-a planer bi
    # ionako birao indeks bez ovog SET-a).
    rc, out = psql(
        "SET enable_seqscan = off; "
        "EXPLAIN ANALYZE SELECT id FROM users "
        "WHERE public.f_unaccent(first_name) ILIKE public.f_unaccent('%Petrovic%') "
        "OR public.f_unaccent(last_name) ILIKE public.f_unaccent('%Petrovic%');"
    )
    uses_first_name_idx = "ix_users_first_name_unaccent_trgm" in out
    uses_last_name_idx = "ix_users_last_name_unaccent_trgm" in out
    has_bitmap_scan = "Bitmap Index Scan" in out
    no_seq_scan = "Seq Scan on users" not in out
    record(
        "EXPLAIN koristi Bitmap Index Scan na trgm indeksima",
        "Bitmap Index Scan + ix_users_first_name_unaccent_trgm + last_name + nema Seq Scan",
        f"rc={rc} bitmap={has_bitmap_scan} first_idx={uses_first_name_idx} "
        f"last_idx={uses_last_name_idx} no_seq={no_seq_scan}",
        rc == 0
        and has_bitmap_scan
        and uses_first_name_idx
        and uses_last_name_idx
        and no_seq_scan,
    )


# ── Setup / Main ─────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")

    suffix = rand_suffix()
    print(f"  suffix={suffix}")

    admin_token = login(ADMIN_EMAIL, ADMIN_PW)
    print(f"  admin login OK")

    student_email, student_pw = register_student(suffix)
    student_token = login(student_email, student_pw)
    print(f"  registered + login student {student_email}")

    # Test prof za scenario 3 — „Đorđe Đorđević" sa srpskim ``đ``.
    djordj_email = create_test_professor(
        admin_token,
        suffix=suffix,
        handle="djordj",
        first_name="Đorđe",
        last_name="Đorđević",
        department="Katedra za matematiku",
        areas_of_interest=["Diferencijalne jednačine"],
    )
    print(f"  created test prof {djordj_email}")

    # Test prof za scenario 4 (ASCII no-op) i 5 (areas_of_interest).
    # Ime „Stefan Mladenović" je čisto ASCII u prezimenu sa ``ć`` na kraju
    # (verifikuje da ć takođe radi), areas_of_interest sadrži „Veštačka
    # inteligencija" koje treba da matchuje query „vestacka".
    stefan_email = create_test_professor(
        admin_token,
        suffix=suffix,
        handle="stefan",
        first_name="Stefan",
        last_name="Mladenović",
        department="Katedra za informacione sisteme",
        areas_of_interest=["Veštačka inteligencija", "Mašinsko učenje"],
    )
    print(f"  created test prof {stefan_email}")

    # Daj backend-u trenutak da indeksira nove redove (GIN indeksi su sync
    # na insertu, ali za sigurnost short sleep).
    time.sleep(0.5)

    return {
        "suffix": suffix,
        "admin_token": admin_token,
        "student_token": student_token,
    }


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    try:
        test_1_sanity_psql_unaccent()
        test_2_student_search_petrovic(ctx)
        test_3_student_search_djordjevic(ctx)
        test_4_student_search_ascii_noop(ctx)
        test_5_search_areas_of_interest(ctx)
        test_6_admin_search_petrovic(ctx)
        test_7_explain_uses_index()
    finally:
        for prefix in ("qa_a47_", "prof_a47_"):
            cleanup_test_rows(prefix)
        print("\n[cleanup] obrisani test redovi sa prefiksima qa_a47_, prof_a47_")

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
