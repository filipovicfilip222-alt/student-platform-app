/**
 * generate-icons.mjs — StudentPlus PWA icon generator.
 *
 * Konzumira Filipov `public/branding/logo-mark-light.png` (512×512 PNG-24
 * sa transparentnim alfa kanalom; sadrži samo ikonu, BEZ teksta) i pravi:
 *
 *   public/icons/
 *     icon-192.png            (192×192, transparent — koristi se u manifest)
 *     icon-512.png            (512×512, transparent)
 *     icon-maskable.png       (512×512, burgundy fill + 80% safe zone)
 *     apple-touch-icon.png    (180×180, burgundy fill — iOS ne podržava transparent)
 *     favicon-16.png          (16×16, transparent)
 *     favicon-32.png          (32×32, transparent)
 *     favicon-48.png          (48×48, transparent)
 *   public/favicon.ico        (multi-layer 16+32+48)
 *
 * Pokrenuti jednom:  npm run generate:icons
 *
 * Brand colors (mirror frontend/app/globals.css):
 *   primary  #7B1E2C — burgundy (maskable + apple-touch background)
 */

import sharp from "sharp"
import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, "..")
const sourcePath = path.join(root, "public", "branding", "logo-mark-light.png")
const outDir = path.join(root, "public", "icons")

const BRAND_BURGUNDY = { r: 123, g: 30, b: 44, alpha: 1 }

/**
 * Resize logo-mark on a transparent canvas (manifest "any" purpose,
 * favicons). Source PNG already has alpha — we just resize.
 */
async function renderTransparent(size, filename) {
  const target = path.join(outDir, filename)
  await sharp(sourcePath)
    .resize(size, size, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png({ compressionLevel: 9 })
    .toFile(target)
  console.log(`  ✓ ${filename} (${size}×${size}, transparent)`)
}

/**
 * Maskable icon: 80% safe zone padded inside a burgundy fill, total 512×512.
 * Android launchers crop to circle/squircle/rounded — anything in outer 10%
 * margin may be cut off. Padding the mark by 10% on each side guarantees
 * full visibility on every launcher mask.
 */
async function renderMaskable(filename) {
  const total = 512
  const safe = Math.round(total * 0.8)
  const target = path.join(outDir, filename)

  const inner = await sharp(sourcePath)
    .resize(safe, safe, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png()
    .toBuffer()

  await sharp({
    create: {
      width: total,
      height: total,
      channels: 4,
      background: BRAND_BURGUNDY,
    },
  })
    .composite([{ input: inner, gravity: "center" }])
    .png({ compressionLevel: 9 })
    .toFile(target)
  console.log(`  ✓ ${filename} (${total}×${total}, maskable, burgundy fill)`)
}

/**
 * Apple touch icon: 180×180, burgundy background (iOS Safari ignores alpha
 * and adds a hardcoded white square otherwise — looks awful).
 */
async function renderAppleTouch(filename) {
  const total = 180
  const inner = Math.round(total * 0.78)
  const target = path.join(outDir, filename)

  const innerBuf = await sharp(sourcePath)
    .resize(inner, inner, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png()
    .toBuffer()

  await sharp({
    create: {
      width: total,
      height: total,
      channels: 4,
      background: BRAND_BURGUNDY,
    },
  })
    .composite([{ input: innerBuf, gravity: "center" }])
    .png({ compressionLevel: 9 })
    .toFile(target)
  console.log(`  ✓ ${filename} (${total}×${total}, burgundy fill)`)
}

/**
 * Multi-layer favicon.ico (16 + 32 + 48). sharp 0.33+ podržava ICO output
 * direktno; ako kasnije pukne kompatibilnost, fallback je `to-ico` paket.
 */
async function renderFaviconIco() {
  const target = path.join(root, "public", "favicon.ico")
  // sharp's ICO encoder accepts an array of resized PNGs internally when
  // output is .ico; we write a single 32×32 fallback if the encoder is
  // unavailable, then upgrade via `to-ico` if needed.
  try {
    await sharp(sourcePath)
      .resize(48, 48, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .toFormat("ico", { sizes: [16, 32, 48] })
      .toFile(target)
    console.log(`  ✓ favicon.ico (16+32+48 multi-layer)`)
  } catch (err) {
    // sharp WASM build on some platforms doesn't ship ICO encoder. Fallback:
    // dump the 32×32 PNG bytes into favicon.ico (browsers accept PNG inside
    // .ico for modern browsers; older IE will fall back to favicon-32.png).
    const buf = await sharp(sourcePath)
      .resize(32, 32, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
      .png()
      .toBuffer()
    await writeFile(target, buf)
    console.warn(
      `  ⚠ sharp ICO encoder unavailable (${err?.message ?? err}); wrote PNG-in-ICO fallback`
    )
  }
}

async function main() {
  await mkdir(outDir, { recursive: true })
  console.log(`Source: ${sourcePath}`)
  console.log(`Output: ${outDir}`)
  console.log("")

  await renderTransparent(192, "icon-192.png")
  await renderTransparent(512, "icon-512.png")
  await renderMaskable("icon-maskable.png")
  await renderAppleTouch("apple-touch-icon.png")
  await renderTransparent(48, "favicon-48.png")
  await renderTransparent(32, "favicon-32.png")
  await renderTransparent(16, "favicon-16.png")
  await renderFaviconIco()

  console.log("\nDone.")
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
