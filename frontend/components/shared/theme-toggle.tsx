/**
 * theme-toggle.tsx — Sun/Moon/System theme switcher.
 *
 * Renderuje DropdownMenuSub (Light / Dark / System) unutar UserMenu-ja.
 * Koristi `useTheme()` iz next-themes — paleta menja smooth (200ms na
 * `body`-ju), Logo PNG se zameni instant kroz `resolvedTheme` u
 * `<Logo />`-ju.
 *
 * Pre hidracije vraćamo neutralan placeholder da se izbegne hydration
 * mismatch (server ne zna preferred theme).
 */

"use client"

import { Check, Monitor, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { useEffect, useState } from "react"

import {
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu"

const OPTIONS = [
  { value: "light", label: "Svetla", icon: Sun },
  { value: "dark", label: "Tamna", icon: Moon },
  { value: "system", label: "Sistemska", icon: Monitor },
] as const

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const triggerIcon =
    !mounted || resolvedTheme === "light" ? (
      <Sun className="size-4" aria-hidden />
    ) : (
      <Moon className="size-4" aria-hidden />
    )

  const current = mounted ? (theme ?? "system") : "system"

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger className="gap-2">
        {triggerIcon}
        <span>Tema</span>
      </DropdownMenuSubTrigger>
      <DropdownMenuSubContent className="w-44">
        <DropdownMenuRadioGroup
          value={current}
          onValueChange={(v) => setTheme(v)}
        >
          {OPTIONS.map(({ value, label, icon: Icon }) => (
            <DropdownMenuRadioItem
              key={value}
              value={value}
              className="gap-2"
            >
              <Icon className="size-4" aria-hidden />
              <span className="flex-1">{label}</span>
              {current === value && (
                <Check className="size-3.5 text-muted-foreground" aria-hidden />
              )}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuSubContent>
    </DropdownMenuSub>
  )
}
