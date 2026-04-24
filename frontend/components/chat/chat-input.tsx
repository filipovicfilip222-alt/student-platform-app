/**
 * chat-input.tsx — Textarea + send button for TicketChat.
 *
 * ROADMAP 3.6 / Faza 3.6. Enter submits, Shift+Enter inserts newline.
 * Input is disabled while `isSending` is true or `disabled` prop set.
 */

"use client"

import { useState, type KeyboardEvent } from "react"
import { Loader2, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const MAX_LENGTH = 1000

export interface ChatInputProps {
  onSend: (content: string) => void
  isSending?: boolean
  disabled?: boolean
  placeholder?: string
  className?: string
}

export function ChatInput({
  onSend,
  isSending = false,
  disabled = false,
  placeholder = "Napišite poruku...",
  className,
}: ChatInputProps) {
  const [value, setValue] = useState("")
  const trimmed = value.trim()
  const isDisabled = disabled || isSending
  const canSend = trimmed.length > 0 && !isDisabled

  function submit() {
    if (!canSend) return
    onSend(trimmed)
    setValue("")
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className={cn("flex items-end gap-2", className)}
    >
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value.slice(0, MAX_LENGTH))}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        rows={2}
        className="min-h-[60px] resize-none"
        aria-label="Poruka"
      />
      <Button
        type="submit"
        size="icon"
        disabled={!canSend}
        aria-label="Pošalji poruku"
      >
        {isSending ? (
          <Loader2 className="animate-spin" aria-hidden />
        ) : (
          <Send aria-hidden />
        )}
      </Button>
    </form>
  )
}
