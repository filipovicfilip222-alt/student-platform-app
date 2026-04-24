/**
 * use-appointments.ts — Student appointment queries + mutations.
 */

"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  studentsApi,
  type MyAppointmentsView,
} from "@/lib/api/students"
import { appointmentsApi } from "@/lib/api/appointments"
import type { AppointmentCreateRequest, Uuid } from "@/types"

const invalidateAppointments = (qc: ReturnType<typeof useQueryClient>) => {
  qc.invalidateQueries({ queryKey: ["my-appointments"] })
  qc.invalidateQueries({ queryKey: ["appointment"] })
}

export function useMyAppointments(view: MyAppointmentsView = "upcoming") {
  return useQuery({
    queryKey: ["my-appointments", view] as const,
    queryFn: () => studentsApi.listMyAppointments(view),
    staleTime: 30 * 1000,
  })
}

export function useAppointmentDetail(id: Uuid | null | undefined) {
  return useQuery({
    queryKey: ["appointment", id] as const,
    queryFn: () => appointmentsApi.getDetail(id as Uuid),
    enabled: Boolean(id),
  })
}

export function useCreateAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AppointmentCreateRequest) =>
      studentsApi.createAppointment(data),
    onSuccess: (_, variables) => {
      invalidateAppointments(qc)
      qc.invalidateQueries({
        queryKey: ["professors", "slots"],
        predicate: (q) => q.queryKey.includes(variables.slot_id),
      })
    },
  })
}

export function useCancelAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: Uuid) => studentsApi.cancelAppointment(id),
    onSuccess: () => invalidateAppointments(qc),
  })
}
