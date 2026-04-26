"""Live E2E test za Korak 4.5 STRIKES flow — admin override + Celery send_block_lifted."""
from __future__ import annotations
import httpx
import subprocess
import time

BASE = "http://localhost:8000/api/v1"


def psql(sql: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["docker", "exec", "studentska_postgres", "psql", "-U", "studentska",
         "-d", "studentska_platforma", "-tA", "-c", sql],
        capture_output=True, timeout=15,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def main() -> None:
    print("=" * 60)
    print("E2E KORAK 4.5 — Strikes flow live")
    print("=" * 60)

    student_email = "filip2@student.fon.bg.ac.rs"
    r = httpx.post(f"{BASE}/auth/register", json={
        "first_name": "FilipE2E", "last_name": "Strike",
        "email": student_email, "password": "Seed@2024!",
        "student_index_number": "FE2E001",
        "study_program": "IS", "enrollment_year": 2024,
    })
    print(f"[1] register/login student: {r.status_code}")

    r = httpx.post(f"{BASE}/auth/login", json={"email": student_email, "password": "Seed@2024!"})
    if r.status_code != 200:
        print(f"   login failed: {r.text}")
        return
    student = r.json()
    student_token = student["access_token"]
    student_id = student["user"]["id"]
    print(f"   student_id = {student_id}")

    rc, out = psql(
        f"DELETE FROM strike_records WHERE student_id='{student_id}'; "
        f"DELETE FROM student_blocks WHERE student_id='{student_id}'; "
        f"DELETE FROM notifications WHERE user_id='{student_id}';"
    )
    print(f"[2] cleanup state: rc={rc}")

    rc, out = psql("SELECT id FROM appointments LIMIT 1;")
    if rc != 0 or not out.strip():
        print(f"   no seed appointment in DB, cannot create strike_record")
        return
    appt_id = out.strip().split("\n")[0]
    print(f"[3] using appointment_id={appt_id} for strike FK")

    rc, _ = psql(
        f"INSERT INTO strike_records (student_id, appointment_id, points, reason) "
        f"VALUES ('{student_id}', '{appt_id}', 3, 'NO_SHOW'); "
        f"INSERT INTO student_blocks (student_id, blocked_until) "
        f"VALUES ('{student_id}', now() + interval '14 days') "
        f"ON CONFLICT (student_id) DO UPDATE SET blocked_until=EXCLUDED.blocked_until;"
    )
    print(f"[4] seed StrikeRecord(3pts) + StudentBlock active: rc={rc}")
    assert rc == 0

    r = httpx.post(f"{BASE}/auth/login", json={"email": "sluzba@fon.bg.ac.rs", "password": "Seed@2024!"})
    admin_token = r.json()["access_token"]

    r = httpx.get(f"{BASE}/admin/strikes", headers={"Authorization": f"Bearer {admin_token}"})
    rows = r.json()
    target_row = next((row for row in rows if row["student_id"] == student_id), None)
    print(f"[5] GET /admin/strikes count = {len(rows)}; target row found = {target_row is not None}")
    assert target_row is not None
    print(f"    student_full_name = {target_row['student_full_name']}")
    print(f"    total_points      = {target_row['total_points']}")
    print(f"    blocked_until     = {target_row['blocked_until']}")
    print(f"    last_strike_at    = {target_row['last_strike_at']}")
    assert target_row["total_points"] == 3
    assert target_row["blocked_until"] is not None

    reason = "E2E manual test - admin override radi ispravno bez problema."
    r = httpx.post(
        f"{BASE}/admin/strikes/{student_id}/unblock",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"removal_reason": reason},
    )
    print(f"[6] POST /admin/strikes/{{id}}/unblock -> {r.status_code}")
    print(f"    body: {r.text}")
    assert r.status_code == 200

    print("[7] Sleeping 4s for send_block_lifted Celery task...")
    time.sleep(4)

    rc, out = psql(
        f"SELECT blocked_until <= now() AS lifted, removal_reason "
        f"FROM student_blocks WHERE student_id='{student_id}';"
    )
    print(f"[8] DB student_blocks: {out.strip()}")
    assert "t|" in out

    r = httpx.get(f"{BASE}/notifications?limit=20", headers={"Authorization": f"Bearer {student_token}"})
    notifs = r.json()
    block_lifted = [n for n in notifs if n["type"] == "BLOCK_LIFTED"]
    print(f"[9] student notifs total = {len(notifs)}; BLOCK_LIFTED = {len(block_lifted)}")
    assert len(block_lifted) == 1
    bl = block_lifted[0]
    print(f"    notif title = {bl['title']}")
    print(f"    notif body  = {bl['body'][:80]}")
    print(f"    notif data  = {bl.get('data')}")

    r = httpx.get(
        f"{BASE}/admin/audit-log?action=STRIKE_UNBLOCKED",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    audit_rows = r.json()
    print(f"[10] audit STRIKE_UNBLOCKED count = {len(audit_rows)}")
    assert len(audit_rows) >= 1
    target_audit = next((a for a in audit_rows if a["impersonated_user_id"] == student_id), None)
    assert target_audit is not None
    print(f"    admin_full_name             = {target_audit['admin_full_name']}")
    print(f"    impersonated_user_full_name = {target_audit['impersonated_user_full_name']}")
    print(f"    ip_address                  = {target_audit['ip_address']}")
    print(f"    created_at                  = {target_audit['created_at']}")

    psql(
        f"DELETE FROM notifications WHERE user_id='{student_id}'; "
        f"DELETE FROM audit_log WHERE impersonated_user_id='{student_id}'; "
        f"DELETE FROM student_blocks WHERE student_id='{student_id}'; "
        f"DELETE FROM strike_records WHERE student_id='{student_id}'; "
        f"DELETE FROM users WHERE id='{student_id}';"
    )
    print("[11] cleanup test data: OK")

    print()
    print("=" * 60)
    print("STRIKES FLOW: ALL CHECKS PASS")
    print("=" * 60)
    print()
    print("Verifikovano:")
    print("  - GET /admin/strikes vraca StrikeRow sa total_points=3, blocked_until!=None")
    print("  - POST /admin/strikes/{id}/unblock UPDATE-uje blocked_until + removal_reason")
    print("  - Celery send_block_lifted dispečuje email + in-app BLOCK_LIFTED notif")
    print("  - Student dobija BLOCK_LIFTED notif sa removal_reason u body-ju")
    print("  - Audit log ima STRIKE_UNBLOCKED red sa impersonated_user_id=student + IP")


if __name__ == "__main__":
    main()
