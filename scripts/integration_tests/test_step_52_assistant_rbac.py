"""End-to-end integration test za KORAK 3 Prompta 2 — Asistent RBAC ojačan.

Acceptance kriterijumi (CURSOR_PROMPT_2_DEMO_READY.md §3.3 + PRD §1.3):

  - ``crm_service._assert_assistant_can_access_student`` blokira pristup
    studentima za predmete kojima asistent NIJE dodeljen (i kojima
    direktno nije delegiran kroz appointment).
  - Asistent dodeljen subjA (prof1) ima pristup studentu s1 koji je
    imao termin za subjA: LIST/POST/PUT 200/201/200.
  - Asistent NEMA pristup studentu s2 koji je imao termin za subjB
    (asistent nije dodeljen subjB): LIST 403, POST 403.
  - Profesor uvek prolazi (unconditional access za svoje predmete) —
    LIST za s1 → 200.

6 testova: 3 RBAC + 3 happy path.

Run protiv žive ``docker compose --profile app up`` instance.

Cleanup: brišu se sve test-kreirane CRM beleške, appointment-i,
slotovi, subjects i `subject_assistants` veze (po ``[I-52 SMOKE]``
opisima i `code` prefiksom).
"""

from __future__ import annotations

import os
import random
import string
import sys
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

PROF1_EMAIL = os.getenv("PROF1_EMAIL", "profesor1@fon.bg.ac.rs")
PROF2_EMAIL = os.getenv("PROF2_EMAIL", "profesor2@fon.bg.ac.rs")
ASISTENT_EMAIL = os.getenv("ASISTENT_EMAIL", "asistent1@fon.bg.ac.rs")
SEED_PASSWORD = os.getenv("SEED_PASSWORD", "Seed@2024!")

SMOKE_TAG = "i52-rbac"
SUBJ_CODE_PREFIX = "I52"


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


def put(path: str, *, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.put(f"{API}{path}", headers=headers, timeout=30, **kwargs)


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


def register_student(suffix: str) -> tuple[str, str, str]:
    email = f"qa_p52_{suffix}@student.fon.bg.ac.rs"
    password = "TestPass1!"
    r = post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "QA52",
            "last_name": f"P52-{suffix}",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"register {email} failed: {r.status_code} {r.text}")
    user_id = r.json().get("id") or r.json().get("user", {}).get("id")
    if not user_id:
        # Login da bi smo dobili user_id ako nije u register response.
        token, uid = login(email, password)
        return email, password, uid
    return email, password, user_id


# ── Backend ergonomics (docker exec helpers) ─────────────────────────────────


def _docker_run_python(py: str, *, timeout: int = 45) -> tuple[int, str, str]:
    import subprocess

    cmd = ["docker", "exec", BACKEND_CONTAINER, "python", "-c", py]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return (
        proc.returncode,
        proc.stdout.decode(errors="replace").strip(),
        proc.stderr.decode(errors="replace").strip(),
    )


def get_professor_id_for_user(user_id: str) -> str:
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


