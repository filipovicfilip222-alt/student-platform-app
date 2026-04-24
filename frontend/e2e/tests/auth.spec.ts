/**
 * auth.spec.ts — Real login round-trip.
 *
 * REQUIRES: backend at http://localhost:8000 with seeded users. See
 * e2e/README.md.
 */

import { expect, test } from "@playwright/test"

import { loginAs, seedCredentials } from "../fixtures/auth"

test.describe("Authentication", () => {
  test("empty submission shows field-level validation", async ({ page }) => {
    await page.goto("/login")
    await page.getByRole("button", { name: /Prijavite se/i }).click()
    await expect(page.getByText("Email je obavezan.")).toBeVisible()
    await expect(page.getByText("Lozinka je obavezna.")).toBeVisible()
  })

  test("malformed email is rejected client-side", async ({ page }) => {
    await page.goto("/login")
    await page.getByLabel(/^Email$/i).fill("not-an-email")
    await page.getByLabel(/^Lozinka$/i).fill("anything")
    await page.getByRole("button", { name: /Prijavite se/i }).click()
    await expect(
      page.getByText(/Unesite ispravnu email adresu/i)
    ).toBeVisible()
  })

  test("wrong credentials surface the API error message", async ({ page }) => {
    await page.goto("/login")
    await page
      .getByLabel(/^Email$/i)
      .fill(seedCredentials.student.email)
    await page.getByLabel(/^Lozinka$/i).fill("definitelyWrongPass!!!")
    await page.getByRole("button", { name: /Prijavite se/i }).click()

    // The axios interceptor passes the backend's `detail` through to the form.
    // We don't assert exact copy because it depends on the backend locale.
    await expect(page).toHaveURL(/\/login/)
    await expect(
      page
        .locator('div[class*="bg-destructive"]')
        .or(page.getByText(/Greška pri prijavi/i))
    ).toBeVisible({ timeout: 10_000 })
  })

  test("seeded student logs in and lands on /dashboard", async ({ page }) => {
    await loginAs(page, "student")
    await expect(page).toHaveURL(/\/dashboard$/)
  })

  test("logout clears the session and redirects to /login", async ({
    page,
  }) => {
    await loginAs(page, "student")

    // UserMenu button is labelled "Korisnički meni" in top-bar.
    await page.getByRole("button", { name: /Korisnički meni/i }).click()
    await page.getByRole("menuitem", { name: /Odjavi se/i }).click()

    await expect(page).toHaveURL(/\/login(\?.*)?$/, { timeout: 10_000 })

    // Navigating back to a protected page must bounce to /login again.
    await page.goto("/dashboard")
    await expect(page).toHaveURL(/\/login(\?.*)?$/)
  })
})
