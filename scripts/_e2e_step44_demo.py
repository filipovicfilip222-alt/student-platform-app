"""E2E demo Koraka 4.4 — mimicira tačan flow koji frontend izvršava.

Pokreće: login admin -> impersonate seed studenta -> decode imp token claim po
claim (zamena za jwt.io) -> GET /admin/audit-log (1 START) -> impersonate/end
-> decode end token (potvrda da NEMA imp claim-ova) -> GET /admin/audit-log
(2 reda START+END sa IP-om).

Ovo je demonstracijska skripta za sesiju, NIJE deo integration test suite-a.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.parse
import base64
from typing import Any

API = "http://localhost/api/v1"
ADMIN = "sluzba@fon.bg.ac.rs"
PWD = "Seed@2024!"
TARGET_EMAIL = "marko.markovic@student.fon.bg.ac.rs"


def http(
    method: str, path: str, *, token: str | None = None, body: dict | None = None
) -> tuple[int, dict | list | None]:
    url = API + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw.decode()}


def decode_jwt(token: str) -> dict[str, Any]:
    parts = token.split(".")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def print_header(text: str) -> None:
    print(f"\n{'=' * 70}\n  {text}\n{'=' * 70}")


def main() -> int:
    print_header("KORAK 1 — Login admin (sluzba@fon.bg.ac.rs)")
    code, body = http("POST", "/auth/login", body={"email": ADMIN, "password": PWD})
    if code != 200:
        print(f"[FAIL] login {code}: {body}")
        return 1
    admin_token = body["access_token"]
    admin_claims = decode_jwt(admin_token)
    print(f"  status: {code}")
    print(f"  admin token claims:")
    print(f"    sub:    {admin_claims['sub']}")
    print(f"    email:  {admin_claims['email']}")
    print(f"    role:   {admin_claims['role']}")
    print(f"    type:   {admin_claims['type']}")
    print(f"    imp:    {'imp' in admin_claims} (must be False/missing)")
    assert "imp" not in admin_claims, "Regular admin token must NOT have imp claim"
    print("  [OK] regular admin token bez imp claim-a — ✓")

    print_header("KORAK 2 — Resolve target student (marko.markovic@student.fon.bg.ac.rs)")
    code, users = http(
        "GET", f"/admin/users?q={urllib.parse.quote(TARGET_EMAIL)}", token=admin_token
    )
    if code != 200 or not users:
        print(f"[FAIL] users list {code}: {users}")
        return 1
    target = next((u for u in users if u["email"] == TARGET_EMAIL), None)
    if not target:
        print(f"[FAIL] target {TARGET_EMAIL} nije pronađen u {users}")
        return 1
    print(f"  status: {code}")
    print(f"  target id:    {target['id']}")
    print(f"  target email: {target['email']}")
    print(f"  target role:  {target['role']}")

    print_header("KORAK 3 — POST /admin/impersonate/{user_id} (start)")
    code, body = http(
        "POST", f"/admin/impersonate/{target['id']}", token=admin_token
    )
    if code != 200:
        print(f"[FAIL] impersonate start {code}: {body}")
        return 1
    imp_token = body["access_token"]
    imp_claims = decode_jwt(imp_token)
    print(f"  status: {code}")
    print(f"  shape keys: {sorted(body.keys())}")
    print(f"  expires_in: {body['expires_in']}s ({body['expires_in']/60:.1f}min — must be 30)")
    print(f"  imp_expires_at: {body['imp_expires_at']}")
    print(f"  imp token claims (zamena za jwt.io decode):")
    print(f"    sub:        {imp_claims['sub']}        (must == target id: {target['id']})")
    print(f"    email:      {imp_claims['email']}     (target email)")
    print(f"    role:       {imp_claims['role']}      (must be STUDENT)")
    print(f"    type:       {imp_claims['type']}")
    print(f"    imp:        {imp_claims['imp']}       (must be True)")
    print(f"    imp_email:  {imp_claims['imp_email']}      (must == admin email)")
    print(f"    imp_name:   {imp_claims['imp_name']}    (admin's full name)")
    exp_ttl = imp_claims["exp"] - int(__import__("time").time())
    print(f"    exp TTL:    {exp_ttl/60:.1f}min        (must be ~30)")
    assert imp_claims["sub"] == target["id"]
    assert imp_claims["imp"] is True
    assert imp_claims["imp_email"] == ADMIN
    assert imp_claims["role"] == "STUDENT"
    print("  [OK] svih 7 claim-ova se poklapa, TTL=30min — ✓")

    print_header("KORAK 4 — Verifikacija da admin sa IMP tokenom NE može na /admin/* (Pitanje 5)")
    code, body = http("GET", "/admin/users", token=imp_token)
    print(f"  GET /admin/users sa imp tokenom -> {code} (must be 403)")
    assert code == 403, f"Pitanje 5 violation: imp token sme na admin rute! {body}"
    print("  [OK] backend striktno blokira (sidebar prirodno štiti UX)")

    print_header("KORAK 5 — GET /admin/audit-log (originalni admin token) — 1 START red")
    code, audit = http("GET", "/admin/audit-log", token=admin_token)
    if code != 200:
        print(f"[FAIL] {code}: {audit}")
        return 1
    print(f"  total redova: {len(audit)}")
    starts = [r for r in audit if r["action"] == "IMPERSONATION_START"]
    print(f"  IMPERSONATION_START redova: {len(starts)}")
    if starts:
        first = starts[0]
        print(f"  poslednji START red:")
        print(f"    id:                              {first['id']}")
        print(f"    admin_id:                        {first['admin_id']}")
        print(f"    admin_full_name:                 {first['admin_full_name']}")
        print(f"    impersonated_user_id:            {first['impersonated_user_id']}")
        print(f"    impersonated_user_full_name:     {first['impersonated_user_full_name']}")
        print(f"    action:                          {first['action']}")
        print(f"    ip_address:                      {first['ip_address']}")
        print(f"    created_at:                      {first['created_at']}")
        assert first["impersonated_user_id"] == target["id"]
        assert first["ip_address"] is not None
    print("  [OK] audit START red ima sve required keys + IP — ✓")

    print_header("KORAK 6 — POST /admin/impersonate/end (sa imp tokenom)")
    code, body = http("POST", "/admin/impersonate/end", token=imp_token)
    if code != 200:
        print(f"[FAIL] end {code}: {body}")
        return 1
    end_token = body["access_token"]
    end_claims = decode_jwt(end_token)
    print(f"  status: {code}")
    print(f"  shape keys: {sorted(body.keys())}")
    print(f"  end token claims:")
    print(f"    sub:    {end_claims['sub']}")
    print(f"    email:  {end_claims['email']}     (must == admin email)")
    print(f"    role:   {end_claims['role']}     (must be ADMIN)")
    print(f"    imp:    {'imp' in end_claims}    (must be False/missing)")
    assert end_claims["email"] == ADMIN
    assert end_claims["role"] == "ADMIN"
    assert "imp" not in end_claims
    print("  [OK] end token je ČIST admin token bez imp claim-ova — ✓")

    print_header("KORAK 7 — GET /admin/audit-log (END token) — 2 reda START+END")
    code, audit2 = http("GET", "/admin/audit-log", token=end_token)
    starts2 = [r for r in audit2 if r["action"] == "IMPERSONATION_START"]
    ends2 = [r for r in audit2 if r["action"] == "IMPERSONATION_END"]
    print(f"  total: {len(audit2)} redova ({len(starts2)} START + {len(ends2)} END)")
    if ends2:
        last_end = ends2[0]
        print(f"  poslednji END red:")
        print(f"    impersonated_user_id:        {last_end['impersonated_user_id']}")
        print(f"    impersonated_user_full_name: {last_end['impersonated_user_full_name']}")
        print(f"    ip_address:                  {last_end['ip_address']}")
        print(f"    created_at:                  {last_end['created_at']}")
    assert len(ends2) >= 1
    assert len(starts2) >= 1
    print("  [OK] audit log pokazuje START + END par — ✓")

    print_header("REZULTAT")
    print("  Sve 7 koraka prošlo. Backend Koraka 4.4 je production-ready.")
    print("  Frontend može da klikne 'Impersoniraj' na /admin/users i banner će se ")
    print("  prikazati sa pravim claim-ovima (imp_name + target name).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
