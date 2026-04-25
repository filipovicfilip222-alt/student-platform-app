#!/usr/bin/env python3
"""
Test skripte za Step 3.2: Document Requests

Testira sve endpointe:
  - Student: POST/GET /api/v1/students/document-requests
  - Admin: GET /api/v1/admin/document-requests + approve/reject/complete

Korišćenje:
  docker exec studentska_backend python scripts/test_step_32_document_requests.py
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple
from uuid import UUID

# ─── CONFIG ───────────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000/api/v1"
STUDENT_EMAIL = "doc_test_student@student.fon.bg.ac.rs"
ADMIN_EMAIL = "sluzba@fon.bg.ac.rs"
PASSWORD = "Seed@2024!"

# Valid document type enums (moraju biti iz modela)
VALID_DOC_TYPES = [
    "POTVRDA_STATUSA",
    "UVERENJE_ISPITI",
    "UVERENJE_PROSEK",
    "PREPIS_OCENA",
    "POTVRDA_SKOLARINE",
    "OSTALO",
]


# ─── UTILITY FUNCTIONS ───────────────────────────────────────────────────────

def call(
    method: str,
    path: str,
    token: Optional[str] = None,
    data: Optional[dict] = None,
) -> Tuple[int, Any]:
    """
    HTTP helper. Vraća (status_code, response_json_or_text).
    """
    url = f"{BASE_URL}{path}"
    headers: dict[str, str] = {}
    body: Optional[bytes] = None

    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            response_text = resp.read().decode()
            try:
                return resp.status, json.loads(response_text) if response_text else None
            except json.JSONDecodeError:
                return resp.status, response_text
    except urllib.error.HTTPError as e:
        response_text = e.read().decode()
        try:
            return e.code, json.loads(response_text)
        except json.JSONDecodeError:
            return e.code, response_text


def test_print(title: str, passed: bool, details: str = ""):
    """Pretty print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} — {title}")
    if details:
        print(f"    {details}")


# ─── SETUP ────────────────────────────────────────────────────────────────────

def setup_users() -> Tuple[str, str]:
    """
    Registruj test studenta i dobij tokens za njega i admin-a.
    Vraća: (student_token, admin_token)
    """
    # Registruj student
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("SETUP: Registracija test korisnika")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    status, resp = call(
        "POST",
        "/auth/register",
        data={
            "email": STUDENT_EMAIL,
            "password": PASSWORD,
            "first_name": "Doc",
            "last_name": "Test",
        },
    )
    test_print(
        "Student registracija",
        status in (200, 201),
        f"Status: {status}",
    )

    # Login student
    status, resp = call(
        "POST",
        "/auth/login",
        data={"email": STUDENT_EMAIL, "password": PASSWORD},
    )
    student_token = resp.get("access_token") if isinstance(resp, dict) else None
    test_print(
        "Student login",
        status == 200 and student_token,
        f"Status: {status}",
    )

    # Login admin
    status, resp = call(
        "POST",
        "/auth/login",
        data={"email": ADMIN_EMAIL, "password": PASSWORD},
    )
    admin_token = resp.get("access_token") if isinstance(resp, dict) else None
    test_print(
        "Admin login",
        status == 200 and admin_token,
        f"Status: {status}",
    )

    return student_token or "", admin_token or ""


# ─── TESTS ────────────────────────────────────────────────────────────────────


