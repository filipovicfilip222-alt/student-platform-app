# E2E tests — Playwright

Phase 6.6 (ROADMAP 5.4) — end-to-end coverage for the parts of the platform
whose backend endpoints already exist (`auth.*`, `students.*`, `professors.*`).
Tests that depend on not-yet-implemented routers (admin, notifications,
appointments WS, search) are **deliberately omitted** for now — see
"Deferred specs" below.

## What works out of the box

- `smoke.spec.ts` — login / register / middleware redirect. **No backend
  required beyond what is needed to serve static pages.** Runs against
  `npm run dev` alone.
- `auth.spec.ts` — real login with the seeded student account → dashboard
  renders. Requires backend + seeded DB.
- `student-search.spec.ts` — student logs in, hits `/search`, validates
  filter UI and calls the real `/students/professors/search`.
- `professor-view.spec.ts` — student visits a seeded professor's profile
  and asserts FAQ accordion is rendered above the booking calendar
  (PRD UX rule).

## Deferred specs (tracked in Phase 6 final report)

| Spec | Blocker |
|------|---------|
| `student-booking.spec.ts` | Requires `POST /api/v1/students/appointments` end-to-end with a seeded slot and chat UI (ROADMAP 3.6). |
| `professor-approve.spec.ts` | Requires `GET/POST /api/v1/professors/requests/*` (ROADMAP 3.7). |
| `admin-bulk-import.spec.ts` | Requires `/api/v1/admin/*` router (ROADMAP 4.7). |
| `strike-system.spec.ts` | Requires strike endpoints + appointment cancel flow end-to-end (ROADMAP 3.4 + 3.6). |

These stubs should be written in the same PR where the corresponding backend
router lands (see `e2e/fixtures/backend-seed.ts` for the helpers they will
reuse).

## Prerequisites

1. Backend running at `http://localhost:8000` (override with env
   `NEXT_PUBLIC_API_URL`).
2. DB seeded with at least:
   - `student1@student.fon.bg.ac.rs` / `TestPass123!` (STUDENT)
   - one PROFESOR with a FAQ entry and at least one availability slot
3. First run only — install browsers:
   ```bash
   npx playwright install --with-deps chromium
   ```

## Seed script (not yet implemented)

There is **no** `scripts/seed_e2e.py` yet. If Stefan hasn't shipped one by
the time these specs are activated, a minimal implementation should:

```
# scripts/seed_e2e.py (PROPOSAL — NOT YET IMPLEMENTED)
# 1. Clear existing users/slots tagged as E2E_FIXTURE.
# 2. Create STUDENT: student1@student.fon.bg.ac.rs
# 3. Create PROFESOR: profesor1@fon.bg.ac.rs with:
#      - 1 FaqEntry(question, answer)
#      - 1 AvailabilitySlot(start_at=now+7d, duration=30m)
# 4. Commit.
```

Environment variables the fixtures read (defaults shown):

| Var | Default |
|-----|---------|
| `E2E_STUDENT_EMAIL` | `student1@student.fon.bg.ac.rs` |
| `E2E_STUDENT_PASSWORD` | `TestPass123!` |
| `E2E_PROFESSOR_EMAIL` | `profesor1@fon.bg.ac.rs` |
| `E2E_PROFESSOR_PASSWORD` | `TestPass123!` |
| `E2E_ADMIN_EMAIL` | `admin@fon.bg.ac.rs` |
| `E2E_ADMIN_PASSWORD` | `TestPass123!` |
| `E2E_BASE_URL` | `http://localhost:3000` |

## Reports

- HTML report lands in `playwright-report/` (auto-opens on failure locally).
- Videos and traces are retained only for failed tests.
- Both `playwright-report/` and `test-results/` are gitignored.
