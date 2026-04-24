/**
 * errors.ts — Centralised API error → toast mapping.
 *
 * FastAPI returns errors as { detail: string } for single messages or
 * { detail: [{ msg, loc, ... }] } for Pydantic validation errors. We unwrap
 * both shapes and surface a single human-readable message through `sonner`.
 */

import axios from "axios"
import { toast } from "sonner"

interface FastApiValidationError {
  loc: (string | number)[]
  msg: string
  type: string
}

interface FastApiErrorBody {
  detail?: string | FastApiValidationError[]
}

function extractDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null
  const detail = (body as FastApiErrorBody).detail

  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((e) => e.msg).join("; ")
  }
  return null
}

/**
 * Display an API error as a destructive toast. Always safe to call with any
 * value — including network errors or non-Axios throwables.
 */
export function toastApiError(err: unknown, fallback = "Nepoznata greška"): void {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status
    const detail = extractDetail(err.response?.data) ?? err.message ?? fallback
    const title =
      status === 401
        ? "Niste prijavljeni"
        : status === 403
          ? "Zabranjen pristup"
          : status === 404
            ? "Nije pronađeno"
            : status === 409
              ? "Konflikt"
              : status === 422
                ? "Neispravni podaci"
                : "Greška"
    toast.error(title, { description: detail })
    return
  }

  if (err instanceof Error) {
    toast.error(fallback, { description: err.message })
    return
  }

  toast.error(fallback)
}

export function toastSuccess(message: string, description?: string): void {
  toast.success(message, description ? { description } : undefined)
}