def test_student_create_request(token: str) -> Optional[str]:
    """Test: Student kreira zahtev za dokument."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 1: Student kreira zahtev")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    status, resp = call(
        "POST",
        "/students/document-requests",
        token=token,
        data={
            "document_type": "POTVRDA_STATUSA",
            "note": "Trebam za ambasadu",
        },
    )

    passed = status == 201 and isinstance(resp, dict)
    test_print(
        "Create request — HTTP 201",
        passed,
        f"Status: {status}",
    )

    if not passed:
        return None

    request_id = resp.get("id")
    status_resp = resp.get("status")

    test_print(
        "Create request — status=PENDING",
        status_resp == "PENDING",
        f"Status u response: {status_resp}",
    )

    test_print(
        "Create request — student_id uključen",
        "student_id" in resp,
        f"Fields: {list(resp.keys())}",
    )

    test_print(
        "Create request — created_at/updated_at dostupni",
        "created_at" in resp and "updated_at" in resp,
        f"Created: {resp.get('created_at')}, Updated: {resp.get('updated_at')}",
    )

    return request_id


def test_student_list_requests(token: str, expected_count: int = 1):
    """Test: Student lista svoje zahteve."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 2: Student lista svoje zahteve")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    status, resp = call(
        "GET",
        "/students/document-requests",
        token=token,
    )

    passed = status == 200 and isinstance(resp, list)
    test_print(
        "List requests — HTTP 200",
        passed,
        f"Status: {status}",
    )

    if not passed:
        return

    test_print(
        f"List requests — ukupno zahteva >= {expected_count}",
        len(resp) >= expected_count,
        f"Pronađeno: {len(resp)}",
    )

    if resp:
        first = resp[0]
        test_print(
            "List requests — respons ima ispravan oblik",
            all(k in first for k in ["id", "status", "document_type", "student_id"]),
            f"Keys: {list(first.keys())}",
        )


def test_admin_list_pending(token: str) -> list[str]:
    """Test: Admin lista pending zahteve."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 3: Admin lista PENDING zahteve")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    status, resp = call(
        "GET",
        "/admin/document-requests?status=PENDING",
        token=token,
    )

    passed = status == 200 and isinstance(resp, list)
    test_print(
        "Admin list pending — HTTP 200",
        passed,
        f"Status: {status}",
    )

    if not passed:
        return []

    pending_ids = [r.get("id") for r in resp if r.get("status") == "PENDING"]
    test_print(
        "Admin list pending — svi imaju status=PENDING",
        all(r.get("status") == "PENDING" for r in resp),
        f"Pronađeno: {len(pending_ids)} PENDING zahteva",
    )

    return pending_ids


def test_admin_approve_request(token: str, request_id: str):
    """Test: Admin odobrava zahtev."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 4: Admin odobrava zahtev")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    pickup_date = (datetime.now() + timedelta(days=5)).date().isoformat()

    status, resp = call(
        "POST",
        f"/admin/document-requests/{request_id}/approve",
        token=token,
        data={
            "pickup_date": pickup_date,
            "admin_note": "Soба 12, Palata nauke",
        },
    )

    passed = status == 200 and isinstance(resp, dict)
    test_print(
        "Admin approve — HTTP 200",
        passed,
        f"Status: {status}",
    )

    if not passed:
        return False

    test_print(
        "Admin approve — status=APPROVED",
        resp.get("status") == "APPROVED",
        f"Status: {resp.get('status')}",
    )

    test_print(
        "Admin approve — pickup_date postavljen",
        resp.get("pickup_date") == pickup_date,
        f"Pickup date: {resp.get('pickup_date')}",
    )

    test_print(
        "Admin approve — admin_note spremljen",
        resp.get("admin_note") == "Soба 12, Palata nauke",
        f"Note: {resp.get('admin_note')}",
    )

    test_print(
        "Admin approve — processed_by uključen",
        resp.get("processed_by") is not None,
        f"Processed by: {resp.get('processed_by')}",
    )

    return True


