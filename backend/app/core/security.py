from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as aioredis
from jose import JWTError, jwt

from app.core.config import settings

import bcrypt


# ── Password helpers ───────────────────────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )




# ── JWT helpers ────────────────────────────────────────────────────────────────

def create_access_token(
    data: dict[str, Any],
    expires_minutes: int | None = None,
) -> str:
    """
    Create a signed access JWT.

    ``data`` may carry arbitrary custom claims (npr. ``imp``, ``imp_email``,
    ``imp_name`` za impersonation tokene — Faza 4.4) — sva proslijeđena polja
    završavaju u payload-u i čitaju se kroz :func:`decode_access_token`.

    ``expires_minutes`` opciono override-uje default ``ACCESS_TOKEN_EXPIRE_MINUTES``.
    Impersonation tokeni koriste :data:`settings.IMPERSONATION_TOKEN_TTL_MINUTES`
    (30 min) jer ne idu kroz refresh rotaciju (CLAUDE.md §14).
    """
    payload = data.copy()
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any]) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def decode_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("Token type mismatch: expected access token")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("Token type mismatch: expected refresh token")
    return payload


# ── Email domain validation (from CLAUDE.md §4) ────────────────────────────────

def get_domain(email: str) -> str:
    return email.split("@")[1].lower()


def is_student_email(email: str) -> bool:
    return get_domain(email) in settings.student_domains


def is_staff_email(email: str) -> bool:
    return get_domain(email) in settings.staff_domains


def validate_email_domain(email: str) -> None:
    domain = get_domain(email)
    if domain not in settings.all_allowed_domains:
        raise ValueError(f"Email domen '{domain}' nije dozvoljen.")


# ── Redis slot locking (from CLAUDE.md §6) ─────────────────────────────────────

_LOCK_SCRIPT = """
if redis.call("exists", KEYS[1]) == 0 then
    redis.call("setex", KEYS[1], ARGV[1], ARGV[2])
    return 1
end
return 0
"""


async def acquire_slot_lock(
    redis: aioredis.Redis,
    slot_id: str,
    user_id: str,
    ttl: int = 30,
) -> bool:
    """
    Atomically acquire a pessimistic lock on a slot via Lua script.
    Returns True if lock acquired, False if slot is already locked.
    Callers that receive False should return HTTP 409 Conflict.
    """
    result = await redis.eval(_LOCK_SCRIPT, 1, f"slot:lock:{slot_id}", ttl, user_id)
    return result == 1


async def release_slot_lock(redis: aioredis.Redis, slot_id: str) -> None:
    await redis.delete(f"slot:lock:{slot_id}")
