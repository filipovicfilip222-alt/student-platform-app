/**
 * users-table.tsx — Full CRUD table for ADMIN → Korisnici.
 *
 * ROADMAP 4.7 / FRONTEND_STRUKTURA §2 admin section. Per-row actions:
 *   - Edit     → opens <UserFormModal mode="edit" />
 *   - Deactivate → AlertDialog confirmation
 *   - Impersonate → calls `useStartImpersonation(id)` (the flow that
 *                   swaps auth store + opens the ImpersonationBanner —
 *                   see lib/hooks/use-impersonation.ts + docs/
 *                   websocket-schema.md §6).
 *
 * Filters (q / role / faculty) live in this component — no separate
 * `users-filters.tsx` is needed given how compact the filter set is.
 *
 * Until the backend `/admin/users` router lands (ROADMAP 4.7 ❌) the
 * table renders an error-fallback empty state; toggles and actions
 * remain wired so the integration is zero-code-change on backend go-live.
 */

"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import {
  Loader2,
  Pencil,
  Search,
  ShieldAlert,
  UserMinus,
  UserRound,
  UsersRound,
} from "lucide-react"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EmptyState } from "@/components/shared/empty-state"
import { FacultyBadge } from "@/components/shared/faculty-badge"
import { ROLES, roleLabel } from "@/lib/constants/roles"
import { ROUTES } from "@/lib/constants/routes"
import {
  useAdminUsers,
  useDeactivateAdminUser,
} from "@/lib/hooks/use-admin-users"
import { useStartImpersonation } from "@/lib/hooks/use-impersonation"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { AdminUserResponse, Faculty, Role } from "@/types"

import { UserFormModal } from "./user-form-modal"

const FACULTY_OPTIONS: Faculty[] = ["FON", "ETF"]

export interface UsersTableProps {
  onBulkImportClick?: () => void
}

