"use client"
import { Suspense } from "react"
import { useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2 } from "lucide-react"
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
import { useAuthStore } from "@/lib/stores/auth"
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
  password: z
    .string()
    .min(1, "Lozinka je obavezna."),
})

type LoginFormValues = z.infer<typeof loginSchema>

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { setAuth } = useAuthStore()
  const [serverError, setServerError] = useState<string | null>(null)

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  const { isSubmitting } = form.formState

  async function onSubmit(values: LoginFormValues) {
    setServerError(null)
    try {
      const { data } = await authApi.login(values)
      setAuth(data.user, data.access_token)
      const from = searchParams.get("from")
      const destination = from && from.startsWith("/") ? from : ROLE_HOME[data.user.role]
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
    <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-2xl font-bold">Konsultacije FON &amp; ETF</CardTitle>
          <CardDescription>Prijavite se sa fakultetskim email nalogom</CardDescription>
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

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <div className="flex items-center justify-between">
                      <FormLabel>Lozinka</FormLabel>
                      <Link
                        href="/forgot-password"
                        className="text-xs text-muted-foreground hover:text-primary underline-offset-4 hover:underline"
                      >
                        Zaboravili ste lozinku?
                      </Link>
                    </div>
                    <FormControl>
                      <Input
                        type="password"
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
                    Prijavljivanje...
                  </>
                ) : (
                  "Prijavite se"
                )}
              </Button>
            </form>
          </Form>
        </CardContent>

        <CardFooter className="justify-center text-sm text-muted-foreground">
          Nemate nalog?&nbsp;
          <Link
            href="/register"
            className="font-medium text-primary hover:underline underline-offset-4"
          >
            Registrujte se
          </Link>
        </CardFooter>
      </Card>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Učitavanje...</div>}>
      <LoginForm />
    </Suspense>
  )
}