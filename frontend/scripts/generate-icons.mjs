/**
 * generate-icons.mjs — One-shot icon generator for PWA.
 *
 * Renders the monogram "SP" on the theme color background into PNG files of
 * the sizes required by the manifest. Run once (or whenever the brand colors
 * change):
 *
 *   node scripts/generate-icons.mjs
 *
 * Output files (in public/icons/):
 *   - icon-192.png           (192x192, regular)
 *   - icon-512.png           (512x512, regular)
 *   - icon-maskable.png      (512x512, 80% safe zone for Android maskable)
 *   - apple-touch-icon.png   (180x180, iOS home-screen)
 *   - favicon-32.png         (32x32, browser tab)
 *   - favicon-16.png         (16x16, browser tab)
 */

import sharp from "sharp"
import { mkdir } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.resolve(__dirname, "..", "public", "icons")

const THEME_BG = "#0f172a"
const THEME_FG = "#ffffff"
const ACCENT = "#3b82f6"

function monogramSvg({ size, cornerRadius, padding }) {
  const innerSize = size - padding * 2
  const fontSize = Math.round(innerSize * 0.48)
  const underlineY = Math.round(size / 2 + fontSize * 0.42)
  const underlineX1 = Math.round(size / 2 - fontSize * 0.45)
  const underlineX2 = Math.round(size / 2 + fontSize * 0.45)
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" rx="${cornerRadius}" ry="${cornerRadius}" fill="${THEME_BG}"/>
  <text
    x="50%"
    y="50%"
    text-anchor="middle"
    dominant-baseline="central"
    font-family="Inter, Arial, Helvetica, sans-serif"
    font-weight="700"
    font-size="${fontSize}"
    fill="${THEME_FG}"
    letter-spacing="-${Math.round(fontSize * 0.04)}"
  >SP</text>
  <line x1="${underlineX1}" y1="${underlineY}" x2="${underlineX2}" y2="${underlineY}"
        stroke="${ACCENT}" stroke-width="${Math.max(3, Math.round(size * 0.015))}" stroke-linecap="round"/>
</svg>`
}

async function render(size, filename, opts = {}) {
  const cornerRadius = opts.maskable ? 0 : Math.round(size * 0.18)
  const padding = opts.maskable ? Math.round(size * 0.1) : 0
  const svg = monogramSvg({ size, cornerRadius, padding })
  const target = path.join(outDir, filename)
  await sharp(Buffer.from(svg))
    .png({ compressionLevel: 9 })
    .toFile(target)
  console.log(`  ✓ ${filename} (${size}x${size})`)
}

async function main() {
  await mkdir(outDir, { recursive: true })
  console.log(`Generating icons into ${outDir}`)
  await render(192, "icon-192.png")
  await render(512, "icon-512.png")
  await render(512, "icon-maskable.png", { maskable: true })
  await render(180, "apple-touch-icon.png")
  await render(32, "favicon-32.png")
  await render(16, "favicon-16.png")
  console.log("Done.")
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
