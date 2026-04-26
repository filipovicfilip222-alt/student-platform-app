"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { CheckCircle2, Loader2, MailCheck } from "lucide-react"
import type { AxiosError } from "axios"

import { PasswordStrengthMeter } from "@/components/auth/password-strength-meter"
import { Logo } from "@/components/shared/logo"
import { Button } from "@/components/ui/button"
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
import { PasswordInput } from "@/components/ui/password-input"
import { authApi } from "@/lib/api/auth"
import { ROUTES } from "@/lib/constants/routes"
import { cn } from "@/lib/utils"

// Mirror backend CLAUDE.md §4.
const STUDENT_DOMAINS = ["student.fon.bg.ac.rs", "student.etf.bg.ac.rs"]
const STAFF_DOMAINS = ["fon.bg.ac.rs", "etf.bg.ac.rs"]

function getEmailDomain(email: string) {
  return email.split("@")[1]?.toLowerCase() ?? ""
}

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

type DomainHint =
  | { tone: "neutral"; text: string }
  | { tone: "ok"; text: string; faculty: "FON" | "ETF" }
  | { tone: "error"; text: string }

function buildDomainHint(email: string): DomainHint {
  if (!email.includes("@")) {
    return {
      tone: "neutral",
      text: "Dozvoljene adrese: @student.fon.bg.ac.rs i @student.etf.bg.ac.rs",
    }
  }
  const domain = getEmailDomain(email)
  if (!domain) {
    return { tone: "neutral", text: "Nastavite sa upisivanjem domena…" }
  }
  if (domain === "student.fon.bg.ac.rs") {
    return { tone: "ok", faculty: "FON", text: "Studentski FON nalog prepoznat." }
  }
  if (domain === "student.etf.bg.ac.rs") {
    return { tone: "ok", faculty: "ETF", text: "Studentski ETF nalog prepoznat." }
  }
  if (STAFF_DOMAINS.includes(domain)) {
    return {
      tone: "error",
      text: "Profesori i asistenti dobijaju nalog od administratora.",
    }
  }
  return {
    tone: "error",
    text: "Domen nije dozvoljen. Koristite studentski FON ili ETF email.",
  }
}

export default function RegisterPage() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [shakeKey, setShakeKey] = useState(0)

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
    mode: "onTouched",
  })

  const { isSubmitting } = form.formState

  const emailValue = form.watch("email")
  const passwordValue = form.watch("password")
  const domainHint = useMemo(() => buildDomainHint(emailValue), [emailValue])

  useEffect(() => {
    if (serverError) setShakeKey((k) => k + 1)
  }, [serverError])

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
      setTimeout(() => router.replace(ROUTES.login), 2500)
    } catch (err) {
      const axiosErr = err as AxiosError<{ detail: string }>
      const msg =
        axiosErr.response?.data?.detail ??
        "Greška pri registraciji. Pokušajte ponovo."
      setServerError(msg)
    }
  }

  if (success) {
    return (
      <div className="space-y-6 text-center">
        <Logo
          variant="full"
          size="lg"
          className="mx-auto justify-center lg:hidden"
        />
        <div className="flex flex-col items-center gap-4 rounded-xl border border-success/30 bg-success/10 px-6 py-10">
          <MailCheck className="size-12 text-success" aria-hidden />
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">Registracija uspešna</h2>
            <p className="text-sm text-muted-foreground">
              Nalog je kreiran. Preusmeravamo vas na stranicu za prijavu…
            </p>
          </div>
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
        <h1 className="text-3xl font-bold tracking-tight">Kreiraj nalog</h1>
        <p className="text-sm text-muted-foreground">
          Studentski FON ili ETF email je obavezan.
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

          <div className="grid grid-cols-2 gap-3">
            <FormField
              control={form.control}
              name="first_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Ime</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Marko"
                      autoComplete="given-name"
                      {...field}
                    />
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
                    <Input
                      placeholder="Petrović"
                      autoComplete="family-name"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="email"
            render={({ field, fieldState }) => (
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
                {!fieldState.error && (
                  <FormDescription
                    className={cn(
                      "flex items-center gap-1.5",
                      domainHint.tone === "ok" && "text-success",
                      domainHint.tone === "error" && "text-destructive"
                    )}
                  >
                    {domainHint.tone === "ok" && (
                      <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />
                    )}
                    <span>{domainHint.text}</span>
                  </FormDescription>
                )}
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
                  <PasswordInput
                    placeholder="Minimum 8 karaktera"
                    autoComplete="new-password"
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
            name="confirmPassword"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Potvrda lozinke</FormLabel>
                <FormControl>
                  <PasswordInput
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
                Kreiram nalog...
              </>
            ) : (
              "Kreiraj nalog"
            )}
          </Button>
        </form>
      </Form>

      <p className="text-center text-sm text-muted-foreground">
        Već imate nalog?{" "}
        <Link
          href={ROUTES.login}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Prijavite se
        </Link>
      </p>
    </div>
  )
}
