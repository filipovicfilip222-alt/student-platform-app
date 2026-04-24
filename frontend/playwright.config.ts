/**
 * playwright.config.ts — Phase 6.6 E2E configuration.
 *
 * The suite assumes the **backend is already running** at
 *   http://localhost:8000
 * with the DB seeded. See e2e/README.md for instructions. The config below
 * only manages the Next.js dev server (`npm run dev`) — it does NOT spin up
 * Postgres / Redis / the FastAPI server.
 *
 * Run:
 *   npm run test:e2e         # headless on Chromium + Pixel 5
 *   npm run test:e2e:ui      # Playwright UI mode
 *   npm run test:e2e:headed  # headed browser for debugging
 */

import { defineConfig, devices } from "@playwright/test"

const PORT = Number(process.env.E2E_PORT ?? 3000)
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`

export default defineConfig({
  testDir: "./e2e/tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "on-failure" }]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "sr-Latn-RS",
    timezoneId: "Europe/Belgrade",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
})
