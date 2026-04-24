"""
auth.py — Authentication endpoints (V1 JWT)

POST  /register          — self-registration (students only)
POST  /login             — returns access token + sets httpOnly refresh cookie
POST  /refresh           — exchanges refresh cookie for a new access token
POST  /logout            — revokes refresh token, clears cookie
POST  /forgot-password   — sends password-reset email
POST  /reset-password    — validates token, sets new password
GET   /me                — returns the current authenticated user
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.core.config import settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter()

# Cookie name used for the refresh token
_REFRESH_COOKIE = "refresh_token"

# Shared cookie kwargs — production vs. development
#
# Path MUST be "/" (not "/api/v1/auth"): the Next.js middleware reads this
# cookie on every protected navigation (e.g. /dashboard, /admin) to decide
# whether the user has an active session. A narrower path would make the
# browser withhold the cookie on those navigations, so middleware would
# redirect authenticated users back to /login (infinite loop after login).
# The cookie stays HttpOnly + SameSite=Lax, so it is still safe.
def _refresh_cookie_params(max_age: int) -> dict:
    return dict(
        key=_REFRESH_COOKIE,
        max_age=max_age,
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
        path="/",
    )


# ── POST /register ─────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registracija studenta",
    description=(
        "Kreiranje novog STUDENT naloga. Dozvoljeni su samo email domeni sa "
        "whitelist-e (`@student.fon.bg.ac.rs`, `@student.etf.bg.ac.rs`). "
        "Osoblje (PROFESOR / ASISTENT / ADMIN) kreira administrator."
    ),
)
async def register(
    data: RegisterRequest,
    db: DBSession,
    response: Response,
) -> UserResponse:
    user = await auth_service.register(db, data)
    return UserResponse.model_validate(user)


# ── POST /login ────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Prijava korisnika",
    description=(
        "Email + password login. Vraća `access_token` u response body-ju "
        "(čuvati u Zustand store-u, NE u localStorage) i postavlja "
        "`refresh_token` kao httpOnly cookie."
    ),
)
async def login(
    data: LoginRequest,
    db: DBSession,
    redis: RedisClient,
    response: Response,
) -> TokenResponse:
    user, access_token, refresh_token = await auth_service.login(
        db, redis, data.email, data.password
    )

    response.set_cookie(
        value=refresh_token,
        **_refresh_cookie_params(max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600),
    )

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


# ── POST /refresh ──────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Obnovi access token",
    description=(
        "Čita `refresh_token` httpOnly cookie, validira ga u Redis-u i "
        "vraća novi `access_token`."
    ),
)
async def refresh(
    db: DBSession,
    redis: RedisClient,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token nije pronađen.",
        )

    user, new_access = await auth_service.refresh_access_token(db, redis, refresh_token)

    # Slide the cookie expiry on each successful refresh
    response.set_cookie(
        value=refresh_token,
        **_refresh_cookie_params(max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600),
    )

    return TokenResponse(
        access_token=new_access,
        user=UserResponse.model_validate(user),
    )


# ── POST /logout ───────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Odjava korisnika",
    description="Briše refresh token iz Redis-a i čisti cookie.",
)
async def logout(
    current_user: CurrentUser,
    redis: RedisClient,
    response: Response,
) -> MessageResponse:
    await auth_service.logout(redis, str(current_user.id))

    # Clear the refresh cookie (path must match the one used when setting it)
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        path="/",
        httponly=True,
        secure=settings.APP_ENV != "development",
        samesite="lax",
    )

    return MessageResponse(message="Uspešno ste se odjavili.")


# ── POST /forgot-password ──────────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Zahtev za resetovanje lozinke",
    description=(
        "Šalje email sa linkom za resetovanje. Uvek vraća 200 OK da se "
        "spreči enumeracija korisnika."
    ),
)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: DBSession,
) -> MessageResponse:
    await auth_service.forgot_password(db, data.email)
    return MessageResponse(
        message="Ako email adresa postoji u sistemu, poslaćemo Vam link za resetovanje."
    )


# ── POST /reset-password ───────────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Resetovanje lozinke",
    description="Validira token i postavlja novu lozinku. Token važi 1 sat.",
)
async def reset_password(
    data: ResetPasswordRequest,
    db: DBSession,
) -> MessageResponse:
    await auth_service.reset_password(db, data.token, data.new_password)
    return MessageResponse(message="Lozinka je uspešno resetovana. Možete se prijaviti.")


# ── GET /me ────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Trenutno prijavljeni korisnik",
    description="Vraća podatke trenutno autentifikovanog korisnika.",
)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
