/**
 * (auth)/reset-password/page.tsx — Završetak password-reset flow-a.
 *
 * `?token=...` query param dolazi iz email link-a; ako ne postoji,
 * page renderuje fallback ekran sa CTA "zatraži novi link".
 *
 * Backend pravila (mirror u zod schemi):
 *   - new_password: min 8, max 128 (schemas/auth.py)
 *   - token: opaque string, 1h validity — backend vraća 422 na expired
 *
 * `useSearchParams()` zahteva Suspense boundary (isti pattern kao /login).
 */

"use client"

import { Suspense, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2 } from "lucide-react"
import type { AxiosError } from "axios"

import { PasswordStrengthMeter } from "@/components/auth/password-strength-meter"
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
import { PasswordInput } from "@/components/ui/password-input"
import { authApi } from "@/lib/api/auth"
import { ROUTES } from "@/lib/constants/routes"
import { cn } from "@/lib/utils"

const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(8, "Lozinka mora imati najmanje 8 karaktera.")
      .max(128, "Lozinka može imati najviše 128 karaktera."),
    confirm_password: z.string().min(1, "Potvrdite lozinku."),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Lozinke se ne poklapaju.",
    path: ["confirm_password"],
  })

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>

function ResetPasswordForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")?.trim() ?? ""

  const [serverError, setServerError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [shakeKey, setShakeKey] = useState(0)

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  })

  const { isSubmitting } = form.formState
  const passwordValue = form.watch("new_password")

  useEffect(() => {
    if (serverError) setShakeKey((k) => k + 1)
  }, [serverError])

  async function onSubmit(values: ResetPasswordFormValues) {
    if (!token) {
      setServerError("Token nije pronađen u linku.")
      return
    }
    setServerError(null)
    try {
      await authApi.resetPassword({
        token,
        new_password: values.new_password,
      })
      setSuccess(true)
      setTimeout(() => router.replace(`${ROUTES.login}?reset=1`), 2000)
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      const msg =
        axiosErr.response?.data?.detail ??
        "Link je nevažeći ili je istekao. Zatražite novi."
      setServerError(msg)
    }
  }

  // ── Missing/invalid token ─────────────────────────────────────────────
  if (!token) {
    return (
      <div className="space-y-6">
        <header className="space-y-3 text-center">
          <Logo
            variant="full"
            size="lg"
            className="mx-auto justify-center lg:hidden"
          />
          <h1 className="text-3xl font-bold tracking-tight">Link nije važeći</h1>
          <p className="text-sm text-muted-foreground">
            Ovaj link za resetovanje lozinke ne sadrži token.
          </p>
        </header>

        <div className="flex flex-col items-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-10 text-center">
          <AlertTriangle className="size-12 text-destructive" aria-hidden />
          <p className="text-sm">
            Otvorite link iz email poruke do kraja ili zatražite novi.
          </p>
        </div>

        <div className="space-y-3">
          <Button asChild className="w-full">
            <Link href={ROUTES.forgotPassword}>Zatraži novi link</Link>
          </Button>
          <Button asChild variant="outline" className="w-full">
            <Link href={ROUTES.login}>Nazad na prijavu</Link>
          </Button>
        </div>
      </div>
    )
  }

  // ── Success ───────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="space-y-6">
        <header className="space-y-3 text-center">
          <Logo
            variant="full"
            size="lg"
            className="mx-auto justify-center lg:hidden"
          />
          <h1 className="text-3xl font-bold tracking-tight">Lozinka je resetovana</h1>
        </header>

        <div className="flex flex-col items-center gap-4 rounded-xl border border-success/30 bg-success/10 px-6 py-10 text-center">
          <CheckCircle2 className="size-12 text-success" aria-hidden />
          <p className="text-sm">Preusmeravamo vas na stranicu za prijavu…</p>
        </div>

        <Button asChild className="w-full">
          <Link href={ROUTES.login}>Idi na prijavu odmah</Link>
        </Button>
      </div>
    )
  }

  return (
    <div
      key={shakeKey}
      className={cn("space-y-8", serverError && "animate-shake")}
    >
      <header className="space-y-3 text-center">
        <Logo
          variant="full"
          size="lg"
          className="mx-auto justify-center lg:hidden"
        />
        <h1 className="text-3xl font-bold tracking-tight">Nova lozinka</h1>
        <p className="text-sm text-muted-foreground">
          Lozinka mora imati najmanje 8 karaktera.
        </p>
      </header>

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
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Nova lozinka</FormLabel>
                <FormControl>
                  <PasswordInput
                    placeholder="••••••••"
                    autoComplete="new-password"
                    autoFocus
                    {...field}
                  />
                </FormControl>
                <PasswordStrengthMeter password={passwordValue ?? ""} />
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Potvrdite lozinku</FormLabel>
                <FormControl>
                  <PasswordInput
                    placeholder="••••••••"
                    autoComplete="new-password"
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
                Resetujem...
              </>
            ) : (
              "Resetuj lozinku"
            )}
          </Button>
        </form>
      </Form>

      <p className="text-center text-sm text-muted-foreground">
        <Link
          href={ROUTES.login}
          className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          Nazad na prijavu
        </Link>
      </p>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  )
}
