"""End-to-end integration test for KORAK 2 (Faza 3.8) — recurring slots.

Runs against a live ``docker compose --profile app up`` stack on localhost.

Tests (acceptance criteria from ROADMAP §3.8 / CURSOR_PROMPT_1 §2.4):
    1. POST /professors/slots with recurring_rule={freq:WEEKLY,
       by_weekday:[1], count:8} → 201 + 8 records, all sharing the
       same `recurring_group_id`, all on a Monday.
    2. GET /professors/slots returns at least the 8 freshly-created
       slots (filtered by recurring_group_id from test 1).
    3. DELETE /professors/slots/recurring/{group_id} → 204; GET no
       longer lists slots from that group.
    4. POST recurring with `until` that would generate > 100 slots
       → 422 with detail containing "prevelik raspon".
    5. Conflict: book + approve a single slot, then try a recurring
       series that overlaps it → 422 with `conflicts` list.

Idempotent — uses a unique random suffix per run for student emails
and a far-future month (2030-06+) for slots so reruns don't collide.
"""

from __future__ import annotations

import os
import random
import string
import sys
from dataclasses import dataclass

# Windows console defaults to cp1252 which can't encode → ≥ etc.
# Force UTF-8 on stdout/stderr so the test prints arrows and Cyrillic
# error messages without UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
ROOT = os.getenv("ROOT_BASE", "http://localhost")
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


