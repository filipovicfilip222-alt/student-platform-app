from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

# ── Redis dependency ───────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


# ── Auth dependencies ──────────────────────────────────────────────────────────

async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """
    Extracts and validates the Bearer JWT from the Authorization header.
    Returns the authenticated User ORM object.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nije moguće potvrditi identitet korisnika",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Korisnički nalog je deaktiviran",
        )

    return user


def require_role(*roles: UserRole):
    """
    Dependency factory that enforces RBAC.

    Usage:
        @router.get("/", dependencies=[Depends(require_role(UserRole.ADMIN))])

    Or as a parameter:
        current_user: User = Depends(require_role(UserRole.PROFESOR, UserRole.ASISTENT))
    """
    async def _check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Pristup odbijen. Potrebna uloga: {', '.join(r.value for r in roles)}",
            )
        return current_user

    return _check_role


# ── Typed shortcuts ────────────────────────────────────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
CurrentProfesor = Annotated[User, Depends(require_role(UserRole.PROFESOR))]
CurrentProfesorOrAsistent = Annotated[
    User, Depends(require_role(UserRole.PROFESOR, UserRole.ASISTENT))
]
CurrentStudent = Annotated[User, Depends(require_role(UserRole.STUDENT))]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
