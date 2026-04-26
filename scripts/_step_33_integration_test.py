"""End-to-end integration test for KORAK 1 (Faza 3.3).

Runs against a live ``docker compose --profile app up`` stack on localhost.

Tests:
    1. Swagger /docs + OpenAPI exposes 9 appointment endpoints.
    2. Lead student GET /{id} → 200 with the full flat detail shape.
    3. Outsider student GET /{id} → 403.
    4. Upload PDF (≈1MB) → 201, presigned URL is reachable from outside Docker.
    5. Upload .exe → 422.
    6. Upload 6MB → 413.
    7. Outsider DELETE on lead's file → 403.
    8a. Send 21st chat message → 409 "Limit od 20 ...".
    8b. Send whitespace-only content → 422 "Poruka ne sme biti prazna.".
    9. Cancelled appointment → POST /messages → 410 "Chat nije dostupan...".

Designed to be idempotent — uses unique email suffixes per run so reruns
don't collide on the unique email constraint.
"""

from __future__ import annotations

import io
import os
import random
import string
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests

API = os.getenv("API_BASE", "http://localhost/api/v1")
ROOT = os.getenv("ROOT_BASE", "http://localhost")  # used for /openapi.json
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


# ── Setup ─────────────────────────────────────────────────────────────────────


