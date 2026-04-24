/**
 * broadcast-form.tsx — Send platform-wide announcement as ADMIN.
 *
 * ROADMAP 4.7 / FRONTEND_STRUKTURA §3.6. Posts to /admin/broadcast with
 * {title, body, target, faculty?, channels[]}. The schema mirrors
 * `BroadcastRequest` in types/admin.ts (targets: ALL / STUDENTS / STAFF /
 * BY_FACULTY; channels: IN_APP / EMAIL).
 *
 * Shows recipient_count in a success toast after send.
 */

"use client"

import { useState } from "react"
import { Loader2, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useSendBroadcast } from "@/lib/hooks/use-broadcast"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type {
  BroadcastChannel,
  BroadcastRequest,
  BroadcastTarget,
  Faculty,
} from "@/types"

const TARGET_OPTIONS: Array<{ value: BroadcastTarget; label: string }> = [
  { value: "ALL", label: "Svi korisnici" },
  { value: "STUDENTS", label: "Samo studenti" },
  { value: "STAFF", label: "Samo profesori/asistenti" },
  { value: "BY_FACULTY", label: "Po fakultetu" },
]

export function BroadcastForm() {
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [target, setTarget] = useState<BroadcastTarget>("ALL")
  const [faculty, setFaculty] = useState<Faculty>("FON")
  const [channels, setChannels] = useState<BroadcastChannel[]>(["IN_APP"])

  const send = useSendBroadcast()

  function toggleChannel(c: BroadcastChannel) {
    setChannels((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (channels.length === 0) {
      toastApiError(
        new Error("Izaberite bar jedan kanal (IN_APP ili EMAIL)."),
        "Nevalidni podaci"
      )
      return
    }

    const payload: BroadcastRequest = {
      title: title.trim(),
      body: body.trim(),
      target,
      faculty: target === "BY_FACULTY" ? faculty : null,
      channels,
    }

    try {
      const result = await send.mutateAsync(payload)
      toastSuccess(
        "Obaveštenje poslato",
        `Dostavljeno ${result.recipient_count} primaocima.`
      )
      setTitle("")
      setBody("")
      setChannels(["IN_APP"])
    } catch (err) {
      toastApiError(err, "Slanje nije uspelo.")
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-4 rounded-lg border border-border bg-background p-4"
    >
      <div className="grid gap-1.5">
        <Label htmlFor="bc-title">Naslov</Label>
        <Input
          id="bc-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={120}
        />
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="bc-body">Tekst</Label>
        <Textarea
          id="bc-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          required
          minLength={10}
        />
        <p className="text-xs text-muted-foreground">
          Markdown nije podržan — obični tekst se dostavlja svim primaocima.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="bc-target">Primaoci</Label>
          <Select
            value={target}
            onValueChange={(v) => setTarget(v as BroadcastTarget)}
          >
            <SelectTrigger id="bc-target" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TARGET_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {target === "BY_FACULTY" && (
          <div className="grid gap-1.5">
            <Label htmlFor="bc-faculty">Fakultet</Label>
            <Select
              value={faculty}
              onValueChange={(v) => setFaculty(v as Faculty)}
            >
              <SelectTrigger id="bc-faculty" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="FON">FON</SelectItem>
                <SelectItem value="ETF">ETF</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <div className="grid gap-1.5">
        <Label>Kanali dostave</Label>
        <div className="flex gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={channels.includes("IN_APP")}
              onChange={() => toggleChannel("IN_APP")}
              className="size-4"
            />
            In-app (notification center)
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={channels.includes("EMAIL")}
              onChange={() => toggleChannel("EMAIL")}
              className="size-4"
            />
            Email
          </label>
        </div>
      </div>

      <div className="flex justify-end">
        <Button
          type="submit"
          disabled={send.isPending || channels.length === 0}
        >
          {send.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Šaljem…
            </>
          ) : (
            <>
              <Send aria-hidden />
              Pošalji obaveštenje
            </>
          )}
        </Button>
      </div>
    </form>
  )
}
