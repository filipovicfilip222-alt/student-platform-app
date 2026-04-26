from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str
    POSTGRES_USER: str = "studentska"
    POSTGRES_PASSWORD: str = "studentska_pass"
    POSTGRES_DB: str = "studentska_platforma"

    # ── Redis ──────────────────────────────────────────────────────────────────
    REDIS_URL: str
    REDIS_PASSWORD: str = ""

    # ── JWT / Security ─────────────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Welcome email (admin-created user) reset-token TTL (Faza 4.3).
    # Duži TTL od standardnog forgot-password (1h) jer admin može da kreira
    # nalog u petak za poziv u ponedeljak — korisnik mora imati vremena.
    WELCOME_RESET_TOKEN_TTL_DAYS: int = 7
    # Impersonation access token TTL (Faza 4.4 / CLAUDE.md §14).
    # Kraći je od regularnog access tokena jer se NE refresh-uje — kad istekne,
    # admin mora ručno re-impersonirati. Krije security gap od dugotrajnog
    # admin-as-X session-a koji se "ne primeti".
    IMPERSONATION_TOKEN_TTL_MINUTES: int = 30

    # ── MinIO ──────────────────────────────────────────────────────────────────
    # MINIO_ENDPOINT is the *internal* address backend uses for server-side I/O
    # (put/get/delete) — Docker DNS name resolves only inside the compose net.
    # MINIO_PUBLIC_ENDPOINT is what the browser / external curl will see in the
    # presigned URL host. Keep both so presigning + S3 ops use the right host.
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    # Setting region avoids a synchronous ``GetBucketLocation`` round-trip the
    # SDK otherwise performs before signing presigned URLs. The public client
    # cannot reach localhost:9000 from inside the backend container, so without
    # this the presign call fails with a 500.
    MINIO_REGION: str = "us-east-1"
    MINIO_BUCKET_APPOINTMENTS: str = "appointment-files"
    MINIO_BUCKET_AVATARS: str = "professor-avatars"
    MINIO_BUCKET_IMPORTS: str = "bulk-imports"
    MINIO_BUCKET_DOCUMENTS: str = "document-requests"
    MINIO_SECURE: bool = False

    # ── SMTP ───────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@fon.bg.ac.rs"
    EMAILS_FROM_NAME: str = "StudentPlus"

    # ── Google PSE ─────────────────────────────────────────────────────────────
    GOOGLE_PSE_API_KEY: str = ""
    GOOGLE_PSE_CX: str = ""

    # ── Email Domain Whitelist ─────────────────────────────────────────────────
    # Comma-separated string, parsed into list by validator
    ALLOWED_STUDENT_DOMAINS: str = "student.fon.bg.ac.rs,student.etf.bg.ac.rs"
    ALLOWED_STAFF_DOMAINS: str = "fon.bg.ac.rs,etf.bg.ac.rs"

    # ── Application ────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ── Web Push / VAPID (KORAK 1 Prompta 2 / PRD §5.3) ───────────────────────
    # VAPID par je generisan ``scripts/generate_vapid_keys.py``-jem (DER →
    # base64-url enkodiranje). Javni ključ se izlaže preko
    # ``GET /api/v1/notifications/vapid-public-key`` i koristi u browseru
    # za ``PushManager.subscribe({applicationServerKey: ...})``. Privatni
    # ključ NIKAD ne napušta server — koristi ga ``pywebpush`` da potpiše
    # JWT pre slanja Web Push poruke.
    #
    # Default vrednosti su prazni stringovi (ne crash-uje boot ako fale),
    # ali ``push_service.send_push`` će logovati warning + skipovati slanje
    # ako VAPID_PRIVATE_KEY nije postavljen — fallback ponašanje za
    # razvojno okruženje pre nego što developer pokrene generate skriptu.
    #
    # Format ``VAPID_SUBJECT``: ``mailto:dev@example.com`` ili
    # ``https://example.com``. Push servisi (FCM/Mozilla) traže ovo polje
    # kao kontakt informaciju za slučaj abuse-a.
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:dev@studentska-platforma.local"

    @field_validator("ALLOWED_STUDENT_DOMAINS", "ALLOWED_STAFF_DOMAINS", mode="before")
    @classmethod
    def parse_comma_list(cls, v: str) -> str:
        # Keep as string; use the property methods below for list access
        return v

    @property
    def student_domains(self) -> List[str]:
        return [d.strip() for d in self.ALLOWED_STUDENT_DOMAINS.split(",") if d.strip()]

    @property
    def staff_domains(self) -> List[str]:
        return [d.strip() for d in self.ALLOWED_STAFF_DOMAINS.split(",") if d.strip()]

    @property
    def all_allowed_domains(self) -> List[str]:
        return self.student_domains + self.staff_domains


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
