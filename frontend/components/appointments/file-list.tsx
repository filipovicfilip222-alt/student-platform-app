/**
 * file-list.tsx — Lists uploaded files for an appointment.
 *
 * ROADMAP 3.6 / Faza 3.6.
 *
 * Behaviors:
 *   - Download: uses `file.download_url` (presigned MinIO link) when
 *     present. Opens in a new tab so uploads don't navigate away.
 *   - Delete:   only visible for the uploader. Confirms inline via the
 *     native confirm() — no dialog library needed for a single action.
 *   - Upload:   delegated to <FileUploadZone /> when `canUpload=true`.
 */

"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, FileIcon, Loader2, Paperclip, Trash2 } from "lucide-react"

import { FileUploadZone } from "./file-upload-zone"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { appointmentsApi } from "@/lib/api/appointments"
import { useAuthStore } from "@/lib/stores/auth"
import { formatFileSize } from "@/lib/utils/file-size"
import { formatDateTime } from "@/lib/utils/date"
import { toastApiError, toastSuccess } from "@/lib/utils/errors"
import type { FileResponse, Uuid } from "@/types"

export interface FileListProps {
  appointmentId: Uuid
  canUpload?: boolean
}

export function FileList({ appointmentId, canUpload = true }: FileListProps) {
  const qc = useQueryClient()
  const currentUserId = useAuthStore((s) => s.user?.id ?? null)
  const [stagedFiles, setStagedFiles] = useState<File[]>([])

  const filesQuery = useQuery({
    queryKey: ["appointment", appointmentId, "files"] as const,
    queryFn: () => appointmentsApi.listFiles(appointmentId),
  })

  const files: FileResponse[] = filesQuery.data ?? []

  const uploadMutation = useMutation({
    mutationFn: async (toUpload: File[]) => {
      const uploaded: FileResponse[] = []
      for (const f of toUpload) {
        const res = await appointmentsApi.uploadFile(appointmentId, f)
        uploaded.push(res)
      }
      return uploaded
    },
    onSuccess: (uploaded) => {
      qc.invalidateQueries({
        queryKey: ["appointment", appointmentId, "files"],
      })
      qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
      toastSuccess(`Uploadovano fajlova: ${uploaded.length}.`)
      setStagedFiles([])
    },
    onError: (err) => toastApiError(err, "Greška pri uploadu fajla."),
  })

  const deleteMutation = useMutation({
    mutationFn: (fileId: Uuid) =>
      appointmentsApi.deleteFile(appointmentId, fileId),
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["appointment", appointmentId, "files"],
      })
      qc.invalidateQueries({ queryKey: ["appointment", appointmentId] })
      toastSuccess("Fajl je obrisan.")
    },
    onError: (err) => toastApiError(err, "Greška pri brisanju fajla."),
  })

  function handleUpload() {
    if (stagedFiles.length === 0) return
    uploadMutation.mutate(stagedFiles)
  }

  function handleDelete(file: FileResponse) {
    if (!window.confirm(`Obrisati fajl "${file.filename}"?`)) return
    deleteMutation.mutate(file.id)
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between border-b p-4">
        <CardTitle className="inline-flex items-center gap-2 text-base font-semibold">
          <Paperclip className="size-4 text-muted-foreground" aria-hidden />
          Prilozi
        </CardTitle>
        <span className="text-xs text-muted-foreground tabular-nums">
          {files.length}
        </span>
      </CardHeader>

      <CardContent className="space-y-4 p-4">
        {filesQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 rounded-md" />
            <Skeleton className="h-12 rounded-md" />
          </div>
        ) : filesQuery.isError ? (
          <p className="text-xs text-muted-foreground">
            Fajlovi nedostupni (očekuje se backend ROADMAP 3.6).
          </p>
        ) : files.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Još uvek nema priloga.
          </p>
        ) : (
          <ul className="space-y-2">
            {files.map((file) => {
              const isOwner = file.uploaded_by === currentUserId
              return (
                <li
                  key={file.id}
                  className="flex items-center gap-2 rounded-md border border-border/70 p-3"
                >
                  <FileIcon
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {file.filename}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {formatFileSize(file.file_size_bytes)} ·{" "}
                      {formatDateTime(file.created_at)}
                    </p>
                  </div>
                  {file.download_url && (
                    <Button
                      asChild
                      type="button"
                      variant="outline"
                      size="icon-sm"
                      aria-label={`Preuzmi ${file.filename}`}
                    >
                      <a
                        href={file.download_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Download aria-hidden />
                      </a>
                    </Button>
                  )}
                  {isOwner && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      disabled={deleteMutation.isPending}
                      onClick={() => handleDelete(file)}
                      aria-label={`Obriši ${file.filename}`}
                    >
                      {deleteMutation.isPending ? (
                        <Loader2 className="animate-spin" aria-hidden />
                      ) : (
                        <Trash2 aria-hidden />
                      )}
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        )}

        {canUpload && (
          <div className="space-y-2 border-t pt-4">
            <FileUploadZone
              files={stagedFiles}
              onChange={setStagedFiles}
              disabled={uploadMutation.isPending}
            />
            {stagedFiles.length > 0 && (
              <Button
                type="button"
                size="sm"
                onClick={handleUpload}
                disabled={uploadMutation.isPending}
              >
                {uploadMutation.isPending && (
                  <Loader2 className="animate-spin" aria-hidden />
                )}
                Uploaduj ({stagedFiles.length})
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
