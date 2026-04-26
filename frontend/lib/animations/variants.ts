/**
 * variants.ts — Centralni framer-motion variants za StudentPlus.
 *
 * KORAK 9 (smanjen obim) — namerno NE definišemo svaku mikro-animaciju
 * inline po komponenti. Sve što je "page transition", "modal pop",
 * "stagger list" ili "press feedback" živi ovde da bismo:
 *   - imali konzistentne timing-e (220ms ease, 18ms stagger),
 *   - jednostavno disable-ovali u jednoj tački ako bude potrebno,
 *   - reduced-motion automatski poštovan (framer-motion to detektuje
 *     interno i smanjuje duration na 0 — globalni CSS override iz
 *     globals.css je dodatni safety net).
 *
 * Konvencija:
 *   - `*Variants` su Variants objekti koji idu na `<motion.div variants={...}>`
 *   - `*Transition` su transition specs (ease, duration) — opciono.
 */

import type { Transition, Variants } from "framer-motion"

// ─── Page transition (cross-fade) ──────────────────────────────────────
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
}

export const pageTransition: Transition = {
  duration: 0.22,
  ease: [0.32, 0.72, 0, 1],
}

// ─── Modal/Dialog spring ───────────────────────────────────────────────
export const modalVariants: Variants = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.96 },
}

export const modalTransition: Transition = {
  type: "spring",
  stiffness: 320,
  damping: 28,
  mass: 0.6,
}

// ─── Button press (scale 0.98) ─────────────────────────────────────────
export const pressTransition: Transition = {
  type: "spring",
  stiffness: 400,
  damping: 22,
}

// ─── Stagger list (notifikacije, dashboard cards) ──────────────────────
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.05,
    },
  },
}

export const staggerItem: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
}

export const staggerItemTransition: Transition = {
  duration: 0.24,
  ease: "easeOut",
}
