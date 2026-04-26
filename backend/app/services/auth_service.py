"""
auth_service.py — Auth business logic.

All public functions are async and work with an AsyncSession.
Redis is used for refresh-token storage and revocation.
"""

import hashlib
import secrets
from datetime import timedelta, timezone, datetime

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    is_student_email,
    is_staff_email,
    validate_email_domain,
    verify_password,
)
from app.models.enums import Faculty, UserRole
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import RegisterRequest

# Redis TTL matches REFRESH_TOKEN_EXPIRE_DAYS
_REFRESH_TTL = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
# Password-reset tokens valid for 1 hour
_RESET_TOKEN_TTL_SECONDS = 3600


# ── Helpers ────────────────────────────────────────────────────────────────────

def _redis_refresh_key(user_id: str) -> str:
    return f"refresh:{user_id}"


def _faculty_from_email(email: str) -> Faculty:
    """Infer Faculty from a whitelisted email domain."""
    domain = email.split("@")[1].lower()
    if "fon" in domain:
        return Faculty.FON
    if "etf" in domain:
        return Faculty.ETF
    # Fallback: shouldn't be reached after domain validation
    raise ValueError(f"Cannot infer faculty from domain '{domain}'.")


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def _create_reset_token(
    db: AsyncSession,
    user: User,
    ttl_seconds: int,
) -> str:
    """Create a one-time password-reset token for a user.

    Returns the **raw** (unhashed) token. The DB stores only its SHA-256 hash.
    Caller is responsible for emailing the raw token to the user (Celery).

    Reused by:
      * forgot_password()                              — TTL = 1h
      * admin_user_service.create_user()               — TTL = 7d (welcome)
      * admin_user_service.bulk_import_confirm()       — TTL = 7d (welcome)
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    await db.flush()
    return raw_token


# ── Register ───────────────────────────────────────────────────────────────────

async def register(db: AsyncSession, data: RegisterRequest) -> User:
    """
    Create a new STUDENT account.
    Staff accounts (PROFESOR, ASISTENT, ADMIN) are created by admins only.
    """
    email = data.email.lower()

    # 1. Domain validation — only student emails allowed for self-registration
    try:
        validate_email_domain(email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if is_staff_email(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Nalozi za osoblje se ne kreiraju putem registracije. "
                "Obratite se administratoru."
            ),
        )

    # 2. Uniqueness check
    if await _get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Korisnik sa ovom email adresom već postoji.",
        )

    # 3. Create user (role always STUDENT for self-registration)
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=UserRole.STUDENT,
        faculty=_faculty_from_email(email),
    )
    db.add(user)
    await db.flush()  # get the UUID assigned without committing

    return user


# ── Login ──────────────────────────────────────────────────────────────────────

async def login(
    db: AsyncSession,
    redis: aioredis.Redis,
    email: str,
    password: str,
) -> tuple[User, str, str]:
    """
    Authenticate and return (user, access_token, refresh_token).
    The refresh token is also stored in Redis for single-session revocation.
    """
    user = await _get_user_by_email(db, email.lower())

    # Use a constant-time comparison path to avoid user enumeration
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pogrešan email ili lozinka.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Korisnički nalog je deaktiviran. Obratite se administratoru.",
        )

    payload = {"sub": str(user.id), "role": user.role.value, "email": user.email}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    # Store refresh token in Redis (overwrites previous session — single active session)
    await redis.setex(_redis_refresh_key(str(user.id)), _REFRESH_TTL, refresh_token)

    return user, access_token, refresh_token


# ── Refresh ────────────────────────────────────────────────────────────────────

async def refresh_access_token(
    db: AsyncSession,
    redis: aioredis.Redis,
    refresh_token: str,
) -> tuple[User, str]:
    """
    Validate the refresh token against Redis and return a new access token.
    Returns (user, new_access_token).
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token je nevažeći ili je istekao.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(refresh_token)
        user_id: str = payload["sub"]
    except Exception:
        raise credentials_exc

    # Validate against Redis (revocation check)
    stored = await redis.get(_redis_refresh_key(user_id))
    if stored != refresh_token:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc

    new_access = create_access_token(
        {"sub": str(user.id), "role": user.role.value, "email": user.email}
    )
    return user, new_access


# ── Logout ─────────────────────────────────────────────────────────────────────

async def logout(redis: aioredis.Redis, user_id: str) -> None:
    """Revoke the refresh token by deleting it from Redis."""
    await redis.delete(_redis_refresh_key(user_id))


# ── Forgot password ────────────────────────────────────────────────────────────

async def forgot_password(db: AsyncSession, email: str) -> None:
    """
    Create a one-time password-reset token and dispatch an email.

    Always returns silently (no 404) to prevent user enumeration.
    """
    from app.core.email import send_password_reset_email  # avoid circular import

    user = await _get_user_by_email(db, email.lower())
    if not user or not user.is_active:
        return  # silent — don't leak whether the email exists

    raw_token = await _create_reset_token(db, user, ttl_seconds=_RESET_TOKEN_TTL_SECONDS)
    send_password_reset_email(to_email=user.email, reset_token=raw_token)


# ── Reset password ─────────────────────────────────────────────────────────────

async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> None:
    """
    Validate the reset token and update the user's password.
    """
    token_hash = _hash_reset_token(raw_token)

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    prt: PasswordResetToken | None = result.scalar_one_or_none()

    invalid_exc = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Token za resetovanje lozinke je nevažeći ili je istekao.",
    )

    if not prt:
        raise invalid_exc
    if not prt.is_valid:
        raise invalid_exc

    # Mark token as used
    prt.used_at = datetime.now(timezone.utc)

    # Update password
    result2 = await db.execute(select(User).where(User.id == prt.user_id))
    user: User | None = result2.scalar_one_or_none()
    if not user:
        raise invalid_exc

    user.hashed_password = hash_password(new_password)
