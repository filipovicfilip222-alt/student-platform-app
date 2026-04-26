"""MinIO file service for appointment uploads (Faza 3.3).

The official ``minio`` Python SDK is synchronous, so blocking I/O calls are
wrapped with ``asyncio.to_thread`` to keep the FastAPI event loop free
(CLAUDE.md §3 — "sve mora biti async").

Public surface:
    validate_upload(filename, mime_type, size_bytes) -> None
        Raises HTTPException(422) on bad MIME, HTTPException(413) on > 5 MB.
    upload_appointment_file(appointment_id, file_uuid, filename, data, mime_type)
        Uploads bytes to the ``appointment-files`` bucket and returns the
        ``minio_object_key`` to be persisted on the ``files`` row.
    presigned_get_url(object_key, ttl_seconds=3600) -> str
        Returns a time-limited download URL. Used by ``GET /{id}/files``.
    delete_object(object_key) -> None
        Removes the object from MinIO. Used by ``DELETE /{id}/files/{file_id}``.

Bucket setup lives in ``infra/minio/init-buckets.sh``. The
``appointment-files`` bucket is private (anonymous=none); access happens
exclusively through presigned URLs.
"""

import asyncio
import io
import re
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status
from minio import Minio
from minio.error import S3Error

from app.core.config import settings


# ── Constants ────────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # PRD §2.2 — 5MB hard limit

# PRD §2.2 + CURSOR_PROMPT_1 §1.3 — explicit allowlist; everything else → 422.
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/png",
        "image/jpeg",
        "application/zip",
        "text/x-python",
        "text/x-java-source",
        "text/x-c++src",
    }
)

_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._\-]")
_MAX_FILENAME_LEN = 200


# ── MinIO client (lazy singleton) ─────────────────────────────────────────────


_minio_client: Minio | None = None


def _get_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _minio_client


# ── Helpers ──────────────────────────────────────────────────────────────────


def _sanitize_filename(filename: str) -> str:
    """Strip path traversal, control chars, and exotic glyphs from a filename.

    The result is safe to embed in an S3 object key. We keep the original
    extension where possible — the MIME whitelist is the authoritative file
    type guard, the filename is purely for UX.
    """
    name = (filename or "").strip().replace("\\", "/").split("/")[-1]
    name = _FILENAME_SANITIZE_RE.sub("_", name)
    name = name.strip("._")
    if not name:
        name = "file"
    return name[:_MAX_FILENAME_LEN]


def _build_object_key(appointment_id: UUID, file_uuid: UUID, filename: str) -> str:
    """Return ``{appointment_id}/{file_uuid}__{sanitized_filename}``."""
    safe = _sanitize_filename(filename)
    return f"{appointment_id}/{file_uuid}__{safe}"


# ── Public API ───────────────────────────────────────────────────────────────


def validate_upload(filename: str, mime_type: str, size_bytes: int) -> None:
    """Raise HTTPException for unsupported MIME (422) or oversized files (413).

    PRD §2.2: hard cap at 5MB; allowlist enforced by ``ALLOWED_MIME_TYPES``.
    Note that 413 is returned for size violations (not 422) to match the
    acceptance criteria in CURSOR_PROMPT_1 §1.4.
    """
    if size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fajl je veći od 5MB.",
        )
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nepodržan tip fajla: {mime_type or 'unknown'}.",
        )
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fajl mora imati naziv.",
        )


async def upload_appointment_file(
    appointment_id: UUID,
    file_uuid: UUID,
    filename: str,
    data: bytes,
    mime_type: str,
) -> str:
    """Upload ``data`` to the appointment-files bucket. Returns the object key.

    Caller is responsible for invoking ``validate_upload`` first.
    """
    object_key = _build_object_key(appointment_id, file_uuid, filename)
    bucket = settings.MINIO_BUCKET_APPOINTMENTS
    client = _get_client()

    def _put() -> None:
        client.put_object(
            bucket_name=bucket,
            object_name=object_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=mime_type,
        )

    try:
        await asyncio.to_thread(_put)
    except S3Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Greška pri snimanju fajla: {exc.code}",
        ) from exc

    return object_key


async def presigned_get_url(object_key: str, ttl_seconds: int = 3600) -> str:
    """Return a presigned GET URL for an existing object (default TTL 1h)."""
    bucket = settings.MINIO_BUCKET_APPOINTMENTS
    client = _get_client()

    def _sign() -> str:
        return client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_key,
            expires=timedelta(seconds=ttl_seconds),
        )

    try:
        return await asyncio.to_thread(_sign)
    except S3Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Greška pri generisanju URL-a: {exc.code}",
        ) from exc


async def delete_object(object_key: str) -> None:
    """Remove an object from the appointment-files bucket. Idempotent."""
    bucket = settings.MINIO_BUCKET_APPOINTMENTS
    client = _get_client()

    def _remove() -> None:
        client.remove_object(bucket_name=bucket, object_name=object_key)

    try:
        await asyncio.to_thread(_remove)
    except S3Error as exc:
        # NoSuchKey is treated as a successful no-op so retries are safe.
        if exc.code == "NoSuchKey":
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Greška pri brisanju fajla: {exc.code}",
        ) from exc
