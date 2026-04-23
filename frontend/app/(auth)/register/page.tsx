"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { authApi } from "@/lib/api/auth"

// ── Constants (mirror backend CLAUDE.md §4) ─────────────────────────────────

const STUDENT_DOMAINS = ["student.fon.bg.ac.rs", "student.etf.bg.ac.rs"]
const STAFF_DOMAINS = ["fon.bg.ac.rs", "etf.bg.ac.rs"]

function getEmailDomain(email: string) {
  return email.split("@")[1]?.toLowerCase() ?? ""
}

// ── Zod schema ─────────────────────────────────────────────────────────────────

const registerSchema = z
  .object({
    first_name: z
      .string()
      .min(1, "Ime je obavezno.")
      .max(100, "Ime ne sme biti duže od 100 karaktera."),
    last_name: z
      .string()
      .min(1, "Prezime je obavezno.")
      .max(100, "Prezime ne sme biti duže od 100 karaktera."),
    email: z
      .string()
      .min(1, "Email je obavezan.")
      .email("Unesite ispravnu email adresu.")
      .refine(
        (email) => {
          const domain = getEmailDomain(email)
          // Self-registration only for student domains
          if (STAFF_DOMAINS.includes(domain)) return false
          return STUDENT_DOMAINS.includes(domain)
        },
        {
          message:
            "Registracija je dozvoljena samo sa studentskim email adresama " +
            "(@student.fon.bg.ac.rs ili @student.etf.bg.ac.rs). " +
            "Nalozi za osoblje se kreiraju od strane administratora.",
        }
      ),
    password: z
      .string()
      .min(8, "Lozinka mora imati najmanje 8 karaktera.")
      .max(128, "Lozinka ne sme biti duža od 128 karaktera."),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Lozinke se ne podudaraju.",
    path: ["confirmPassword"],
  })

type RegisterFormValues = z.infer<typeof registerSchema>

// ── Component ──────────────────────────────────────────────────────────────────

export default function RegisterPage() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  })

  const { isSubmitting } = form.formState

  async function onSubmit(values: RegisterFormValues) {
    setServerError(null)
    try {
      await authApi.register({
        email: values.email,
        password: values.password,
        first_name: values.first_name,
        last_name: values.last_name,
      })
      setSuccess(true)
      // Redirect to login after a short delay so user sees the success message
      setTimeout(() => router.replace("/login"), 2500)
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      const msg =
        axiosErr.response?.data?.detail ??
        "Greška pri registraciji. Pokušajte ponovo."
      setServerError(msg)
    }
  }

  // ── Success state ────────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4">
        <Card className="w-full max-w-md shadow-lg text-center">
          <CardHeader>
            <CardTitle className="text-xl text-green-600">Registracija uspešna!</CardTitle>
            <CardDescription>
              Vaš nalog je kreiran. Preusmeravamo Vas na stranicu za prijavu...
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 px-4 py-8">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-2xl font-bold">Registracija</CardTitle>
          <CardDescription>
            Kreirajte nalog sa Vašom studentskom email adresom
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

              {/* Name row */}
              <div className="grid grid-cols-2 gap-3">
                <FormField
                  control={form.control}
                  name="first_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Ime</FormLabel>
                      <FormControl>
                        <Input placeholder="Marko" autoComplete="given-name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="last_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Prezime</FormLabel>
                      <FormControl>
                        <Input placeholder="Petrović" autoComplete="family-name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Studentski email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        placeholder="ime.prezime@student.fon.bg.ac.rs"
                        autoComplete="email"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      Dozvoljenе adrese: @student.fon.bg.ac.rs i @student.etf.bg.ac.rs
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Lozinka</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="Minimum 8 karaktera"
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
                name="confirmPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Potvrda lozinke</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="Ponovite lozinku"
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
                    Kreiranje naloga...
                  </>
                ) : (
                  "Kreiraj nalog"
                )}
              </Button>
            </form>
          </Form>
        </CardContent>

        <CardFooter className="justify-center text-sm text-muted-foreground">
          Već imate nalog?&nbsp;
          <Link
            href="/login"
            className="font-medium text-primary hover:underline underline-offset-4"
          >
            Prijavite se
          </Link>
        </CardFooter>
      </Card>
    </div>
  )
}
