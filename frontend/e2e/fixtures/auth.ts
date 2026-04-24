/**
 * auth.ts — Shared login helpers for E2E specs.
 *
 * Uses the REAL backend (POST /api/v1/auth/login). Fail fast with a clear
 * message if the backend is unreachable or the seed account is missing —
 * that is almost always the cause of a red test in CI.
 */

import { expect, type Page } from "@playwright/test"

type Seed = "student" | "professor" | "admin"

const SEED: Record<Seed, { email: string; password: string }> = {
  student: {
    email:
      process.env.E2E_STUDENT_EMAIL ?? "student1@student.fon.bg.ac.rs",
    password: process.env.E2E_STUDENT_PASSWORD ?? "TestPass123!",
  },
  professor: {
    email: process.env.E2E_PROFESSOR_EMAIL ?? "profesor1@fon.bg.ac.rs",
    password: process.env.E2E_PROFESSOR_PASSWORD ?? "TestPass123!",
  },
  admin: {
    email: process.env.E2E_ADMIN_EMAIL ?? "admin@fon.bg.ac.rs",
    password: process.env.E2E_ADMIN_PASSWORD ?? "TestPass123!",
  },
}

/**
 * Log in via the UI so that Zustand, cookies and the axios interceptor all
 * share the same post-login state. Returns the page for chaining.
 *
 * We navigate to `/login` regardless of the current URL — middleware would
 * redirect anyway on protected routes.
 */
export async function loginAs(page: Page, role: Seed): Promise<Page> {
  const { email, password } = SEED[role]
  await page.goto("/login")

  await page.getByLabel(/^Email$/i).fill(email)
  await page.getByLabel(/^Lozinka$/i).fill(password)
  await page.getByRole("button", { name: /Prijavite se/i }).click()

  await expect(page).toHaveURL(
    role === "admin"
      ? /\/admin$/
      : role === "professor"
        ? /\/professor\/dashboard$/
        : /\/dashboard$/,
    { timeout: 15_000 }
  )
  return page
}

export const seedCredentials = SEED
