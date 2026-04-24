/**
 * profile-form.tsx — Professor self-profile editor (settings → Profil tab).
 *
 * ROADMAP 3.7 / Faza 4 (frontend). Maps 1:1 to `ProfessorProfileUpdate`
 * on the backend. Wires into `useMyProfessorProfile` + `useUpdateMyProfile`
 * — both 404 until the backend endpoints ship, in which case the form
 * renders an EmptyState instead of the editor.
 */

"use client"

import { useEffect } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { Loader2, UserCog } from "lucide-react"

import { EmptyState } from "@/components/shared/empty-state"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
  useMyProfessorProfile,
  useUpdateMyProfile,
} from "@/lib/hooks/use-my-profile"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { ProfessorProfileUpdate } from "@/types"

import { AreasOfInterestInput } from "./areas-of-interest-input"

const schema = z.object({
  title: z
    .string()
    .trim()
    .min(2, "Zvanje mora imati najmanje 2 karaktera.")
    .max(100),
  department: z
    .string()
    .trim()
    .min(2, "Katedra mora imati najmanje 2 karaktera.")
    .max(120),
  office: z.string().trim().max(80).optional(),
  office_description: z.string().trim().max(500).optional(),
  areas_of_interest: z.array(z.string().min(1)).max(20),
  auto_approve_recurring: z.boolean(),
  auto_approve_special: z.boolean(),
  buffer_minutes: z
    .number({ invalid_type_error: "Buffer mora biti broj." })
    .int("Buffer mora biti ceo broj.")
    .min(0, "Buffer ne može biti negativan.")
    .max(60, "Buffer ne sme biti veći od 60 minuta."),
})

type FormValues = z.infer<typeof schema>

const DEFAULTS: FormValues = {
  title: "",
  department: "",
  office: "",
  office_description: "",
  areas_of_interest: [],
  auto_approve_recurring: false,
  auto_approve_special: false,
  buffer_minutes: 10,
}

export function ProfileForm() {
  const profileQuery = useMyProfessorProfile()
  const updateMutation = useUpdateMyProfile()

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULTS,
  })

  useEffect(() => {
    const data = profileQuery.data
    if (!data) return
    form.reset({
      title: data.title ?? "",
      department: data.department ?? "",
      office: data.office ?? "",
      office_description: data.office_description ?? "",
      areas_of_interest: data.areas_of_interest ?? [],
      auto_approve_recurring: data.auto_approve_recurring ?? false,
      auto_approve_special: data.auto_approve_special ?? false,
      buffer_minutes: data.buffer_minutes ?? 10,
    })
  }, [profileQuery.data, form])

  if (profileQuery.isLoading) {
    return (
      <Card>
        <CardContent className="space-y-4 p-6">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    )
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <EmptyState
        icon={UserCog}
        title="Profil trenutno nije dostupan"
        description="Endpoint za profesorski profil još nije aktivan (backend u izradi)."
      />
    )
  }

  function handleSubmit(values: FormValues) {
    const payload: ProfessorProfileUpdate = {
      title: values.title,
      department: values.department,
      office: values.office?.trim() ? values.office : null,
      office_description: values.office_description?.trim()
        ? values.office_description
        : null,
      areas_of_interest: values.areas_of_interest,
      auto_approve_recurring: values.auto_approve_recurring,
      auto_approve_special: values.auto_approve_special,
      buffer_minutes: values.buffer_minutes,
    }
    updateMutation.mutate(payload, {
      onSuccess: () => toastSuccess("Profil sačuvan."),
      onError: (err) => toastApiError(err, "Greška pri čuvanju profila."),
    })
  }

  const profile = profileQuery.data

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleSubmit)}
        className="space-y-5"
        noValidate
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Osnovni podaci</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <FormItem>
              <FormLabel>Ime i prezime</FormLabel>
              <Input value={profile.full_name} readOnly disabled />
              <FormDescription>
                Menja se kroz administraciju korisnika.
              </FormDescription>
            </FormItem>
            <FormItem>
              <FormLabel>Email</FormLabel>
              <Input value={profile.email} readOnly disabled />
            </FormItem>

            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Zvanje</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Redovni profesor"
                      disabled={updateMutation.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="department"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Katedra</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Katedra za matematiku"
                      disabled={updateMutation.isPending}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="office"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Kancelarija</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Zgrada B, kancelarija 114"
                      disabled={updateMutation.isPending}
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="office_description"
              render={({ field }) => (
                <FormItem className="md:col-span-2">
                  <FormLabel>Opis kancelarije (opciono)</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={2}
                      placeholder="Ulaz preko glavnog holla, prvi sprat..."
                      disabled={updateMutation.isPending}
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Oblasti interesovanja</CardTitle>
          </CardHeader>
          <CardContent>
            <FormField
              control={form.control}
              name="areas_of_interest"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Teme za konsultacije</FormLabel>
                  <FormControl>
                    <AreasOfInterestInput
                      value={field.value}
                      onChange={field.onChange}
                      disabled={updateMutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    Maks. 20 stavki. Pritisnite Enter ili zarez da dodate.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Automatsko odobravanje</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="auto_approve_recurring"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <FormLabel className="text-sm">
                      Redovni termini (iz recurring rule)
                    </FormLabel>
                    <FormDescription className="text-xs">
                      Automatski odobri zahteve koji padaju u standardan
                      termin konsultacija.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={updateMutation.isPending}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="auto_approve_special"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                  <div className="space-y-0.5">
                    <FormLabel className="text-sm">
                      Specijalni (ad-hoc) termini
                    </FormLabel>
                    <FormDescription className="text-xs">
                      Automatski odobri jednokratne slotove kreirane van
                      standardnog rasporeda.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={updateMutation.isPending}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="buffer_minutes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Buffer između konsultacija (min)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={0}
                      max={60}
                      disabled={updateMutation.isPending}
                      {...field}
                      value={field.value}
                      onChange={(e) => field.onChange(Number(e.target.value))}
                    />
                  </FormControl>
                  <FormDescription>
                    Minimalan razmak između dva zakazana termina.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={updateMutation.isPending}>
            {updateMutation.isPending && (
              <Loader2 className="animate-spin" aria-hidden />
            )}
            Sačuvaj izmene
          </Button>
        </div>
      </form>
    </Form>
  )
}
