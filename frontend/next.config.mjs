import withPWAInit from "@ducanh2912/next-pwa"

/**
 * PWA configuration — ROADMAP 5.2 / Phase 6.3.
 *
 * - register: true, skipWaiting: true → new SW activates on next navigation.
 * - disable in development (SW complicates HMR and the cache hides live edits).
 * - reloadOnOnline: true → page refetches when connectivity returns.
 *
 * Runtime caching strategy (see workboxOptions.runtimeCaching):
 *   • /_next/static/* and /icons/*  → CacheFirst (immutable assets)
 *   • /api/v1/*                     → NetworkFirst w/ 3s timeout, fallback to cache
 *   • page navigations              → NetworkFirst (default from preset is fine)
 *   • Google Fonts                  → StaleWhileRevalidate
 *
 * NOTE: We chose next-pwa runtime caching instead of TanStack Query
 * persistQueryClient so the service worker can serve cached /api/v1/* responses
 * even when the JS bundle itself isn't hydrated yet (e.g. cold-start offline
 * launch of /my-appointments). The query client still dedupes within a session.
 */
const withPWA = withPWAInit({
  dest: "public",
  register: true,
  disable: process.env.NODE_ENV === "development",
  reloadOnOnline: true,
  cacheOnFrontEndNav: true,
  aheadOfTimeCaching: true,
  workboxOptions: {
    skipWaiting: true,
    clientsClaim: true,
    runtimeCaching: [
      {
        urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i,
        handler: "CacheFirst",
        options: {
          cacheName: "google-fonts",
          expiration: { maxEntries: 4, maxAgeSeconds: 365 * 24 * 60 * 60 },
        },
      },
      {
        urlPattern: /\/_next\/static\/.*/i,
        handler: "CacheFirst",
        options: {
          cacheName: "next-static",
          expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 },
        },
      },
      {
        urlPattern: /\/icons\/.*\.(?:png|svg|webp)/i,
        handler: "CacheFirst",
        options: {
          cacheName: "pwa-icons",
          expiration: { maxEntries: 20, maxAgeSeconds: 30 * 24 * 60 * 60 },
        },
      },
      {
        urlPattern: /\.(?:png|jpg|jpeg|gif|webp|svg|ico)$/i,
        handler: "StaleWhileRevalidate",
        options: {
          cacheName: "images",
          expiration: { maxEntries: 64, maxAgeSeconds: 7 * 24 * 60 * 60 },
        },
      },
      {
        // Read-only GETs for offline archive view of /my-appointments and /notifications.
        urlPattern: ({ url, sameOrigin, request }) =>
          request.method === "GET" &&
          (sameOrigin || /\/api\/v1\//.test(url.pathname)) &&
          /\/api\/v1\/(students\/appointments|notifications)/.test(url.pathname),
        handler: "NetworkFirst",
        options: {
          cacheName: "api-archive",
          networkTimeoutSeconds: 3,
          expiration: { maxEntries: 40, maxAgeSeconds: 24 * 60 * 60 },
          cacheableResponse: { statuses: [200] },
        },
      },
      {
        urlPattern: ({ request }) => request.mode === "navigate",
        handler: "NetworkFirst",
        options: {
          cacheName: "pages",
          networkTimeoutSeconds: 3,
          expiration: { maxEntries: 32, maxAgeSeconds: 24 * 60 * 60 },
        },
      },
    ],
  },
})

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "9000",
        pathname: "/professor-avatars/**",
      },
      {
        protocol: "https",
        hostname: "*.fon.bg.ac.rs",
      },
      {
        protocol: "https",
        hostname: "*.etf.bg.ac.rs",
      },
    ],
  },
  reactStrictMode: true,
}

export default withPWA(nextConfig)
