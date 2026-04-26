/**
 * (auth)/forgot-password/page.tsx — Request a password-reset link.
 *
 * Backend always returns 200 to prevent user enumeration; client side
 * mirrors that — UI ne razlikuje "poslato" od "email ne postoji".
 *
 * Page renderuje samo formu/poruku — split layout i marketing panel
 * vlasi `(auth)/layout.tsx` (KORAK 2).
 */

"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ArrowLeft, Loader2, MailCheck } from "lucide-react"
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
import { authApi } from "@/lib/api/auth"
import { ROUTES } from "@/lib/constants/routes"
import { cn } from "@/lib/utils"

const forgotPasswordSchema = z.object({
  email: z
    .string()
    .min(1, "Email je obavezan.")
    .email("Unesite ispravnu email adresu."),
})

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>

export default function ForgotPasswordPage() {
  const [serverError, setServerError] = useState<string | null>(null)
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null)
  const [shakeKey, setShakeKey] = useState(0)

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  })

  const { isSubmitting } = form.formState

  useEffect(() => {
    if (serverError) setShakeKey((k) => k + 1)
  }, [serverError])

  async function onSubmit(values: ForgotPasswordFormValues) {
    setServerError(null)
    try {
      await authApi.forgotPassword({ email: values.email })
      setSubmittedEmail(values.email)
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      const msg =
        axiosErr.response?.data?.detail ??
        "Greška pri slanju zahteva. Pokušajte ponovo."
      setServerError(msg)
    }
  }

  if (submittedEmail) {
    return (
      <div className="space-y-6">
        <header className="space-y-3 text-center">
          <Logo
            variant="full"
            size="lg"
            className="mx-auto justify-center lg:hidden"
          />
          <h1 className="text-3xl font-bold tracking-tight">Proverite email</h1>
        </header>

        <div className="flex flex-col items-center gap-4 rounded-xl border border-primary/30 bg-primary/5 px-6 py-10 text-center">
          <MailCheck className="size-12 text-primary" aria-hidden />
          <div className="space-y-1">
            <p className="text-sm font-medium">
              Ako adresa{" "}
              <span className="font-semibold text-foreground">
                {submittedEmail}
              </span>{" "}
              postoji u sistemu, link za resetovanje lozinke je poslat.
            </p>
            <p className="text-xs text-muted-foreground">
              Proverite inbox i spam folder. Link važi jedan sat.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              setSubmittedEmail(null)
              form.reset()
            }}
          >
            Pošalji ponovo na drugu adresu
          </Button>
          <Button asChild variant="ghost" className="w-full">
            <Link href={ROUTES.login}>
              <ArrowLeft aria-hidden />
              Nazad na prijavu
            </Link>
          </Button>
        </div>
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
        <h1 className="text-3xl font-bold tracking-tight">Zaboravljena lozinka</h1>
        <p className="text-sm text-muted-foreground">
          Unesite email adresu i poslaćemo link za resetovanje.
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

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="animate-spin" />
                Šaljem...
              </>
            ) : (
              "Pošalji link za resetovanje"
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
