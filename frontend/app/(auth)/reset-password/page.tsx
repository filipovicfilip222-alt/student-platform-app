/**
 * (auth)/reset-password/page.tsx — Finish the password-reset flow.
 *
 * ROADMAP 3.4 / Faza 3.1. Reads the `?token=...` query parameter from
 * the email link, accepts a new password + confirmation, and POSTs to
 * /auth/reset-password. On success the user is redirected to /login.
 *
 * Backend rules (mirrored in zod schema):
 *   - new_password: min 8, max 128 characters (schemas/auth.py)
 *   - token: opaque string, validity 1h — backend returns 422 on expired
 *     or used tokens
 *
 * Uses `useSearchParams()` which requires a Suspense boundary (same
 * pattern as /login).
 */

"use client"

import { Suspense, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2 } from "lucide-react"
import type { AxiosError } from "axios"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { authApi } from "@/lib/api/auth"
import { ROUTES } from "@/lib/constants/routes"

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

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  })

  const { isSubmitting } = form.formState

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

  // ── Missing/invalid token — explicit UX, avoid exposing the form ────────────
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl font-bold">Link nije važeći</CardTitle>
            <CardDescription>
              Ovaj link za resetovanje lozinke ne sadrži token.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-6 py-8 text-center">
              <AlertTriangle className="size-10 text-destructive" aria-hidden />
              <p className="text-sm">
                Otvorite link iz email poruke do kraja ili zatražite novi.
              </p>
            </div>
          </CardContent>
          <CardFooter className="flex-col gap-2">
            <Button asChild className="w-full">
              <Link href={ROUTES.forgotPassword}>Zatraži novi link</Link>
            </Button>
            <Button asChild variant="outline" className="w-full">
              <Link href={ROUTES.login}>Nazad na prijavu</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  // ── Success state — auto-redirect after 2s ─────────────────────────────────
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="space-y-1 text-center">
            <CardTitle className="text-2xl font-bold">Lozinka je resetovana</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center gap-3 rounded-md border border-primary/30 bg-primary/5 px-6 py-8 text-center">
              <CheckCircle2 className="size-10 text-primary" aria-hidden />
              <p className="text-sm">
                Preusmeravamo vas na stranicu za prijavu...
              </p>
            </div>
          </CardContent>
          <CardFooter>
            <Button asChild className="w-full">
              <Link href={ROUTES.login}>Idi na prijavu odmah</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-2xl font-bold">Nova lozinka</CardTitle>
          <CardDescription>
            Unesite novu lozinku za svoj nalog. Lozinka mora imati najmanje 8 karaktera.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              {serverError && (
                <div className="rounded-md bg-destructive/10 border border-destructive/30 px-4 py-3 text-sm text-destructive">
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
                      <Input
                        type="password"
                        placeholder="••••••••"
                        autoComplete="new-password"
                        {...field}
                      />
                    </FormControl>
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
                      <Input
                        type="password"
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
        </CardContent>

        <CardFooter className="justify-center text-sm text-muted-foreground">
          <Link
            href={ROUTES.login}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline underline-offset-4"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            Nazad na prijavu
          </Link>
        </CardFooter>
      </Card>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="min-h-screen" />}>
      <ResetPasswordForm />
    </Suspense>
  )
}
