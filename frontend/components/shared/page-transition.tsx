/**
 * page-transition.tsx — Subtle cross-fade između ruta u Next 14 App Router-u.
 *
 * KORAK 9 — namerno smanjenog obima:
 *   - Trajanje 220ms — primetno ali ne usporava nav tokom prezentacije.
 *   - `mode="wait"` — sledeća stranica čeka da prethodna izađe; tako se
 *     izbegavaju duple skrol-pozicije.
 *   - `key={pathname}` — ključ tera AnimatePresence da otkrije promenu
 *     rute (Next ne unmount-uje children sam po sebi za isti layout).
 *
 * Reduced motion: framer-motion automatski svodi duration na ~0ms
 * kada `prefers-reduced-motion: reduce` (vidi MotionConfig docs).
 * Dodatni CSS guard u globals.css je belt-and-suspenders.
 */

"use client"

import { usePathname } from "next/navigation"
import { AnimatePresence, MotionConfig, motion } from "framer-motion"
import type { ReactNode } from "react"

import { pageTransition, pageVariants } from "@/lib/animations/variants"

export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  return (
    <MotionConfig reducedMotion="user">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={pathname}
          variants={pageVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={pageTransition}
          className="contents"
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </MotionConfig>
  )
}
