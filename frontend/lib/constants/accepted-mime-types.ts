/**
 * accepted-mime-types.ts — Allowed upload formats (student → appointment files).
 *
 * Keep in sync with backend FilesService MIME whitelist + max_size limit.
 * Structured as react-dropzone expects: `{ mime: [extensions] }`.
 */

export const ACCEPTED_FILE_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "application/zip": [".zip"],
  "text/x-python": [".py"],
  "text/x-java-source": [".java"],
  "text/x-c++src": [".cpp"],
}

export const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5 MB