export function UsersTable({ onBulkImportClick }: UsersTableProps) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const debouncedQuery = useDebouncedValue(query, 300)
  const [role, setRole] = useState<Role | "ALL">("ALL")
  const [faculty, setFaculty] = useState<Faculty | "ALL">("ALL")

  const filters = useMemo(
    () => ({
      q: debouncedQuery.trim() || undefined,
      role: role === "ALL" ? undefined : role,
      faculty: faculty === "ALL" ? undefined : faculty,
    }),
    [debouncedQuery, role, faculty]
  )

  const usersQuery = useAdminUsers(filters)
  const deactivate = useDeactivateAdminUser()
  const startImpersonation = useStartImpersonation()

  const [editingUser, setEditingUser] = useState<AdminUserResponse | null>(null)
  const [creatingUser, setCreatingUser] = useState(false)
  const [deactivationTarget, setDeactivationTarget] =
    useState<AdminUserResponse | null>(null)

  async function handleImpersonate(user: AdminUserResponse) {
    try {
      await startImpersonation.mutateAsync(user.id)
      toastSuccess(
        "Impersonacija pokrenuta",
        `Prijavljeni ste kao ${user.first_name} ${user.last_name}.`
      )
      // Per FRONTEND_STRUKTURA §3.6 — redirect to the target user's home
      // so admin tools stop being the active surface.
      const target =
        user.role === "ADMIN"
          ? ROUTES.admin
          : user.role === "STUDENT"
            ? ROUTES.dashboard
            : ROUTES.professorDashboard
      router.push(target)
    } catch (err) {
      toastApiError(err, "Impersonacija nije uspela.")
    }
  }

  async function handleConfirmDeactivate() {
    if (!deactivationTarget) return
    try {
      await deactivate.mutateAsync(deactivationTarget.id)
      toastSuccess(
        "Korisnik deaktiviran",
        `${deactivationTarget.first_name} ${deactivationTarget.last_name} više nema pristup.`
      )
      setDeactivationTarget(null)
    } catch (err) {
      toastApiError(err, "Deaktivacija nije uspela.")
    }
  }

  const users = usersQuery.data ?? []

  return (
    <div className="space-y-4">
      {/* ── Filter row ────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-background p-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label
            htmlFor="users-search"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Pretraga
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="users-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ime, prezime ili email"
              className="pl-8"
            />
          </div>
        </div>

        <div className="w-full sm:w-44">
          <label
            htmlFor="users-role"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Uloga
          </label>
          <Select
            value={role}
            onValueChange={(v) => setRole(v as Role | "ALL")}
          >
            <SelectTrigger id="users-role" className="w-full">
              <SelectValue placeholder="Sve uloge" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Sve uloge</SelectItem>
              {ROLES.map((r) => (
                <SelectItem key={r} value={r}>
                  {roleLabel(r)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-full sm:w-32">
          <label
            htmlFor="users-faculty"
            className="mb-1 block text-xs font-medium text-muted-foreground"
          >
            Fakultet
          </label>
          <Select
            value={faculty}
            onValueChange={(v) => setFaculty(v as Faculty | "ALL")}
          >
            <SelectTrigger id="users-faculty" className="w-full">
              <SelectValue placeholder="Svi" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Svi</SelectItem>
              {FACULTY_OPTIONS.map((f) => (
                <SelectItem key={f} value={f}>
                  {f}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex shrink-0 gap-2 sm:ml-auto">
          <Button variant="outline" onClick={onBulkImportClick}>
            <UsersRound aria-hidden />
            Bulk import
          </Button>
          <Button onClick={() => setCreatingUser(true)}>
            <UserRound aria-hidden />
            Novi korisnik
          </Button>
        </div>
      </div>

      {/* ── Table ─────────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-lg border border-border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[30%]">Ime</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Uloga</TableHead>
              <TableHead>Fakultet</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Akcije</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {usersQuery.isLoading ? (
              Array.from({ length: 4 }).map((_, idx) => (
                <TableRow key={idx}>
                  <TableCell colSpan={6}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))
            ) : usersQuery.isError ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8">
                  <EmptyState
                    icon={ShieldAlert}
                    title="Korisnici nisu dostupni"
                    description="Backend endpoint /admin/users još nije aktivan (ROADMAP 4.7)."
                  />
                </TableCell>
              </TableRow>
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8">
                  <EmptyState
                    icon={UserRound}
                    title="Nema pronađenih korisnika"
                    description="Pokušajte izmenom filtera ili dodajte novog korisnika."
                  />
                </TableCell>
              </TableRow>
            ) : (
              users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-medium">
                    {u.first_name} {u.last_name}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {u.email}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{roleLabel(u.role as Role)}</Badge>
                  </TableCell>
                  <TableCell>
                    <FacultyBadge faculty={u.faculty as Faculty} />
                  </TableCell>
                  <TableCell>
                    {u.is_active ? (
                      <Badge variant="secondary">Aktivan</Badge>
                    ) : (
                      <Badge variant="destructive">Deaktiviran</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditingUser(u)}
                        aria-label={`Izmeni ${u.first_name} ${u.last_name}`}
                      >
                        <Pencil aria-hidden />
                        Izmeni
                      </Button>
                      {u.role !== "ADMIN" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleImpersonate(u)}
                          disabled={
                            startImpersonation.isPending || !u.is_active
                          }
                          aria-label={`Impersoniraj ${u.first_name} ${u.last_name}`}
                        >
                          {startImpersonation.isPending &&
                          startImpersonation.variables === u.id ? (
                            <Loader2 className="animate-spin" aria-hidden />
                          ) : (
                            <ShieldAlert aria-hidden />
                          )}
                          Impersoniraj
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setDeactivationTarget(u)}
                        disabled={!u.is_active}
                        aria-label={`Deaktiviraj ${u.first_name} ${u.last_name}`}
                      >
                        <UserMinus aria-hidden />
                        Deaktiviraj
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* ── Edit / Create modals ─────────────────────────────────────── */}
      <UserFormModal
        mode="create"
        open={creatingUser}
        onOpenChange={setCreatingUser}
      />
      <UserFormModal
        mode="edit"
        user={editingUser}
        open={Boolean(editingUser)}
        onOpenChange={(open) => !open && setEditingUser(null)}
      />

      {/* ── Deactivate confirmation ──────────────────────────────────── */}
      <AlertDialog
        open={Boolean(deactivationTarget)}
        onOpenChange={(open) => !open && setDeactivationTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deaktivirati korisnika?</AlertDialogTitle>
            <AlertDialogDescription>
              {deactivationTarget && (
                <>
                  Deaktivacijom gubi pristup svim servisima.{" "}
                  <strong>
                    {deactivationTarget.first_name}{" "}
                    {deactivationTarget.last_name}
                  </strong>{" "}
                  više neće moći da se prijavi.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deactivate.isPending}>
              Odustani
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deactivate.isPending}
              onClick={(e) => {
                e.preventDefault()
                void handleConfirmDeactivate()
              }}
            >
              {deactivate.isPending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden />
                  Deaktiviram…
                </>
              ) : (
                "Deaktiviraj"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
