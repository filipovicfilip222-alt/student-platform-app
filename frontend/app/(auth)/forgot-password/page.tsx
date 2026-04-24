/**
 * (auth)/forgot-password/page.tsx — Request a password-reset link.
 *
 * ROADMAP 3.4 / Faza 3.1. Mirrors the login page pattern (RHF + zod +
 * shadcn Card). On submit, POSTs to /auth/forgot-password and shows the
 * success banner — the backend always returns 200 to prevent user
 * enumeration, so we do the same client-side (no distinction between
 * "sent" and "email not found").
 */

"use client"

import Link from "next/link"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ArrowLeft, Loader2, MailCheck } from "lucide-react"
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

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  })

  const { isSubmitting } = form.formState

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

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-2xl font-bold">Zaboravljena lozinka</CardTitle>
          <CardDescription>
            Unesite email adresu i poslaćemo vam link za resetovanje lozinke.
          </CardDescription>
        </CardHeader>

        <CardContent>
          {submittedEmail ? (
            <div className="space-y-4">
              <div className="flex flex-col items-center gap-3 rounded-md border border-primary/30 bg-primary/5 px-6 py-8 text-center">
                <MailCheck className="size-10 text-primary" aria-hidden />
                <p className="text-sm font-medium">
                  Ako adresa <span className="font-semibold">{submittedEmail}</span> postoji u sistemu,
                  link za resetovanje lozinke je poslat.
                </p>
                <p className="text-xs text-muted-foreground">
                  Proverite inbox i spam folder. Link važi jedan sat.
                </p>
              </div>
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
            </div>
          ) : (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                {serverError && (
                  <div className="rounded-md bg-destructive/10 border border-destructive/30 px-4 py-3 text-sm text-destructive">
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
          )}
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