def create_subject_with_appointment(
    *,
    professor_id: str,
    student_id: str,
    subject_code: str,
    subject_name: str,
    assistant_user_id: str | None,
    slot_datetime_utc: str,
) -> tuple[str, str, str]:
    """Direktno INSERT Subject + slot + APPROVED appointment.

    Ako je dat ``assistant_user_id``, takođe upiše red u
    ``subject_assistants`` (M2M veza koju koristi
    ``_assert_assistant_can_access_student``).

    Vraća (subject_id, slot_id, appointment_id).
    """
    py = (
        "import asyncio\n"
        "from datetime import datetime\n"
        "from sqlalchemy import insert\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.models.subject import Subject, subject_assistants\n"
        "from app.models.availability_slot import AvailabilitySlot\n"
        "from app.models.appointment import Appointment\n"
        "from app.models.enums import AppointmentStatus, ConsultationType, TopicCategory, Faculty\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        "        subj = Subject(\n"
        f"            name='{subject_name}',\n"
        f"            code='{subject_code}',\n"
        "            faculty=Faculty.FON,\n"
        f"            professor_id='{professor_id}',\n"
        "        )\n"
        "        db.add(subj)\n"
        "        await db.flush()\n"
    )
    if assistant_user_id:
        py += (
            "        await db.execute(insert(subject_assistants).values("
            f"subject_id=subj.id, assistant_id='{assistant_user_id}'))\n"
        )
    py += (
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
        "            subject_id=subj.id,\n"
        "            topic_category=TopicCategory.OSTALO,\n"
        f"            description='I-52 smoke termin {SMOKE_TAG}',\n"
        "            status=AppointmentStatus.APPROVED,\n"
        "            consultation_type=ConsultationType.UZIVO,\n"
        "        )\n"
        "        db.add(appt)\n"
        "        await db.flush()\n"
        "        await db.commit()\n"
        "        print(f'CREATE_RESULT:{subj.id} {slot.id} {appt.id}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py)
    if rc != 0:
        raise RuntimeError(f"create_subject_with_appointment failed: rc={rc} stderr={err}")
    for line in out.splitlines():
        if line.startswith("CREATE_RESULT:"):
            subj_id, slot_id, appt_id = line.split(":", 1)[1].strip().split()
            return subj_id, slot_id, appt_id
    raise RuntimeError(f"CREATE_RESULT not in output: {out}")


def cleanup_smoke(*, suffix: str) -> None:
    """Briše sve I-52 smoke artefakte: appointmente, slotove, subjects,
    subject_assistants (cascade), CRM beleške koje su pravljene preko
    test-a (po sadržaju)."""
    py = (
        "import asyncio\n"
        "from sqlalchemy import select, delete\n"
        "from app.core.database import AsyncSessionLocal\n"
        "from app.models.appointment import Appointment\n"
        "from app.models.availability_slot import AvailabilitySlot\n"
        "from app.models.crm_note import CrmNote\n"
        "from app.models.subject import Subject\n"
        "async def main():\n"
        "    async with AsyncSessionLocal() as db:\n"
        f"        appts = (await db.execute(select(Appointment.id, Appointment.slot_id, Appointment.subject_id).where(Appointment.description.like('%{SMOKE_TAG}%')))).all()\n"
        "        slot_ids = list({row[1] for row in appts})\n"
        "        subj_ids = list({row[2] for row in appts if row[2] is not None})\n"
        f"        n_appt = (await db.execute(delete(Appointment).where(Appointment.description.like('%{SMOKE_TAG}%')))).rowcount\n"
        f"        n_notes = (await db.execute(delete(CrmNote).where(CrmNote.content.like('%{suffix}%')))).rowcount\n"
        "        for sid in slot_ids:\n"
        "            await db.execute(delete(AvailabilitySlot).where(AvailabilitySlot.id == sid))\n"
        f"        n_subj = (await db.execute(delete(Subject).where(Subject.code.like('%{suffix}%')))).rowcount\n"
        "        await db.commit()\n"
        "        print(f'CLEANUP_RESULT:appts={n_appt} notes={n_notes} subjects={n_subj}')\n"
        "asyncio.run(main())\n"
    )
    rc, out, err = _docker_run_python(py, timeout=60)
    if rc != 0:
        print(f"  [warn] cleanup failed: rc={rc} stderr={err}")
        return
    for line in out.splitlines():
        if line.startswith("CLEANUP_RESULT:"):
            print(f"  [cleanup] {line.split(':', 1)[1].strip()}")


# ── Setup ────────────────────────────────────────────────────────────────────


def setup(ctx: dict[str, Any]) -> None:
    print("\n=== SETUP ===\n")
    suffix = rand_suffix(6)
    ctx["suffix"] = suffix

    # Login profesori i asistent.
    p1_token, p1_user_id = login(PROF1_EMAIL, SEED_PASSWORD)
    p2_token, p2_user_id = login(PROF2_EMAIL, SEED_PASSWORD)
    asi_token, asi_user_id = login(ASISTENT_EMAIL, SEED_PASSWORD)
    print(f"  prof1={PROF1_EMAIL} user={p1_user_id}")
    print(f"  prof2={PROF2_EMAIL} user={p2_user_id}")
    print(f"  asistent={ASISTENT_EMAIL} user={asi_user_id}")

    p1_prof_id = get_professor_id_for_user(p1_user_id)
    p2_prof_id = get_professor_id_for_user(p2_user_id)
    print(f"  prof1.Professor.id={p1_prof_id}")
    print(f"  prof2.Professor.id={p2_prof_id}")

    # Registracija 2 studenta.
    s1_email, _, s1_id = register_student("s1" + suffix)
    s2_email, _, s2_id = register_student("s2" + suffix)
    print(f"  s1 {s1_email} id={s1_id}")
    print(f"  s2 {s2_email} id={s2_id}")

    # Vremenski slotovi za appointment-e (juče da ne smetaju live booking-u).
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    slot_a_dt = yesterday.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    slot_b_dt = yesterday.replace(hour=12, minute=0, second=0, microsecond=0).isoformat()

    # SubjA (prof1, asistent dodeljen) + appointment s1 ↔ subjA.
    subj_a_id, slot_a_id, appt_a_id = create_subject_with_appointment(
        professor_id=p1_prof_id,
        student_id=s1_id,
        subject_code=f"{SUBJ_CODE_PREFIX}A-{suffix}",
        subject_name=f"I-52 SubjA {suffix}",
        assistant_user_id=asi_user_id,
        slot_datetime_utc=slot_a_dt,
    )
    # SubjB (prof2, asistent NIJE dodeljen) + appointment s2 ↔ subjB.
    subj_b_id, slot_b_id, appt_b_id = create_subject_with_appointment(
        professor_id=p2_prof_id,
        student_id=s2_id,
        subject_code=f"{SUBJ_CODE_PREFIX}B-{suffix}",
        subject_name=f"I-52 SubjB {suffix}",
        assistant_user_id=None,
        slot_datetime_utc=slot_b_dt,
    )
    print(f"  subjA={subj_a_id[:8]} apptA={appt_a_id[:8]}")
    print(f"  subjB={subj_b_id[:8]} apptB={appt_b_id[:8]}")

    ctx.update(
        {
            "p1_token": p1_token,
            "p1_user_id": p1_user_id,
            "p1_prof_id": p1_prof_id,
            "p2_token": p2_token,
            "p2_prof_id": p2_prof_id,
            "asi_token": asi_token,
            "asi_user_id": asi_user_id,
            "s1_id": s1_id,
            "s2_id": s2_id,
            "subj_a_id": subj_a_id,
            "subj_b_id": subj_b_id,
            "appt_a_id": appt_a_id,
            "appt_b_id": appt_b_id,
        }
    )


# ── Tests ────────────────────────────────────────────────────────────────────


def test_1_assistant_blocked_listing_unrelated_student(ctx: dict[str, Any]) -> None:
    """[RBAC] Asistent NEMA pristup CRM listingu za studenta na predmetu
    kojem nije dodeljen (s2 ↔ subjB)."""
    print("\n=== TEST 1 [RBAC] — Asistent ne može LIST CRM za studenta van svojih predmeta ===\n")
    r = get(f"/professors/crm/{ctx['s2_id']}", token=ctx["asi_token"])
    record(
        "Asistent LIST /crm/{s2_id} → 403 Forbidden",
        "status_code=403 (subject mismatch)",
        f"status={r.status_code} body={r.text[:200]}",
        r.status_code == 403,
    )


def test_2_assistant_blocked_creating_for_unrelated_student(ctx: dict[str, Any]) -> None:
    """[RBAC] Asistent ne može da pravi CRM beleške za studenta van
    svojih predmeta."""
    print("\n=== TEST 2 [RBAC] — Asistent ne može POST CRM za studenta van svojih predmeta ===\n")
    r = post(
        f"/professors/crm/{ctx['s2_id']}",
        token=ctx["asi_token"],
        json={"content": f"I-52 [BLOCK] asistent → s2 {ctx['suffix']}"},
    )
    record(
        "Asistent POST /crm/{s2_id} → 403 Forbidden",
        "status_code=403 (subject mismatch)",
        f"status={r.status_code} body={r.text[:200]}",
        r.status_code == 403,
    )


def test_3_professor_unconditional_access(ctx: dict[str, Any]) -> None:
    """[RBAC] Profesor uvek prolazi (PRD §1.3): LIST za svog studenta
    s1 → 200 (bez bilo kakve subject_assistants provere)."""
    print("\n=== TEST 3 [RBAC] — Profesor unconditional pristup CRM ===\n")
    r = get(f"/professors/crm/{ctx['s1_id']}", token=ctx["p1_token"])
    record(
        "Profesor1 LIST /crm/{s1_id} → 200 OK",
        "status_code=200 (unconditional pristup za svoj predmet)",
        f"status={r.status_code} items={len(r.json()) if r.status_code == 200 else '-'}",
        r.status_code == 200,
    )


def test_4_assistant_can_list_for_assigned_student(ctx: dict[str, Any]) -> None:
    """[HAPPY] Asistent dodeljen subjA može LIST CRM za s1 (koji ima
    appointment za subjA)."""
    print("\n=== TEST 4 [HAPPY] — Asistent LIST CRM za studenta na njegovom predmetu ===\n")
    r = get(f"/professors/crm/{ctx['s1_id']}", token=ctx["asi_token"])
    record(
        "Asistent LIST /crm/{s1_id} → 200 OK",
        "status_code=200 (asistent dodeljen subjA, s1 ima appt za subjA)",
        f"status={r.status_code} items={len(r.json()) if r.status_code == 200 else '-'}",
        r.status_code == 200,
    )


def test_5_assistant_can_create_note(ctx: dict[str, Any]) -> None:
    """[HAPPY] Asistent može POST CRM beleške za s1 (ima access kroz
    subjA), nota se kreira pod profesorom subjA (prof1)."""
    print("\n=== TEST 5 [HAPPY] — Asistent POST CRM za studenta na njegovom predmetu ===\n")
    r = post(
        f"/professors/crm/{ctx['s1_id']}",
        token=ctx["asi_token"],
        json={"content": f"I-52 [HAPPY] asistent kreira CRM beleske za s1 {ctx['suffix']}"},
    )
    note_id = ""
    note_prof_id = ""
    if r.status_code == 201:
        body = r.json()
        note_id = body.get("id", "")
        note_prof_id = body.get("professor_id", "")
        ctx["note_id"] = note_id

    expected_prof = ctx["p1_prof_id"]
    professor_ok = note_prof_id == expected_prof
    record(
        "Asistent POST /crm/{s1_id} → 201 sa professor_id=prof1",
        f"status_code=201, professor_id={expected_prof[:8]}…",
        f"status={r.status_code} note_id={note_id[:8]}… professor_id={note_prof_id[:8]}…",
        r.status_code == 201 and professor_ok,
    )


def test_6_assistant_can_update_note(ctx: dict[str, Any]) -> None:
    """[HAPPY] Asistent može PUT (izmena) postojećoj CRM beleški za
    studenta kojem ima access. Provera prolazi i kroz update_note."""
    print("\n=== TEST 6 [HAPPY] — Asistent PUT izmena CRM beleške ===\n")
    note_id = ctx.get("note_id")
    if not note_id:
        record(
            "Asistent PUT /crm/{note_id} → 200",
            "200 OK",
            "note_id missing iz prethodnog testa",
            False,
        )
        return
    r = put(
        f"/professors/crm/{note_id}",
        token=ctx["asi_token"],
        json={"content": f"I-52 [HAPPY] asistent EDIT-uje CRM beleske {ctx['suffix']}"},
    )
    new_content = ""
    if r.status_code == 200:
        new_content = r.json().get("content", "")

    record(
        "Asistent PUT /crm/{note_id} → 200 sa novim content-om",
        "status_code=200, content sadrži 'EDIT-uje'",
        f"status={r.status_code} content_has_edit={'EDIT-uje' in new_content}",
        r.status_code == 200 and "EDIT-uje" in new_content,
    )


# ── Runner ───────────────────────────────────────────────────────────────────


def main() -> int:
    ctx: dict[str, Any] = {}
    try:
        setup(ctx)
        test_1_assistant_blocked_listing_unrelated_student(ctx)
        test_2_assistant_blocked_creating_for_unrelated_student(ctx)
        test_3_professor_unconditional_access(ctx)
        test_4_assistant_can_list_for_assigned_student(ctx)
        test_5_assistant_can_create_note(ctx)
        test_6_assistant_can_update_note(ctx)
    finally:
        cleanup_smoke(suffix=ctx.get("suffix", ""))

    print("\n=== SUMMARY ===\n")
    width = max((len(r.name) for r in RESULTS), default=40)
    for r in RESULTS:
        icon = "PASS" if r.passed else "FAIL"
        print(f"  [{icon}] {r.name.ljust(width)}")
    passed = sum(1 for r in RESULTS if r.passed)
    print(f"\n  {passed}/{len(RESULTS)} passed.")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