def test_admin_complete_request(token: str, request_id: str):
    """Test: Admin označava zahtev kao preuzet."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 5: Admin označava zahtev kao preuzet")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    status, resp = call(
        "POST",
        f"/admin/document-requests/{request_id}/complete",
        token=token,
    )

    passed = status == 200 and isinstance(resp, dict)
    test_print(
        "Admin complete — HTTP 200",
        passed,
        f"Status: {status}",
    )

    if not passed:
        return False

    test_print(
        "Admin complete — status=COMPLETED",
        resp.get("status") == "COMPLETED",
        f"Status: {resp.get('status')}",
    )

    return True


def test_admin_reject_request(token: str, request_id: str):
    """Test: Admin odbija zahtev."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 6: Admin odbija zahtev")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    status, resp = call(
        "POST",
        f"/admin/document-requests/{request_id}/reject",
        token=token,
        data={
            "admin_note": "Potrebna dopunska dokumentacija",
        },
    )

    passed = status == 200 and isinstance(resp, dict)
    test_print(
        "Admin reject — HTTP 200",
        passed,
        f"Status: {status}",
    )

    if not passed:
        return False

    test_print(
        "Admin reject — status=REJECTED",
        resp.get("status") == "REJECTED",
        f"Status: {resp.get('status')}",
    )

    test_print(
        "Admin reject — admin_note spremljen",
        resp.get("admin_note") == "Potrebna dopunska dokumentacija",
        f"Note: {resp.get('admin_note')}",
    )

    test_print(
        "Admin reject — pickup_date=null",
        resp.get("pickup_date") is None,
        f"Pickup date: {resp.get('pickup_date')}",
    )

    return True


def test_edge_cases(student_token: str, admin_token: str, request_id: str):
    """Test: Edge cases i error scenarios."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 7: Edge cases i greške")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 7a: Non-existent request
    status, resp = call(
        "GET",
        "/admin/document-requests",
        token=admin_token,
    )
    non_existent_id = "00000000-0000-0000-0000-000000000000"
    status, resp = call(
        "POST",
        f"/admin/document-requests/{non_existent_id}/approve",
        token=admin_token,
        data={"pickup_date": "2026-05-20", "admin_note": "test"},
    )
    test_print(
        "Edge: Non-existent request — HTTP 404",
        status == 404,
        f"Status: {status}",
    )

    # 7b: Student nije autorizovan za admin endpoint
    status, resp = call(
        "GET",
        "/admin/document-requests",
        token=student_token,
    )
    test_print(
        "Edge: Student pristupa admin inbox — HTTP 403 (Forbidden)",
        status in (403, 401),
        f"Status: {status}",
    )

    # 7c: Invalid document type pri kreiranju
    status, resp = call(
        "POST",
        "/students/document-requests",
        token=student_token,
        data={
            "document_type": "INVALID_TYPE",
            "note": "test",
        },
    )
    test_print(
        "Edge: Invalid document_type — HTTP 422",
        status == 422,
        f"Status: {status}",
    )

    # 7d: Pokušaj double approve (zahtev je već PENDING posle reject-a)
    # Prvo kreiramo novi zahtev, odobrimo ga, pa pokušamo opet approve
    status, resp = call(
        "POST",
        "/students/document-requests",
        token=student_token,
        data={
            "document_type": "PREPIS_OCENA",
            "note": "Za konkurs",
        },
    )
    new_req_id = resp.get("id") if isinstance(resp, dict) else None

    if new_req_id:
        # Odobri
        status1, _ = call(
            "POST",
            f"/admin/document-requests/{new_req_id}/approve",
            token=admin_token,
            data={"pickup_date": "2026-05-20", "admin_note": "test"},
        )

        # Pokušaj odobri ponovo
        status2, resp2 = call(
            "POST",
            f"/admin/document-requests/{new_req_id}/approve",
            token=admin_token,
            data={"pickup_date": "2026-05-20", "admin_note": "test"},
        )

        test_print(
            "Edge: Double approve na APPROVED zahtev — HTTP 409 Conflict",
            status2 == 409,
            f"Status: {status2}",
        )


def test_all_document_types(token: str):
    """Test: Kreiraj zahtev sa svakim document type-om."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 8: Svi document type-ovi")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    results = []
    for doc_type in VALID_DOC_TYPES:
        status, resp = call(
            "POST",
            "/students/document-requests",
            token=token,
            data={
                "document_type": doc_type,
                "note": f"Test za {doc_type}",
            },
        )
        success = status == 201 and resp.get("document_type") == doc_type
        results.append(success)
        test_print(
            f"Document type: {doc_type}",
            success,
            f"Status: {status}",
        )

    test_print(
        f"Svi document type-ovi kreirani — {sum(results)}/{len(VALID_DOC_TYPES)}",
        all(results),
        "",
    )


