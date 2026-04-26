/**
 * smoke.spec.ts — Zero-dependency smoke tests.
 *
 * These do NOT require the backend to be running — they exercise routing,
 * middleware redirects, form validation and the public auth pages.
 */

import { expect, test } from "@playwright/test"

test.describe("Public routes", () => {
  test("unauthenticated visit to /dashboard redirects to /login", async ({
    page,
  }) => {
    await page.goto("/dashboard")
    await expect(page).toHaveURL(/\/login(\?.*)?$/)
  })

  test("/login renders the authentication form", async ({ page }) => {
    await page.goto("/login")
    // Brand mark + wordmark renderuje <Logo /> sa role="img" + aria-label.
    await expect(
      page.getByRole("img", { name: /StudentPlus/i }).first()
    ).toBeVisible()
    await expect(
      page.getByRole("heading", { name: /Prijava/i })
    ).toBeVisible()
    await expect(page.getByLabel(/^Email$/i)).toBeVisible()
    await expect(page.getByLabel(/^Lozinka$/i)).toBeVisible()
    await expect(
      page.getByRole("button", { name: /Prijavite se/i })
    ).toBeVisible()
  })

  test("/register renders and rejects a non-university domain", async ({
    page,
  }) => {
    await page.goto("/register")
    await expect(
      page.getByRole("heading", { name: /Registracija/i })
    ).toBeVisible()

    await page.getByLabel("Ime", { exact: true }).fill("Test")
    await page.getByLabel("Prezime", { exact: true }).fill("Test")
    await page.getByLabel(/Studentski email/i).fill("someone@gmail.com")
    await page.getByLabel("Lozinka", { exact: true }).fill("ValidPass123!")
    await page.getByLabel(/Potvrda lozinke/i).fill("ValidPass123!")

    await page.getByRole("button", { name: /Kreiraj nalog/i }).click()

    await expect(
      page.getByText(
        /Registracija je dozvoljena samo sa studentskim email adresama/i
      )
    ).toBeVisible({ timeout: 10_000 })
  })

  test('"Zaboravili ste lozinku" link navigates to /forgot-password', async ({
    page,
  }) => {
    await page.goto("/login")
    await page.getByRole("link", { name: /Zaboravili ste lozinku/i }).click()
    await expect(page).toHaveURL(/\/forgot-password$/)
  })
})

test.describe("PWA manifest", () => {
  test("manifest file exists on disk and has required fields", async () => {
    const fs = await import("node:fs/promises")
    const path = await import("node:path")
    const file = path.resolve("public", "manifest.json")
    const content = await fs.readFile(file, "utf8")
    const manifest = JSON.parse(content) as {
      name: string
      short_name: string
      start_url: string
      display: string
      icons: Array<{ src: string; sizes: string; purpose?: string }>
    }
    expect(manifest.name).toBeTruthy()
    expect(manifest.short_name).toBeTruthy()
    expect(manifest.start_url).toBe("/dashboard")
    expect(manifest.display).toBe("standalone")
    expect(Array.isArray(manifest.icons)).toBe(true)
    expect(manifest.icons.length).toBeGreaterThanOrEqual(3)
    expect(manifest.icons.some((i) => i.purpose === "maskable")).toBe(true)
  })

  test("root layout references the manifest", async ({ page }) => {
    await page.goto("/login")
    const manifestHref = await page
      .locator('link[rel="manifest"]')
      .getAttribute("href")
    expect(manifestHref).toBe("/manifest.json")
  })
})
