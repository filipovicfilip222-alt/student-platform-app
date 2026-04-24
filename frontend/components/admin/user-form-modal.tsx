/**
 * user-form-modal.tsx — Create / edit a user as admin.
 *
 * ROADMAP 4.7. Shared by the "Novi korisnik" CTA and the per-row "Izmeni"
 * action in `UsersTable`. In `edit` mode, email + password are locked
 * (the backend exposes only `AdminUserUpdate = Partial<...>` without
 * email/password — password resets go through /auth flows).
 */

"use client"

import { useEffect, useMemo, useState } from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ROLES, roleLabel } from "@/lib/constants/roles"
import {
  useCreateAdminUser,
  useUpdateAdminUser,
} from "@/lib/hooks/use-admin-users"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type {
  AdminUserCreate,
  AdminUserResponse,
  AdminUserUpdate,
  Faculty,
  Role,
} from "@/types"

const FACULTIES: Faculty[] = ["FON", "ETF"]

interface FormState {
  email: string
  password: string
  first_name: string
  last_name: string
  role: Role
  faculty: Faculty
  is_active: boolean
}

const EMPTY: FormState = {
  email: "",
  password: "",
  first_name: "",
  last_name: "",
  role: "STUDENT",
  faculty: "FON",
  is_active: true,
}

export type UserFormMode = "create" | "edit"

interface BaseProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface CreateProps extends BaseProps {
  mode: "create"
  user?: never
}

interface EditProps extends BaseProps {
  mode: "edit"
  user: AdminUserResponse | null
}

export type UserFormModalProps = CreateProps | EditProps

export function UserFormModal(props: UserFormModalProps) {
  const { mode, open, onOpenChange } = props
  const editingUser = mode === "edit" ? props.user : null

  const create = useCreateAdminUser()
  const update = useUpdateAdminUser()

  const initial = useMemo<FormState>(() => {
    if (mode === "edit" && editingUser) {
      return {
        email: editingUser.email,
        password: "",
        first_name: editingUser.first_name,
        last_name: editingUser.last_name,
        role: editingUser.role,
        faculty: editingUser.faculty,
        is_active: editingUser.is_active,
      }
    }
    return EMPTY
  }, [mode, editingUser])

  const [form, setForm] = useState<FormState>(initial)

  useEffect(() => {
    setForm(initial)
  }, [initial])

  const isPending = create.isPending || update.isPending

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      if (mode === "create") {
        const payload: AdminUserCreate = {
          email: form.email.trim(),
          password: form.password,
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          role: form.role,
          faculty: form.faculty,
        }
        await create.mutateAsync(payload)
        toastSuccess("Korisnik kreiran", `${payload.first_name} ${payload.last_name}`)
      } else if (editingUser) {
        const payload: AdminUserUpdate = {
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          role: form.role,
          faculty: form.faculty,
          is_active: form.is_active,
        }
        await update.mutateAsync({ id: editingUser.id, data: payload })
        toastSuccess("Izmene sačuvane")
      }
      onOpenChange(false)
    } catch (err) {
      toastApiError(
        err,
        mode === "create"
          ? "Kreiranje korisnika nije uspelo."
          : "Snimanje izmena nije uspelo."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Novi korisnik" : "Izmena korisnika"}
          </DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Kreirajte nalog. Korisnik će dobiti email sa linkom za prvu prijavu."
              : `Izmena naloga ${editingUser?.first_name ?? ""} ${editingUser?.last_name ?? ""}.`}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="grid gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="form-email">Email</Label>
            <Input
              id="form-email"
              type="email"
              autoComplete="off"
              required
              disabled={mode === "edit"}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>

          {mode === "create" && (
            <div className="grid gap-1.5">
              <Label htmlFor="form-password">Privremena lozinka</Label>
              <Input
                id="form-password"
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) =>
                  setForm({ ...form, password: e.target.value })
                }
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="form-first">Ime</Label>
              <Input
                id="form-first"
                required
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="form-last">Prezime</Label>
              <Input
                id="form-last"
                required
                value={form.last_name}
                onChange={(e) =>
                  setForm({ ...form, last_name: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="form-role">Uloga</Label>
              <Select
                value={form.role}
                onValueChange={(v) => setForm({ ...form, role: v as Role })}
              >
                <SelectTrigger id="form-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {roleLabel(r)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="form-faculty">Fakultet</Label>
              <Select
                value={form.faculty}
                onValueChange={(v) =>
                  setForm({ ...form, faculty: v as Faculty })
                }
              >
                <SelectTrigger id="form-faculty" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FACULTIES.map((f) => (
                    <SelectItem key={f} value={f}>
                      {f}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {mode === "edit" && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) =>
                  setForm({ ...form, is_active: e.target.checked })
                }
                className="size-4"
              />
              Nalog aktivan
            </label>
          )}

          <DialogFooter className="mt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Otkaži
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Snimam…
                </>
              ) : mode === "create" ? (
                "Kreiraj"
              ) : (
                "Sačuvaj"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
