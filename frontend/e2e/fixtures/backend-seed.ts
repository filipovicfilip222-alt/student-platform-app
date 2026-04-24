/**
 * backend-seed.ts — Helpers for deferred specs that need backend-created
 * fixtures (slots, appointments, strikes).
 *
 * Right now these only hit the endpoints that already exist (search, slot
 * listings). The TODO blocks mark API calls that will become live once the
 * corresponding backend modules ship (ROADMAP 3.6 / 3.7 / 4.7).
 */

import type { APIRequestContext } from "@playwright/test"

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"

export async function getFirstProfessorId(
  request: APIRequestContext,
  accessToken: string
): Promise<string> {
  const response = await request.get(`${API_BASE}/students/professors/search`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok()) {
    throw new Error(
      `Seed lookup failed: GET /students/professors/search returned ${response.status()}. ` +
        "Is the backend running and the DB seeded?"
    )
  }
  const payload = (await response.json()) as {
    items?: Array<{ id: string }>
  }
  const items = payload.items ?? []
  if (items.length === 0) {
    throw new Error(
      "Seed lookup returned zero professors — run your backend seed script first."
    )
  }
  return items[0]!.id
}

// TODO: enable when ROADMAP 3.6 appointments router lands.
// export async function createSeedAppointment(...) { ... }

// TODO: enable when ROADMAP 3.7 requests inbox lands.
// export async function approveFirstPendingRequest(...) { ... }

// TODO: enable when ROADMAP 4.7 admin router lands.
// export async function bulkImportUsers(...) { ... }
