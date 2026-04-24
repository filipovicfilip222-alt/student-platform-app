/**
 * areas-of-interest-input.tsx — Tag-style input for the professor's
 * areas_of_interest list.
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Keeps the UX consistent with the
 * student-facing profile header chips (Badge variant="secondary").
 *
 * Keyboard UX: Enter or comma commits the current buffer; Backspace on
 * an empty buffer pops the last chip.
 */

"use client"

import { useState, type KeyboardEvent } from "react"
import { X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export interface AreasOfInterestInputProps {
  value: string[]
  onChange: (next: string[]) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  maxTags?: number
}

export function AreasOfInterestInput({
  value,
  onChange,
  placeholder = "Dodajte oblast i pritisnite Enter",
  disabled,
  className,
  maxTags = 20,
}: AreasOfInterestInputProps) {
  const [buffer, setBuffer] = useState("")

  function commit() {
    const next = buffer.trim()
    if (!next) return
    if (value.includes(next)) {
      setBuffer("")
      return
    }
    if (value.length >= maxTags) return
    onChange([...value, next])
    setBuffer("")
  }

  function remove(tag: string) {
    onChange(value.filter((t) => t !== tag))
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault()
      commit()
      return
    }
    if (e.key === "Backspace" && buffer.length === 0 && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }

  return (
    <div
      className={cn(
        "flex flex-wrap gap-1.5 rounded-lg border border-input bg-transparent px-2 py-1.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30",
        disabled && "pointer-events-none opacity-50",
        className
      )}
    >
      {value.map((tag) => (
        <Badge key={tag} variant="secondary" className="gap-1 pl-2 pr-1">
          <span>{tag}</span>
          <button
            type="button"
            aria-label={`Ukloni ${tag}`}
            className="rounded-sm p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            onClick={() => remove(tag)}
            disabled={disabled}
          >
            <X className="size-3" aria-hidden />
          </button>
        </Badge>
      ))}
      <Input
        value={buffer}
        onChange={(e) => setBuffer(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commit}
        placeholder={value.length === 0 ? placeholder : ""}
        disabled={disabled || value.length >= maxTags}
        className="h-6 min-w-[120px] flex-1 border-0 bg-transparent px-1 py-0 shadow-none focus-visible:ring-0 dark:bg-transparent"
      />
    </div>
  )
}