def get(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(f"{API}{path}", headers=headers, timeout=30, **kwargs)


def delete(path: str, *, token: str | None = None) -> requests.Response:
    return requests.delete(
        f"{API}{path}",
        headers={"Authorization": f"Bearer {token}"} if token else {},
        timeout=30,
    )


def login(email: str, password: str) -> str:
    r = post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def register_student(suffix: str, faculty: str = "fon") -> tuple[str, str]:
    email = f"qa_{suffix}@student.{faculty}.bg.ac.rs"
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
    """Return the first Monday on or after the 1st of (year, month)."""
    d = date(year, month, 1)
    # Python weekday: Mon=0, Tue=1, …, Sun=6
    offset = (0 - d.weekday()) % 7
    return d + timedelta(days=offset)


def to_iso_utc(d: date, hour: int = 14, minute: int = 0) -> str:
    """Compose ISO-8601 with explicit +00:00 offset (matches frontend)."""
    return datetime.combine(d, time(hour, minute), tzinfo=timezone.utc).isoformat()


# ── Setup ─────────────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix()
    lead_email, lead_pw = register_student(f"rec{suffix}")
    print(f"  registered lead     {lead_email}")

    prof_token = login(PROF_EMAIL, SEED_PASSWORD)
    lead_token = login(lead_email, lead_pw)
    print("  logged in: prof, lead")

    return {
        "prof_token": prof_token,
        "lead_token": lead_token,
        "lead_email": lead_email,
        "suffix": suffix,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_1_recurring_creates_eight(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 1 — POST recurring count=8 → 8 rows w/ same recurring_group_id ===\n")
    start_monday = first_monday_of_month(2030, 6)  # 3 June 2030
    body = {
        "slot_datetime": to_iso_utc(start_monday, hour=10),
        "duration_minutes": 30,
        "consultation_type": "UZIVO",
        "max_students": 1,
        "is_available": True,
        "valid_from": start_monday.isoformat(),
        "recurring_rule": {
            "freq": "WEEKLY",
            "by_weekday": [1],  # JS Monday
            "count": 8,
        },
    }
    r = post("/professors/slots", token=ctx["prof_token"], json=body)
    if r.status_code != 201:
        record(
            "Recurring count=8 produces 8 rows",
            "201 + len==8 + 1 group_id + all Mondays",
            f"{r.status_code} {r.text[:300]}",
            False,
        )
        return
    payload = r.json()
    if not isinstance(payload, list):
        record(
            "Recurring count=8 produces 8 rows",
            "response is JSON array",
            f"got {type(payload).__name__}: {str(payload)[:200]}",
            False,
        )
        return

    group_ids = {s.get("recurring_group_id") for s in payload}
    weekdays = {datetime.fromisoformat(s["slot_datetime"]).weekday() for s in payload}
    ctx["test1_group_id"] = next(iter(group_ids), None)
    ctx["test1_slot_ids"] = [s["id"] for s in payload]

    record(
        "Recurring count=8 produces 8 rows w/ shared group_id, all Mondays",
        "201, 8 rows, |group_ids|==1 non-null, weekdays=={0}",
        f"{r.status_code}, len={len(payload)}, group_ids={group_ids}, weekdays={weekdays}",
        r.status_code == 201
        and len(payload) == 8
        and len(group_ids) == 1
        and None not in group_ids
        and weekdays == {0},
    )


def test_2_get_slots_returns_eight(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — GET /professors/slots returns the 8 fresh slots ===\n")
    group_id = ctx.get("test1_group_id")
    if not group_id:
        record("GET /slots returns the 8", "all 8 from group", "skipped (test 1 failed)", False)
        return
    r = get("/professors/slots", token=ctx["prof_token"])
    if r.status_code != 200:
        record(
            "GET /slots returns the 8",
            "200 + 8 group members",
            f"{r.status_code} {r.text[:200]}",
            False,
        )
        return
    in_group = [s for s in r.json() if s.get("recurring_group_id") == group_id]
    record(
        "GET /slots returns all 8 group members",
        "200, 8 group members visible",
        f"{r.status_code}, |in_group|={len(in_group)}",
        r.status_code == 200 and len(in_group) == 8,
    )


def test_3_delete_recurring_group(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — DELETE /professors/slots/recurring/{group_id} → 204 + gone ===\n")
    group_id = ctx.get("test1_group_id")
    if not group_id:
        record(
            "DELETE recurring group",
            "204 + 0 future members afterwards",
            "skipped (test 1 failed)",
            False,
        )
        return
    r = delete(f"/professors/slots/recurring/{group_id}", token=ctx["prof_token"])
    after = get("/professors/slots", token=ctx["prof_token"])
    remaining = (
        [s for s in after.json() if s.get("recurring_group_id") == group_id]
        if after.status_code == 200
        else None
    )
    record(
        "DELETE recurring group removes future slots",
        "204 + 0 group members in GET after",
        f"DELETE={r.status_code}, GET={after.status_code}, remaining={remaining}",
        r.status_code == 204 and remaining == [],
    )


def test_4_too_many_slots(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — > 100 generated slots → 422 'prevelik raspon' ===\n")
    start = first_monday_of_month(2030, 7)  # isolated month
    # Daily occurrences for ~6 months (7 weekdays * 26 weeks ≈ 180)
    until = start + timedelta(weeks=26)
    body = {
        "slot_datetime": to_iso_utc(start, hour=11),
        "duration_minutes": 30,
        "consultation_type": "UZIVO",
        "max_students": 1,
        "is_available": True,
        "valid_from": start.isoformat(),
        "valid_until": until.isoformat(),
        "recurring_rule": {
            "freq": "WEEKLY",
            "by_weekday": [0, 1, 2, 3, 4, 5, 6],  # every day of week
            "until": until.isoformat(),
        },
    }
    r = post("/professors/slots", token=ctx["prof_token"], json=body)
    body_text = r.text
    record(
        "Recurring > 100 slots → 422 'prevelik raspon'",
        "422, detail contains 'prevelik raspon' (case-insensitive)",
        f"{r.status_code} {body_text[:200]}",
        r.status_code == 422 and "prevelik raspon" in body_text.lower(),
    )


def test_5_conflict_with_approved(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Recurring overlaps APPROVED appointment → 422 + conflicts list ===\n")
    start_monday = first_monday_of_month(2030, 8)  # isolated month

    # Step A: professor creates a single slot the lead can book.
    single_slot_iso = to_iso_utc(start_monday, hour=14)
    r = post(
        "/professors/slots",
        token=ctx["prof_token"],
        json={
            "slot_datetime": single_slot_iso,
            "duration_minutes": 30,
            "consultation_type": "UZIVO",
            "max_students": 1,
            "is_available": True,
        },
    )
    if r.status_code != 201:
        record(
            "Conflict pre-step (single slot)",
            "201",
            f"{r.status_code} {r.text[:200]}",
            False,
        )
        return
    single_payload = r.json()
    # POST /slots returns a list; the single-shot path returns [slot].
    single_slot = single_payload[0] if isinstance(single_payload, list) else single_payload
    single_slot_id = single_slot["id"]

    # Step B: student books, professor approves to APPROVED.
    book = post(
        "/students/appointments",
        token=ctx["lead_token"],
        json={
            "slot_id": single_slot_id,
            "topic_category": "ISPIT",
            "description": "QA conflict-detection booking — KORAK 2 acceptance.",
        },
    )
    if book.status_code != 200:
        record(
            "Conflict pre-step (book)",
            "200",
            f"{book.status_code} {book.text[:200]}",
            False,
        )
        return
    appt = book.json()
    if appt["status"] != "APPROVED":
        ar = post(
            f"/professors/requests/{appt['id']}/approve",
            token=ctx["prof_token"],
        )
        if ar.status_code != 200:
            record(
                "Conflict pre-step (approve)",
                "200 APPROVED",
                f"{ar.status_code} {ar.text[:200]}",
                False,
            )
            return

    # Step C: professor tries a recurring series whose first occurrence
    # lands on exactly that timeslot → backend should reject 422 with
    # `conflicts` listing the offending slot_datetime.
    recurring_body = {
        "slot_datetime": single_slot_iso,
        "duration_minutes": 30,
        "consultation_type": "UZIVO",
        "max_students": 1,
        "is_available": True,
        "valid_from": start_monday.isoformat(),
        "recurring_rule": {
            "freq": "WEEKLY",
            "by_weekday": [1],
            "count": 4,
        },
    }
    r = post("/professors/slots", token=ctx["prof_token"], json=recurring_body)
    body_text = r.text
    detail: Any = None
    if r.status_code == 422:
        try:
            detail = r.json().get("detail")
        except Exception:  # noqa: BLE001
            pass
    has_conflicts = (
        isinstance(detail, dict)
        and isinstance(detail.get("conflicts"), list)
        and len(detail["conflicts"]) >= 1
    )
    record(
        "Recurring vs APPROVED appt → 422 + conflicts list",
        "422 + detail.conflicts[] non-empty",
        f"{r.status_code}, has_conflicts={has_conflicts}, body={body_text[:300]}",
        r.status_code == 422 and has_conflicts,
    )

    # Cleanup the single slot's appointment so reruns aren't blocked
    # by the student-side appointment row. We don't fail the test if
    # cleanup itself fails — it's best-effort.
    try:
        delete(f"/students/appointments/{appt['id']}", token=ctx["lead_token"])
    except Exception:  # noqa: BLE001
        pass


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    test_1_recurring_creates_eight(ctx)
    test_2_get_slots_returns_eight(ctx)
    test_3_delete_recurring_group(ctx)
    test_4_too_many_slots(ctx)
    test_5_conflict_with_approved(ctx)

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
