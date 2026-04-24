/**
 * file-validation.ts — MIME + size checks for upload dropzones.
 *
 * Mirrors backend FilesService limits. A failed check returns a Serbian
 * user-facing error string so it can be piped straight into a toast or
 * react-hook-form error.
 */

import {
  ACCEPTED_FILE_TYPES,
  MAX_FILE_SIZE,
} from "@/lib/constants/accepted-mime-types"
import { formatFileSize } from "./file-size"

export interface FileValidationError {
  code: "FILE_TOO_LARGE" | "INVALID_MIME"
  message: string
}

export function validateFile(file: File): FileValidationError | null {
  if (file.size > MAX_FILE_SIZE) {
    return {
      code: "FILE_TOO_LARGE",
      message: `Fajl je prevelik (maks ${formatFileSize(MAX_FILE_SIZE)}).`,
    }
  }

  const acceptedMimes = Object.keys(ACCEPTED_FILE_TYPES)
  if (!acceptedMimes.includes(file.type)) {
    return {
      code: "INVALID_MIME",
      message: `Format fajla '${file.type || "nepoznat"}' nije dozvoljen.`,
    }
  }

  return null
}

export function validateFiles(files: File[]): FileValidationError | null {
  for (const file of files) {
    const err = validateFile(file)
    if (err) return err
  }
  return null
}
