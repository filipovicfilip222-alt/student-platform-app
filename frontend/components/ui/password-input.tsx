/**
 * password-input.tsx — Password Input sa Show/Hide toggle.
 *
 * Drop-in replacement za `<Input type="password" />` koji dodaje
 * Eye/EyeOff dugme u trailing slot. Ostatak ponašanja (focus ring,
 * aria-invalid, disabled state) nasleđuje iz `<Input />` da ostane
 * konzistentno sa ostatkom forme.
 *
 * Forwarduje ref → kompatibilno sa react-hook-form `<FormControl>`.
 *
 * A11y:
 *   - Toggle button ima `aria-label` koji se menja po stanju.
 *   - Button je `type="button"` da NE submituje formu kad korisnik klikne.
 *   - Ikona je `aria-hidden`; tekst je u `sr-only` da screen reader-i
 *     pročitaju label.
 */

"use client"

import { Eye, EyeOff } from "lucide-react"
import * as React from "react"

import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export interface PasswordInputProps
  extends Omit<React.ComponentProps<"input">, "type"> {
  /** Override the visibility toggle's accessible label (default: "Prikaži lozinku" / "Sakrij lozinku"). */
  showLabel?: string
  hideLabel?: string
}

export const PasswordInput = React.forwardRef<
  HTMLInputElement,
  PasswordInputProps
>(function PasswordInput(
  { className, showLabel = "Prikaži lozinku", hideLabel = "Sakrij lozinku", ...props },
  ref
) {
  const [visible, setVisible] = React.useState(false)

  return (
    <div className="relative">
      <Input
        {...props}
        ref={ref}
        type={visible ? "text" : "password"}
        className={cn("pr-10", className)}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-lg text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50"
        aria-label={visible ? hideLabel : showLabel}
        disabled={props.disabled}
        tabIndex={-1}
      >
        {visible ? (
          <EyeOff className="size-4" aria-hidden />
        ) : (
          <Eye className="size-4" aria-hidden />
        )}
      </button>
    </div>
  )
})
