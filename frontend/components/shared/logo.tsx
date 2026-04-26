/**
 * logo.tsx — StudentPlus brand mark + wordmark.
 *
 * Primarno učitava PNG slike iz `public/branding/` (logo-mark-light.png /
 * logo-mark-dark.png). Ako slike ne postoje ili ne uspeju da se učitaju,
 * automatski se prikazuje inline SVG fallback (mortarboard ikona u brand
 * bojama) — bez ikakvog vidljivog prekida u UI-ju.
 *
 * Theme switching: next-themes daje `resolvedTheme` (light|dark|undefined).
 * Pre hidracije i pre nego što useEffect postavi `mounted=true`, vraćamo
 * neutralan placeholder iste veličine — tako sprečavamo FOUC.
 */

"use client"

import Image from "next/image"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

export type LogoVariant = "full" | "mark-only"
export type LogoSize = "sm" | "md" | "lg" | "xl"

export interface LogoProps {
  variant?: LogoVariant
  size?: LogoSize
  className?: string
  /** Optional override; defaults to "StudentPlus". */
  alt?: string
  /** Hide the wordmark even on `variant="full"`. Used inside collapsed sidebars. */
  showText?: boolean
}

const MARK_PX: Record<LogoSize, number> = {
  sm: 24,
  md: 32,
  lg: 48,
  xl: 72,
}

const TEXT_CLASS: Record<LogoSize, string> = {
  sm: "text-base",
  md: "text-lg",
  lg: "text-2xl",
  xl: "text-4xl",
}

/**
 * Inline SVG fallback — mortarboard (graduation cap) u brand bojama.
 * Koristi se kada PNG slika nije uploadovana u `public/branding/`.
 * Isti fallback se koristi i tokom SSR pre hidracije.
 */
function LogoMarkSvg({
  size,
  dark = false,
}: {
  size: number
  dark?: boolean
}) {
  const primary = dark ? "#B0405A" : "#7B1E2C"
  const accent = dark ? "#F4C56A" : "#E8A93D"
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      style={{ flexShrink: 0 }}
    >
      {/* Background circle */}
      <circle cx="24" cy="24" r="24" fill={primary} />
      {/* Mortarboard board (top flat square) */}
      <polygon
        points="24,10 40,18 24,26 8,18"
        fill={accent}
      />
      {/* Cap body (trapezoid) */}
      <path
        d="M16 20v9c0 3.314 3.582 6 8 6s8-2.686 8-6v-9l-8 4-8-4z"
        fill="white"
        fillOpacity="0.92"
      />
      {/* Tassel string */}
      <line
        x1="40"
        y1="18"
        x2="40"
        y2="30"
        stroke={accent}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Tassel end */}
      <circle cx="40" cy="33" r="3" fill={accent} />
    </svg>
  )
}

export function Logo({
  variant = "full",
  size = "md",
  className,
  alt = "StudentPlus",
  showText,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const [imgError, setImgError] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const px = MARK_PX[size]
  const renderText = (showText ?? variant === "full") === true
  const isDark = resolvedTheme === "dark"

  // Pre hidracije — SVG placeholder rezerviše prostor (nema layout shift).
  if (!mounted) {
    return (
      <span
        className={cn("inline-flex items-center gap-2", className)}
        aria-label={alt}
        role="img"
      >
        <LogoMarkSvg size={px} dark={false} />
        {renderText && (
          <span
            className={cn(
              "font-semibold tracking-tight text-foreground",
              TEXT_CLASS[size]
            )}
            aria-hidden
          >
            Student<span className="text-accent">Plus</span>
          </span>
        )}
      </span>
    )
  }

  const src = isDark
    ? "/branding/logo-mark-dark.png"
    : "/branding/logo-mark-light.png"

  return (
    <span
      className={cn("inline-flex items-center gap-2", className)}
      role="img"
      aria-label={alt}
    >
      {imgError ? (
        <LogoMarkSvg size={px} dark={isDark} />
      ) : (
        <Image
          src={src}
          alt=""
          width={px}
          height={px}
          priority
          className="shrink-0 select-none"
          draggable={false}
          onError={() => setImgError(true)}
        />
      )}
      {renderText && (
        <span
          className={cn(
            "font-semibold tracking-tight text-foreground",
            TEXT_CLASS[size]
          )}
        >
          Student<span className="text-accent">Plus</span>
        </span>
      )}
    </span>
  )
}
