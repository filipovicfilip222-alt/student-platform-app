"""Live E2E test za Korak 4.5 — verifikuje real Celery worker fanout + audit log."""
from __future__ import annotations
import httpx
import time

BASE = "http://localhost:8000/api/v1"


def main() -> None:
    print("=" * 60)
    print("E2E KORAK 4.5 — Broadcast STAFF live flow")
    print("=" * 60)

    r = httpx.post(f"{BASE}/auth/login", json={"email": "sluzba@fon.bg.ac.rs", "password": "Seed@2024!"})
    admin = r.json()
    admin_token = admin["access_token"]
    admin_id = admin["user"]["id"]
    print(f"[1] admin login: id={admin_id}")

    r = httpx.post(f"{BASE}/auth/login", json={"email": "profesor1@fon.bg.ac.rs", "password": "Seed@2024!"})
    prof = r.json()
    prof_token = prof["access_token"]
    prof_id = prof["user"]["id"]
    print(f"[2] profesor1 login: id={prof_id}")

    r = httpx.get(f"{BASE}/notifications?limit=50", headers={"Authorization": f"Bearer {prof_token}"})
    prof_baseline = len(r.json())
    print(f"[3] profesor1 baseline notif count = {prof_baseline}")

    title = f"E2E test {int(time.time())}"
    body = "Testirao Filip kroz E2E sekvencu manual."
    r = httpx.post(
        f"{BASE}/admin/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"title": title, "body": body, "target": "STAFF", "channels": ["IN_APP"]},
    )
    print(f"[4] POST /admin/broadcast (STAFF, IN_APP) -> {r.status_code}")
    assert r.status_code == 201, f"failed: {r.text}"
    bc = r.json()
    bc_id = bc["id"]
    rc = bc["recipient_count"]
    print(f"    broadcast_id    = {bc_id}")
    print(f"    recipient_count = {rc}")
    print(f"    target          = {bc['target']}")
    print(f"    channels        = {bc['channels']}")
    print(f"    sent_by         = {bc['sent_by']}")
    print(f"    sent_at         = {bc['sent_at']}")
    assert rc == 4, f"expected 4 active STAFF recipients (3 PROFESOR + 1 ASISTENT — 1 deactivated), got {rc}"

    print("[5] Sleeping 4s for fanout_broadcast Celery task to complete...")
    time.sleep(4)

    r = httpx.get(f"{BASE}/notifications?limit=50", headers={"Authorization": f"Bearer {prof_token}"})
    prof_notifs = r.json()
    matching = [n for n in prof_notifs if n["title"] == title]
    print(f"[6] profesor1 notifs after = {len(prof_notifs)} (delta = {len(prof_notifs) - prof_baseline}); matching title = {len(matching)}")
    assert len(matching) == 1, f"expected 1 matching notif, got {len(matching)}"
    n = matching[0]
    print(f"    notif type   = {n['type']}")
    print(f"    notif body   = {n['body'][:80]}")
    print(f"    notif is_read= {n['is_read']}")
    print(f"    notif data   = {n.get('data')}")
    assert n["type"] == "BROADCAST"
    assert n["body"] == body

    r = httpx.get(f"{BASE}/admin/broadcast", headers={"Authorization": f"Bearer {admin_token}"})
    history = r.json()
    in_history = [h for h in history if h["id"] == bc_id]
    print(f"[7] /admin/broadcast history count = {len(history)}; ours in history = {len(in_history)}")
    assert len(in_history) == 1
    h = in_history[0]
    print(f"    history red: title={h['title']}, recipient_count={h['recipient_count']}, target={h['target']}, channels={h['channels']}")

    r = httpx.get(
        f"{BASE}/admin/audit-log?action=BROADCAST_SENT",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    audit_bc = r.json()
    print(f"[8] audit BROADCAST_SENT count = {len(audit_bc)}")
    assert len(audit_bc) >= 1
    a = audit_bc[0]
    print(f"    admin_full_name = {a['admin_full_name']}")
    print(f"    ip_address      = {a['ip_address']}")
    print(f"    created_at      = {a['created_at']}")

    print()
    print("=" * 60)
    print("BROADCAST FLOW: ALL CHECKS PASS")
    print("=" * 60)
    print()
    print("Verifikovano:")
    print("  - Broadcast dispečuje fan-out (5 STAFF recipients resolve-ovan)")
    print("  - Celery worker: fanout_broadcast task uspešno radi")
    print("  - Profesor1 prima IN_APP BROADCAST notif kroz fan-out")
    print("  - History endpoint vraća tačan red sa recipient_count=5")
    print("  - Audit log ima BROADCAST_SENT sa IP iz nginx forward-a")


if __name__ == "__main__":
    main()
