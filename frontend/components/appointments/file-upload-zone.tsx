/**
 * file-upload-zone.tsx — react-dropzone wrapper for appointment uploads.
 *
 * ROADMAP 3.5 / Faza 3.5. Enforces client-side MIME + size limits that
 * match the backend whitelist (5 MB, specific MIMEs). Shows a chip per
 * staged file with size + remove button. Dropping the same filename
 * twice is rejected to avoid ambiguity on the server.
 */

"use client"

import { useCallback } from "react"
import { useDropzone, type FileRejection } from "react-dropzone"
import { FileIcon, Upload, X } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  ACCEPTED_FILE_TYPES,
  MAX_FILE_SIZE,
} from "@/lib/constants/accepted-mime-types"
import { formatFileSize } from "@/lib/utils/file-size"
import { validateFile } from "@/lib/utils/file-validation"

function toastError(message: string) {
  toast.error(message)
}

export interface FileUploadZoneProps {
  files: File[]
  onChange: (files: File[]) => void
  disabled?: boolean
  maxFiles?: number
  className?: string
}

export function FileUploadZone({
  files,
  onChange,
  disabled = false,
  maxFiles = 5,
  className,
}: FileUploadZoneProps) {
  const onDrop = useCallback(
    (accepted: File[], rejections: FileRejection[]) => {
      if (rejections.length > 0) {
        const first = rejections[0]
        toastError(
          first.errors[0]?.message ||
            `Fajl ${first.file.name} nije dozvoljen.`
        )
      }

      const seen = new Set(files.map((f) => `${f.name}|${f.size}`))
      const next: File[] = [...files]

      for (const file of accepted) {
        if (next.length >= maxFiles) {
          toastError(`Maksimalno ${maxFiles} fajl(ov)a po zahtevu.`)
          break
        }
        const err = validateFile(file)
        if (err) {
          toastError(`${file.name}: ${err.message}`)
          continue
        }
        const key = `${file.name}|${file.size}`
        if (seen.has(key)) continue
        seen.add(key)
        next.push(file)
      }

      if (next.length !== files.length) {
        onChange(next)
      }
    },
    [files, maxFiles, onChange]
  )

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    disabled,
    noClick: true,
    noKeyboard: true,
  })

  function removeAt(index: number) {
    onChange(files.filter((_, i) => i !== index))
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div
        {...getRootProps()}
        data-active={isDragActive}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-input bg-muted/40 p-5 text-center transition-colors",
          "data-[active=true]:border-primary data-[active=true]:bg-primary/5",
          disabled && "cursor-not-allowed opacity-60"
        )}
      >
        <input {...getInputProps()} />
        <Upload
          className="size-5 text-muted-foreground"
          aria-hidden
        />
        <p className="text-xs text-muted-foreground">
          Prevucite fajlove ovde ili
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={open}
          disabled={disabled}
        >
          Izaberite fajlove
        </Button>
        <p className="text-[10px] text-muted-foreground">
          PDF, DOCX, XLSX, PNG, JPG, ZIP, PY, JAVA, CPP · maks {formatFileSize(MAX_FILE_SIZE)}
        </p>
      </div>

      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${index}`}
              className="flex items-center justify-between gap-2 rounded-md border border-border/70 bg-card px-3 py-2 text-xs"
            >
              <div className="flex min-w-0 items-center gap-2">
                <FileIcon
                  className="size-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
                <span className="truncate font-medium text-foreground">
                  {file.name}
                </span>
                <span className="shrink-0 text-muted-foreground">
                  {formatFileSize(file.size)}
                </span>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => removeAt(index)}
                disabled={disabled}
                aria-label={`Ukloni ${file.name}`}
              >
                <X aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