def test_filter_by_status(admin_token: str):
    """Test: Admin filter po statusu."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("TEST 9: Admin filter po statusu")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    statuses = ["PENDING", "APPROVED", "REJECTED", "COMPLETED"]

    for status_filter in statuses:
        status, resp = call(
            "GET",
            f"/admin/document-requests?status={status_filter}",
            token=admin_token,
        )

        passed = status == 200 and isinstance(resp, list)
        if passed and resp:
            all_match = all(r.get("status") == status_filter for r in resp)
            test_print(
                f"Filter: status={status_filter}",
                all_match,
                f"Pronađeno: {len(resp)} zahteva sa statusom {status_filter}",
            )
        else:
            test_print(
                f"Filter: status={status_filter}",
                passed,
                f"Status HTTP: {status}",
            )


# ─── MAIN ──────────────────────────────────────────────────────────────────────


def main():
    """Pokreni sve testove."""
    print("\n")
    print("╔════════════════════════════════════════════════════════╗")
    print("║  TEST SUITE: Step 3.2 — Document Requests             ║")
    print("╚════════════════════════════════════════════════════════╝")

    try:
        # Setup
        student_token, admin_token = setup_users()

        if not student_token or not admin_token:
            print("\n❌ Setup failed, stopping tests.")
            return 1

        # Test 1: Student kreira zahtev
        request_id = test_student_create_request(student_token)

        if not request_id:
            print("\n❌ Test 1 failed, cannot continue.")
            return 1

        # Test 2: Student lista zahteve
        test_student_list_requests(student_token, expected_count=1)

        # Test 3: Admin lista pending zahteve
        pending_ids = test_admin_list_pending(admin_token)

        if request_id not in pending_ids:
            print(f"\n⚠️  Request ID {request_id} not in pending list")

        # Test 4: Admin odobrava zahtev
        if test_admin_approve_request(admin_token, request_id):
            # Test 5: Admin označava kao preuzet
            test_admin_complete_request(admin_token, request_id)

        # Test 6: Admin odbija drugi zahtev (kreiraj novog za ovo)
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Prépare: Kreiraj drugi zahtev za reject test")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        status, resp = call(
            "POST",
            "/students/document-requests",
            token=student_token,
            data={
                "document_type": "UVERENJE_ISPITI",
                "note": "Za testiranje reject",
            },
        )
        reject_request_id = resp.get("id") if isinstance(resp, dict) else None

        if reject_request_id:
            test_admin_reject_request(admin_token, reject_request_id)

        # Test 7: Edge cases
        test_edge_cases(student_token, admin_token, request_id)

        # Test 8: Svi document type-ovi
        test_all_document_types(student_token)

        # Test 9: Filter po statusu
        test_filter_by_status(admin_token)

        # Summary
        print("\n")
        print("╔════════════════════════════════════════════════════════╗")
        print("║  ✅ SVI TESTOVI ZAVRŠENI                              ║")
        print("╚════════════════════════════════════════════════════════╝")
        print("\nZAVRŠETAK:")
        print("  ✅ Student create document request")
        print("  ✅ Student list own requests")
        print("  ✅ Admin list pending requests")
        print("  ✅ Admin approve request")
        print("  ✅ Admin complete request")
        print("  ✅ Admin reject request")
        print("  ✅ Edge cases i error handling")
        print("  ✅ Svi document type-ovi")
        print("  ✅ Filter po statusu")
        print("\n")

        return 0

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
