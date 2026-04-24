/**
 * professor-view.spec.ts — /professor/[id] layout invariant.
 *
 * PRD mandates that the FAQ accordion sits **above** the booking calendar —
 * this test guards that rule against accidental regression.
 *
 * REQUIRES: backend at http://localhost:8000, student seed login, and at
 * least one seeded PROFESOR. See e2e/README.md.
 */

import { expect, test } from "@playwright/test"

import { loginAs } from "../fixtures/auth"
import { getFirstProfessorId } from "../fixtures/backend-seed"

test.describe("Student · professor profile layout", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "student")
  })

  test("FAQ accordion is rendered above the booking calendar (DOM order)", async ({
    page,
    request,
  }) => {
    // Grab any professor from the seed DB and build the URL directly —
    // this avoids depending on the /search flow staying stable.
    const accessToken = await page.evaluate(() => {
      const raw = (
        window as unknown as {
          __zustand_auth_debug?: { access_token?: string }
        }
      ).__zustand_auth_debug?.access_token
      return raw ?? null
    })
    // Fallback: if the store debug handle isn't exposed, read the token
    // from the "auth" Zustand snapshot in window (test helper lives on
    // the page). If neither works, use the API request context as a last
    // resort — but `loginAs` already guarantees an authenticated session.
    const id = await page
      .evaluate(async () => {
        const response = await fetch(
          "/api/v1/students/professors/search",
          { credentials: "include" }
        )
        if (!response.ok) return null
        const payload = await response.json()
        return (payload?.items?.[0]?.id as string | undefined) ?? null
      })
      .then(async (pageId) => {
        if (pageId) return pageId
        if (!accessToken) {
          throw new Error(
            "No access token available. Ensure loginAs() succeeded."
          )
        }
        return getFirstProfessorId(request, accessToken)
      })

    await page.goto(`/professor/${id}`)

    // Booking calendar has the heading "Dostupni termini" — wait for it.
    const calendarHeading = page.getByRole("heading", {
      name: /Dostupni termini/i,
    })
    await expect(calendarHeading).toBeVisible({ timeout: 15_000 })

    // The FAQ card only renders when the professor has entries. If the
    // seeded professor has FAQs, enforce DOM order; otherwise flag
    // softly so the test still acts as a smoke check.
    const faqHeading = page.getByRole("heading", {
      name: /Često postavljena pitanja/i,
    })
    const faqCount = await faqHeading.count()
    test.skip(
      faqCount === 0,
      "Seeded professor has no FAQ entries — see e2e/README.md for expected seed data."
    )

    // Assert FAQ appears before the calendar in the DOM.
    const order = await page.evaluate(() => {
      const nodes = Array.from(document.querySelectorAll("h2, h3"))
      const faqIdx = nodes.findIndex((n) =>
        /Često postavljena pitanja/i.test(n.textContent ?? "")
      )
      const calIdx = nodes.findIndex((n) =>
        /Dostupni termini/i.test(n.textContent ?? "")
      )
      return { faqIdx, calIdx }
    })
    expect(order.faqIdx).toBeGreaterThanOrEqual(0)
    expect(order.calIdx).toBeGreaterThanOrEqual(0)
    expect(order.faqIdx).toBeLessThan(order.calIdx)
  })
})
