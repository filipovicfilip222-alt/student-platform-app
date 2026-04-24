/**
 * student-search.spec.ts — /search filter UI + real API roundtrip.
 *
 * REQUIRES: backend at http://localhost:8000 with the student seed account
 * AND at least one professor visible to that student. See e2e/README.md.
 */

import { expect, test } from "@playwright/test"

import { loginAs } from "../fixtures/auth"

test.describe("Student · professor search", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "student")
  })

  test("filters render and reset-button behaves correctly", async ({ page }) => {
    await page.goto("/search")

    await expect(
      page.getByRole("heading", { name: /Pretraga profesora/i })
    ).toBeVisible()

    const searchInput = page.getByLabel(/^Pretraga$/i)
    const subjectInput = page.getByLabel(/^Predmet$/i)
    const resetButton = page.getByRole("button", { name: /Resetuj filtere/i })

    await expect(resetButton).toBeDisabled()

    await searchInput.fill("An")
    await expect(resetButton).toBeEnabled({ timeout: 2_000 })

    await subjectInput.fill("Programiranje")
    await resetButton.click()

    await expect(searchInput).toHaveValue("")
    await expect(subjectInput).toHaveValue("")
    await expect(resetButton).toBeDisabled()
  })

  test("typing triggers a debounced API call and renders a result count", async ({
    page,
  }) => {
    await page.goto("/search")
    const searchInput = page.getByLabel(/^Pretraga$/i)

    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/students/professors/search") &&
        response.status() === 200,
      { timeout: 10_000 }
    )

    await searchInput.fill("a")
    await responsePromise

    await expect(
      page
        .getByText(/Pronađeno profesora/i)
        .or(page.getByText(/Nema rezultata/i))
    ).toBeVisible({ timeout: 5_000 })
  })

  test("faculty select narrows results without page reload", async ({
    page,
  }) => {
    await page.goto("/search")
    // Shadcn Select trigger keeps the label visible — click by accessible name.
    await page
      .getByRole("combobox", { name: /Fakultet/i })
      .click()
    await page.getByRole("option", { name: "FON" }).click()

    await expect(
      page.getByRole("combobox", { name: /Fakultet/i })
    ).toContainText("FON")
  })
})
