/**
 * user-menu.tsx — Avatar dropdown in the top-bar (profile + logout).
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * - "Profil" link is disabled for now (ROADMAP 3.4 — profile page arrives
 *   with the student dashboard milestone).
 * - "Odjavi se" calls the existing `useLogout` mutation which:
 *     1. POSTs /auth/logout to revoke the Redis refresh entry and clear
 *        the httpOnly cookie (see backend/app/api/v1/auth.py).
 *     2. Clears the Zustand auth store.
 *     3. Clears the whole TanStack Query cache.
 *     4. We then push to /login. Middleware would redirect anyway on the
 *        next navigation, but an explicit redirect avoids a brief flash
 *        of the protected page shell after logout.
 */

"use client"

import { LogOut, User } from "lucide-react"
import { useRouter } from "next/navigation"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ROUTES } from "@/lib/constants/routes"
import { useLogout } from "@/lib/hooks/use-auth"
import { useAuthStore } from "@/lib/stores/auth"
import { toastApiError } from "@/lib/utils/errors"
import type { UserResponse } from "@/types/auth"

function initialsOf(user: UserResponse | null): string {
  if (!user) return "?"
  const a = user.first_name?.[0] ?? ""
  const b = user.last_name?.[0] ?? ""
  return (a + b).toUpperCase() || "?"
}

export function UserMenu() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()

  async function handleLogout() {
    try {
      await logout.mutateAsync()
    } catch (err) {
      // Even if the network call fails, clearAuth still ran in onSettled —
      // surface the problem but still proceed to /login so the UI matches
      // the store state.
      toastApiError(err, "Odjava nije potvrđena sa serverom")
    } finally {
      router.replace(ROUTES.login)
    }
  }

  if (!user) return null

  const fullName = `${user.first_name} ${user.last_name}`.trim()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="gap-2 pl-1 pr-2"
          aria-label="Korisnički meni"
        >
          <Avatar size="sm">
            {user.profile_image_url && (
              <AvatarImage src={user.profile_image_url} alt={fullName} />
            )}
            <AvatarFallback>{initialsOf(user)}</AvatarFallback>
          </Avatar>
          <span className="hidden max-w-[10rem] truncate text-sm font-medium sm:inline">
            {fullName}
          </span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="py-2">
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-foreground">
              {fullName}
            </span>
            <span className="truncate text-xs text-muted-foreground">
              {user.email}
            </span>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        <DropdownMenuItem disabled>
          <User aria-hidden />
          Profil
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          variant="destructive"
          onSelect={(e) => {
            e.preventDefault()
            void handleLogout()
          }}
          disabled={logout.isPending}
        >
          <LogOut aria-hidden />
          {logout.isPending ? "Odjavljivanje…" : "Odjavi se"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
