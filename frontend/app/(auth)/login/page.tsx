"use client"
import { Suspense } from "react"
import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2 } from "lucide-react"
import type { AxiosError } from "axios"

import { Logo } from "@/components/shared/logo"
import { Button } from "@/components/ui/button"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PasswordInput } from "@/components/ui/password-input"
import { authApi } from "@/lib/api/auth"
import { ROUTES } from "@/lib/constants/routes"
import { useAuthStore } from "@/lib/stores/auth"
import { cn } from "@/lib/utils"
import type { Role } from "@/types/common"

const ROLE_HOME: Record<Role, string> = {
  STUDENT: ROUTES.dashboard,
  PROFESOR: ROUTES.professorDashboard,
  ASISTENT: ROUTES.professorDashboard,
  ADMIN: ROUTES.admin,
}

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Email je obavezan.")
    .email("Unesite ispravnu email adresu."),
  password: z.string().min(1, "Lozinka je obavezna."),
})

type LoginFormValues = z.infer<typeof loginSchema>

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { setAuth } = useAuthStore()
  const [serverError, setServerError] = useState<string | null>(null)
  const [shakeKey, setShakeKey] = useState(0)
  const cardRef = useRef<HTMLDivElement>(null)

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  const { isSubmitting } = form.formState

  // Surface a "lozinka uspešno resetovana" hint kada user dođe sa
  // /reset-password (preusmeravan kroz `?reset=1`).
  const justReset = searchParams.get("reset") === "1"

  // Restart shake animation each time serverError postavi — `key` na
  // wrapperu trigger-uje React-to-remount i animacija krene ispočetka.
  useEffect(() => {
    if (serverError) setShakeKey((k) => k + 1)
  }, [serverError])

  async function onSubmit(values: LoginFormValues) {
    setServerError(null)
    try {
      const { data } = await authApi.login(values)
      setAuth(data.user, data.access_token)
      const from = searchParams.get("from")
      const destination =
        from && from.startsWith("/") ? from : ROLE_HOME[data.user.role]
      router.replace(destination)
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      const msg =
        axiosErr.response?.data?.detail ??
        "Greška pri prijavi. Pokušajte ponovo."
      setServerError(msg)
    }
  }

  return (
    <div
      ref={cardRef}
      key={shakeKey}
      className={cn("space-y-8", serverError && "animate-shake")}
    >
      <header className="space-y-3 text-center">
        <Logo
          variant="full"
          size="lg"
          className="mx-auto justify-center lg:hidden"
        />
        <h1 className="text-3xl font-bold tracking-tight">Dobrodošli nazad</h1>
        <p className="text-sm text-muted-foreground">
          Prijavite se sa fakultetskim email nalogom.
        </p>
      </header>

      {justReset && !serverError && (
        <div className="rounded-md border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-foreground">
          Lozinka je uspešno resetovana. Prijavite se sa novom lozinkom.
        </div>
      )}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
          {serverError && (
            <div
              role="alert"
              aria-live="assertive"
              className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {serverError}
            </div>
          )}

          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="ime.prezime@student.fon.bg.ac.rs"
                    autoComplete="email"
                    autoFocus
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between">
                  <FormLabel>Lozinka</FormLabel>
                  <Link
                    href={ROUTES.forgotPassword}
                    className="text-xs text-muted-foreground underline-offset-4 transition-colors hover:text-primary hover:underline"
                  >
                    Zaboravili ste lozinku?
                  </Link>
                </div>
                <FormControl>
                  <PasswordInput
                    placeholder="••••••••"
                    autoComplete="current-password"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="animate-spin" />
                Prijavljujem...
              </>
            ) : (
              "Prijavi se"
            )}
          </Button>
        </form>
      </Form>

      <p className="text-center text-sm text-muted-foreground">
        Nemate nalog?{" "}
        <Link
          href={ROUTES.register}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Registrujte se
        </Link>
      </p>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
