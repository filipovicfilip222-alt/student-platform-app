/**
 * chat-input.tsx — Textarea + send button za TicketChat.
 *
 * KORAK 6 (StudentPlus polish):
 *   - Auto-grow: textarea raste sa sadržajem do max 4 reda (~120px).
 *     Iznad — interni scroll, bez pomeranja chat layout-a.
 *   - Enter šalje, Shift+Enter ubacuje novi red.
 *   - Char counter pojavljuje se na 50% (>=500 chars), postaje amber na
 *     80% (>=800), destructive na 95% (>=950).
 *   - Tipke u taskbar-u (formatting hint) ostaju namerno odsutne — user
 *     research je pokazao da admini i studenti koriste 99% plain tekst.
 */

"use client"

import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react"
import { Loader2, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const MAX_LENGTH = 1000
const MAX_ROWS = 4
/** ~24px line-height + padding (top/bottom) — measured for `<Textarea />`. */
const APPROX_LINE_HEIGHT = 24
const TEXTAREA_PADDING = 18

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
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const [value, setValue] = useState("")
  const trimmed = value.trim()
  const isDisabled = disabled || isSending
  const canSend = trimmed.length > 0 && !isDisabled

  // Auto-grow: reset → measure → clamp at MAX_ROWS lines.
  useLayoutEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    const max = MAX_ROWS * APPROX_LINE_HEIGHT + TEXTAREA_PADDING
    const next = Math.min(ta.scrollHeight, max)
    ta.style.height = `${next}px`
    ta.style.overflowY = ta.scrollHeight > max ? "auto" : "hidden"
  }, [value])

  // Reset overflowY style when input is cleared after send.
  useEffect(() => {
    if (!value) {
      const ta = textareaRef.current
      if (ta) ta.style.overflowY = "hidden"
    }
  }, [value])

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

  const showCounter = value.length >= MAX_LENGTH * 0.5
  const counterTone =
    value.length >= MAX_LENGTH * 0.95
      ? "text-destructive"
      : value.length >= MAX_LENGTH * 0.8
        ? "text-amber-700 dark:text-amber-300"
        : "text-muted-foreground"

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className={cn("space-y-1", className)}
    >
      <div className="flex items-end gap-2">
        <div className="relative flex-1">
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value.slice(0, MAX_LENGTH))}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isDisabled}
            rows={1}
            maxLength={MAX_LENGTH}
            className="min-h-[42px] resize-none overflow-hidden text-sm leading-6"
            aria-label="Poruka"
            aria-describedby={showCounter ? "chat-input-counter" : undefined}
          />
        </div>
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
      </div>
      <div className="flex items-center justify-between gap-2 px-1 text-[10px] text-muted-foreground">
        <span aria-hidden>
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px] font-mono">
            Enter
          </kbd>{" "}
          šalje ·{" "}
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px] font-mono">
            Shift+Enter
          </kbd>{" "}
          novi red
        </span>
        {showCounter && (
          <span
            id="chat-input-counter"
            className={cn("font-medium tabular-nums", counterTone)}
            aria-live="polite"
          >
            {value.length} / {MAX_LENGTH}
          </span>
        )}
      </div>
    </form>
  )
}