def setup() -> dict[str, Any]:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix()

    lead_email, lead_pw = register_student(f"lead{suffix}")
    outsider_email, outsider_pw = register_student(f"out{suffix}")
    print(f"  registered lead     {lead_email}")
    print(f"  registered outsider {outsider_email}")

    prof_token = login(PROF_EMAIL, SEED_PASSWORD)
    lead_token = login(lead_email, lead_pw)
    outsider_token = login(outsider_email, outsider_pw)
    print("  logged in: prof, lead, outsider")

    slot_dt = "2027-04-01T10:00:00+00:00"
    r = post(
        "/professors/slots",
        token=prof_token,
        json={
            "slot_datetime": slot_dt,
            "duration_minutes": 30,
            "consultation_type": "UZIVO",
            "max_students": 1,
            "is_available": True,
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"create slot failed: {r.status_code} {r.text}")
    slot_id = r.json()["id"]
    print(f"  slot id     {slot_id}")

    r = post(
        "/students/appointments",
        token=lead_token,
        json={
            "slot_id": slot_id,
            "topic_category": "ISPIT",
            "description": "QA integration test booking — KORAK 1 acceptance.",
        },
    )
    if r.status_code != 200:
        raise RuntimeError(f"create appointment failed: {r.status_code} {r.text}")
    appt_id = r.json()["id"]
    appt_status = r.json()["status"]
    print(f"  appt id     {appt_id} (status={appt_status})")

    if appt_status != "APPROVED":
        ar = post(f"/professors/requests/{appt_id}/approve", token=prof_token)
        if ar.status_code != 200:
            raise RuntimeError(f"approve appt failed: {ar.status_code} {ar.text}")
        print(f"  approved by professor -> status APPROVED")

    return {
        "appt_id": appt_id,
        "slot_id": slot_id,
        "lead_token": lead_token,
        "outsider_token": outsider_token,
        "prof_token": prof_token,
        "lead_email": lead_email,
        "outsider_email": outsider_email,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_1_swagger(_: dict[str, Any]) -> None:
    print("\n=== TEST 1 — Swagger / OpenAPI exposes 9 appointment endpoints ===\n")
    r = requests.get(f"{ROOT}/openapi.json", timeout=15)
    spec = r.json()
    paths = [p for p in spec["paths"].keys() if p.startswith("/api/v1/appointments/")]
    method_count = sum(
        1
        for p in paths
        for m in spec["paths"][p].keys()
        if m in {"get", "post", "delete", "put", "patch"}
    )
    record(
        "Swagger exposes 9 appointment endpoints",
        "9 methods under /appointments/*",
        f"{method_count} methods on {len(paths)} paths",
        method_count == 9,
    )


def test_2_lead_detail(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 2 — Lead GET /{id} → 200 ===\n")
    r = get(f"/appointments/{ctx['appt_id']}", token=ctx["lead_token"])
    body = r.json() if r.status_code < 500 else r.text
    expected_fields = {
        "id", "slot_id", "professor_id", "lead_student_id", "subject_id",
        "topic_category", "description", "status", "consultation_type",
        "slot_datetime", "created_at", "is_group", "delegated_to",
        "rejection_reason", "chat_message_count", "file_count",
    }
    actual_fields = set(body.keys()) if isinstance(body, dict) else set()
    record(
        "Lead detail returns flat 16-field schema",
        "200, 16 fields exact match",
        f"{r.status_code}, fields={sorted(actual_fields)}",
        r.status_code == 200 and actual_fields == expected_fields,
    )


def test_3_outsider_403(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 3 — Outsider GET /{id} → 403 ===\n")
    r = get(f"/appointments/{ctx['appt_id']}", token=ctx["outsider_token"])
    record(
        "Outsider blocked at detail",
        "403, detail contains 'Nemate pristup'",
        f"{r.status_code} {r.text[:120]}",
        r.status_code == 403 and "Nemate pristup" in r.text,
    )


def _upload_file(
    appt_id: str,
    token: str,
    filename: str,
    content: bytes,
    mime_type: str,
) -> requests.Response:
    return post(
        f"/appointments/{appt_id}/files",
        token=token,
        files={"file": (filename, io.BytesIO(content), mime_type)},
    )


def test_4_upload_pdf(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 4 — Upload PDF + verify presigned URL is externally reachable ===\n")
    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + (b"A" * (1024 * 1024))  # ~1MB
    r = _upload_file(ctx["appt_id"], ctx["lead_token"], "qa_test.pdf", pdf, "application/pdf")
    if r.status_code != 201:
        record(
            "Upload PDF",
            "201 + presigned URL reachable",
            f"{r.status_code} {r.text[:200]}",
            False,
        )
        return
    body = r.json()
    url = body.get("download_url")
    file_id = body.get("id")
    ctx["uploaded_file_id"] = file_id
    if not url:
        record("Upload PDF presigned URL present", "non-empty download_url", "missing", False)
        return

    print(f"  presigned URL: {url[:120]}...")
    dl = requests.get(url, timeout=30)
    content_len = int(dl.headers.get("Content-Length", "-1"))
    expected_len = len(pdf)

    record(
        "Upload PDF + presigned URL downloads correct bytes",
        f"201 + GET {expected_len} bytes from URL",
        f"upload={r.status_code}, dl={dl.status_code}, content-length={content_len}",
        r.status_code == 201
        and dl.status_code == 200
        and content_len == expected_len
        and dl.content == pdf,
    )


def test_5_upload_exe(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 5 — Upload .exe → 422 ===\n")
    r = _upload_file(
        ctx["appt_id"],
        ctx["lead_token"],
        "malware.exe",
        b"MZ\x90\x00" + b"X" * 1024,
        "application/x-msdownload",
    )
    record(
        "Upload .exe rejected by MIME whitelist",
        "422, detail contains 'Nepodržan tip fajla'",
        f"{r.status_code} {r.text[:200]}",
        r.status_code == 422 and "Nepodržan tip fajla" in r.text,
    )


def test_6_upload_6mb(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 6 — Upload 6MB PDF → 413 ===\n")
    big = b"%PDF-1.4\n" + (b"B" * (6 * 1024 * 1024))
    r = _upload_file(ctx["appt_id"], ctx["lead_token"], "huge.pdf", big, "application/pdf")
    record(
        "Upload >5MB rejected with 413",
        "413, detail contains '5MB'",
        f"{r.status_code} {r.text[:200]}",
        r.status_code == 413 and "5MB" in r.text,
    )


def test_7_delete_other(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 7 — DELETE by non-uploader → 403 ===\n")
    file_id = ctx.get("uploaded_file_id")
    if not file_id:
        record("Delete non-uploader", "403", "skipped (no file uploaded)", False)
        return
    # The outsider isn't a participant → would be 403 at detail RBAC anyway.
    # Use the *professor* who has access via professor RBAC but is not the
    # uploader. They must still be blocked by the uploader-only check.
    r = delete(
        f"/appointments/{ctx['appt_id']}/files/{file_id}",
        token=ctx["prof_token"],
    )
    record(
        "Professor (non-uploader) cannot delete student's file",
        "403, detail contains 'samo fajlove koje ste sami otpremili'",
        f"{r.status_code} {r.text[:200]}",
        r.status_code == 403 and "samo fajlove koje ste sami otpremili" in r.text,
    )


def test_8_chat_limit(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 8a — 21st message → 409 ===\n")
    # Fresh appointment isolates chat counter from prior runs.
    appt_id = ctx["appt_id"]
    token = ctx["lead_token"]

    # Status of appt depends on professor's auto_approve. profesor1 default
    # auto_approve_recurring=true, so status should be APPROVED. If not, we
    # need to check.
    detail = get(f"/appointments/{appt_id}", token=token).json()
    if detail["status"] != "APPROVED":
        record(
            "Chat limit precondition (APPROVED)",
            "status=APPROVED",
            f"status={detail['status']}",
            False,
        )
        return

    sent_ok = 0
    last_err: tuple[int, str] | None = None
    for i in range(1, 22):
        r = post(
            f"/appointments/{appt_id}/messages",
            token=token,
            json={"content": f"msg {i}"},
        )
        if r.status_code == 201:
            sent_ok += 1
        else:
            last_err = (r.status_code, r.text[:200])
            break

    record(
        "21st chat message blocked at 20-message cap",
        "20 sent, 21st → 409 'Limit od 20'",
        f"sent={sent_ok}, last_err={last_err}",
        sent_ok == 20 and last_err is not None and last_err[0] == 409 and "Limit od 20" in last_err[1],
    )


def test_8b_whitespace(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 8b — whitespace-only message → 422 ===\n")
    # Make a fresh appointment so the 20-cap doesn't poison this case.
    suffix = rand_suffix()
    prof_token = ctx["prof_token"]
    r = post(
        "/professors/slots",
        token=prof_token,
        json={
            "slot_datetime": "2027-05-01T10:00:00+00:00",
            "duration_minutes": 30,
            "consultation_type": "UZIVO",
            "max_students": 1,
            "is_available": True,
        },
    )
    fresh_slot = r.json()["id"]
    fresh_lead_email, fresh_lead_pw = register_student(f"ws{suffix}")
    fresh_lead_token = login(fresh_lead_email, fresh_lead_pw)
    appt = post(
        "/students/appointments",
        token=fresh_lead_token,
        json={
            "slot_id": fresh_slot,
            "topic_category": "OSTALO",
            "description": "QA whitespace test booking minimum length.",
        },
    ).json()
    if appt.get("status") != "APPROVED":
        ar = post(f"/professors/requests/{appt['id']}/approve", token=prof_token)
        if ar.status_code != 200:
            record(
                "Whitespace precondition (approve)",
                "200",
                f"{ar.status_code} {ar.text[:200]}",
                False,
            )
            return
        appt = ar.json()

    # Pydantic will reject "" (min_length=1) but pass "   ". Service must 422.
    r = post(
        f"/appointments/{appt['id']}/messages",
        token=fresh_lead_token,
        json={"content": "   "},
    )
    record(
        "Whitespace-only chat content blocked post-strip",
        "422, detail contains 'Poruka ne sme biti prazna'",
        f"{r.status_code} {r.text[:200]}",
        r.status_code == 422 and "Poruka ne sme biti prazna" in r.text,
    )

    # Stash for test 9 (cancel + chat closed reason).
    ctx["fresh_appt_id"] = appt["id"]
    ctx["fresh_lead_token"] = fresh_lead_token


def test_9_cancelled_chat(ctx: dict[str, Any]) -> None:
    print("\n=== TEST 9 — CANCELLED appointment → POST /messages → 410 'Chat nije dostupan...' ===\n")
    appt_id = ctx.get("fresh_appt_id")
    token = ctx.get("fresh_lead_token")
    if not appt_id or not token:
        record(
            "Cancelled chat closed",
            "410 with NOT_APPROVED message",
            "skipped (no fresh appt)",
            False,
        )
        return

    cancel = delete(f"/students/appointments/{appt_id}", token=token)
    if cancel.status_code != 200:
        record(
            "Cancel precondition",
            "200 from DELETE /students/appointments/{id}",
            f"{cancel.status_code} {cancel.text[:200]}",
            False,
        )
        return

    r = post(
        f"/appointments/{appt_id}/messages",
        token=token,
        json={"content": "Trying to chat on a cancelled appt."},
    )
    record(
        "Cancelled appt chat returns NOT_APPROVED reason",
        "410, detail == 'Chat nije dostupan za ovaj termin.'",
        f"{r.status_code} {r.text[:200]}",
        r.status_code == 410 and "Chat nije dostupan za ovaj termin" in r.text,
    )


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        ctx = setup()
    except Exception as exc:  # noqa: BLE001
        print(f"\nSETUP FAILED: {exc}")
        return 2

    test_1_swagger(ctx)
    test_2_lead_detail(ctx)
    test_3_outsider_403(ctx)
    test_4_upload_pdf(ctx)
    test_5_upload_exe(ctx)
    test_6_upload_6mb(ctx)
    test_7_delete_other(ctx)
    test_8_chat_limit(ctx)
    test_8b_whitespace(ctx)
    test_9_cancelled_chat(ctx)

    print("\n=== SUMMARY ===\n")
    width = max(len(r.name) for r in RESULTS)
    for r in RESULTS:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name:<{width}}")
    failed = sum(1 for r in RESULTS if not r.passed)
    print(f"\n  {len(RESULTS) - failed}/{len(RESULTS)} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
