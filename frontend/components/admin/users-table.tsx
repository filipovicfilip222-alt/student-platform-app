/**
 * users-table.tsx — Full CRUD table za ADMIN → Korisnici.
 *
 * KORAK 4 — refaktor sa generic `<DataTable />`. Per-row akcije sada idu
 * u kompaktan `<DropdownMenu />` (MoreHorizontal trigger), umesto 3
 * inline ghost button-a koji su visili iz desne strane reda.
 *
 * Filteri (q / role / faculty) su SERVER-driven — `useAdminUsers(filters)`
 * šalje params na backend (unaccent prefix iz Prompt 1 KORAK 10).
 * Pagination i sort su CLIENT-driven preko DataTable-a (server vraća
 * collapsed listu jer interni admin set retko prelazi 1000+).
 */

"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import {
  Loader2,
  MoreHorizontal,
  Pencil,
  ShieldAlert,
  UserMinus,
  UserRound,
  UsersRound,
} from "lucide-react"
import type { ColumnDef } from "@tanstack/react-table"

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
import { DataTable } from "@/components/ui/data-table"
import {
  DataTableToolbar,
  FilterChip,
} from "@/components/ui/data-table-toolbar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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

  // ── Column definitions ────────────────────────────────────────────────
  const columns = useMemo<ColumnDef<AdminUserResponse>[]>(
    () => [
      {
        accessorFn: (u) => `${u.first_name} ${u.last_name}`,
        id: "name",
        header: "Ime",
        cell: ({ row }) => (
          <span className="font-medium">
            {row.original.first_name} {row.original.last_name}
          </span>
        ),
      },
      {
        accessorKey: "email",
        header: "Email",
        cell: ({ getValue }) => (
          <span className="font-mono text-xs text-muted-foreground">
            {getValue<string>()}
          </span>
        ),
      },
      {
        accessorKey: "role",
        header: "Uloga",
        cell: ({ getValue }) => (
          <Badge variant="outline">{roleLabel(getValue<Role>())}</Badge>
        ),
      },
      {
        accessorKey: "faculty",
        header: "Fakultet",
        cell: ({ getValue }) => {
          const f = getValue<Faculty | null>()
          return f ? (
            <FacultyBadge faculty={f} />
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )
        },
      },
      {
        accessorKey: "is_active",
        header: "Status",
        cell: ({ getValue }) =>
          getValue<boolean>() ? (
            <Badge variant="secondary">Aktivan</Badge>
          ) : (
            <Badge variant="destructive">Deaktiviran</Badge>
          ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Akcije</span>,
        enableSorting: false,
        cell: ({ row }) => {
          const u = row.original
          const isImpersonating =
            startImpersonation.isPending && startImpersonation.variables === u.id
          return (
            <div className="flex justify-end">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Akcije za ${u.first_name} ${u.last_name}`}
                  >
                    {isImpersonating ? (
                      <Loader2 className="animate-spin" aria-hidden />
                    ) : (
                      <MoreHorizontal aria-hidden />
                    )}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-44">
                  <DropdownMenuLabel>Korisnik</DropdownMenuLabel>
                  <DropdownMenuItem onSelect={() => setEditingUser(u)}>
                    <Pencil aria-hidden />
                    Izmeni
                  </DropdownMenuItem>
                  {u.role !== "ADMIN" && (
                    <DropdownMenuItem
                      disabled={!u.is_active || startImpersonation.isPending}
                      onSelect={() => handleImpersonate(u)}
                    >
                      <ShieldAlert aria-hidden />
                      Impersoniraj
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    disabled={!u.is_active}
                    variant="destructive"
                    onSelect={() => setDeactivationTarget(u)}
                  >
                    <UserMinus aria-hidden />
                    Deaktiviraj
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )
        },
      },
    ],
    [startImpersonation.isPending, startImpersonation.variables]
  )

  return (
    <div className="space-y-4">
      <DataTable<AdminUserResponse, unknown>
        data={users}
        columns={columns}
        isLoading={usersQuery.isLoading}
        isError={usersQuery.isError}
        ariaLabel="Tabela korisnika"
        toolbar={
          <DataTableToolbar
            searchValue={query}
            searchPlaceholder="Ime, prezime ili email"
            onSearchChange={setQuery}
            filters={
              <>
                <Select
                  value={role}
                  onValueChange={(v) => setRole(v as Role | "ALL")}
                >
                  <SelectTrigger className="h-8 w-44" aria-label="Uloga">
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

                <Select
                  value={faculty}
                  onValueChange={(v) => setFaculty(v as Faculty | "ALL")}
                >
                  <SelectTrigger className="h-8 w-32" aria-label="Fakultet">
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

                {role !== "ALL" && (
                  <FilterChip
                    label="Uloga"
                    value={roleLabel(role)}
                    onClear={() => setRole("ALL")}
                  />
                )}
                {faculty !== "ALL" && (
                  <FilterChip
                    label="Fakultet"
                    value={faculty}
                    onClear={() => setFaculty("ALL")}
                  />
                )}
              </>
            }
            actions={
              <>
                <Button variant="outline" onClick={onBulkImportClick}>
                  <UsersRound aria-hidden />
                  Bulk import
                </Button>
                <Button onClick={() => setCreatingUser(true)}>
                  <UserRound aria-hidden />
                  Novi korisnik
                </Button>
              </>
            }
          />
        }
        emptyState={{
          icon: UserRound,
          title: "Nema pronađenih korisnika",
          description:
            "Pokušajte izmenom filtera ili dodajte novog korisnika.",
        }}
        errorState={{
          icon: ShieldAlert,
          title: "Korisnici nisu dostupni",
          description:
            "Backend endpoint /admin/users još nije aktivan (ROADMAP 4.7).",
        }}
      />

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
