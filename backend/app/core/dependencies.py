from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Cookie, Depends, HTTPException, Request, status
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
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """
    Extracts and validates the Bearer JWT from the Authorization header.
    Returns the authenticated User ORM object.

    **Impersonation handling (Faza 4.4 / docs/websocket-schema.md §6):**
    Ako payload nosi ``imp: true`` claim, ``user`` je TARGET (po ``sub``-u),
    NE admin. Originalni admin se nosi na payload ``imp_email`` claim-u i
    prilepljuje se na request.state za audit/logging svrhe:

    - ``request.state.is_impersonation: bool``
    - ``request.state.original_admin_email: str | None``
    - ``request.state.original_admin_name: str | None``

    Dodatno se sirovi claim-ovi prilepe i na sam User objekat kao
    ``user._impersonated_by_*`` atributi (in-memory, ne-persisted) tako da
    servisi koji već primaju ``current_user: User`` mogu da pročitaju
    impersonation kontekst bez novog dependency hop-a.
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

    # ── Impersonation context propagation ──────────────────────────────────────
    is_imp = bool(payload.get("imp"))
    imp_email = payload.get("imp_email") if is_imp else None
    imp_name = payload.get("imp_name") if is_imp else None

    request.state.is_impersonation = is_imp
    request.state.original_admin_email = imp_email
    request.state.original_admin_name = imp_name

    # In-memory marker — bezbedno za servisni sloj (ne dira ORM tabelu).
    user._is_impersonated = is_imp  # type: ignore[attr-defined]
    user._impersonated_by_email = imp_email  # type: ignore[attr-defined]
    user._impersonated_by_name = imp_name  # type: ignore[attr-defined]

    return user


async def get_current_admin_actor(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Resolve the **actual admin** behind a request, even during an active
    impersonation session.

    Behavior:

    - Token NIJE imp + role=ADMIN → vraća ``current_user`` direktno.
    - Token JE imp (current_user je target) → resolve-uje originalnog admina
      preko ``imp_email`` claim-a (postavljenog u
      :func:`get_current_user`); 401 ako je admin u međuvremenu obrisan ili
      deaktiviran.
    - Sve ostalo → 403.

    Postoji kao **odvojena** dependency od :func:`require_role` da se ne
    razvodnjava postojeći ``CurrentAdmin`` na ~30 admin ruta — samo
    impersonation endpoint-i (start/end/audit-log) traže ovu logiku.
    """
    # Common path — admin sa regularnim tokenom.
    is_imp = getattr(current_user, "_is_impersonated", False)
    if not is_imp:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pristup odbijen. Potrebna uloga: ADMIN",
            )
        return current_user

    # Impersonation path — resolve original admin from the imp_email claim.
    imp_email: str | None = getattr(current_user, "_impersonated_by_email", None)
    if not imp_email:
        # imp=true ali bez imp_email — token je iskvaren / pre-Faza-4.4.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Impersonation token bez imp_email claim-a",
        )

    result = await db.execute(select(User).where(User.email == imp_email))
    admin: User | None = result.scalar_one_or_none()

    if admin is None or not admin.is_active or admin.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Originalni admin više nije validan",
        )

    return admin


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


def require_subject_assistant(subject_id_param: str = "subject_id"):
    """RBAC factory: assert da je current_user dodeljen subject-u kao asistent.

    KORAK 3 Prompta 2 / PRD §1.3 / CLAUDE.md §5. Profesor i admin
    bezuslovno prolaze; asistent prolazi samo ako postoji red u
    ``subject_assistants`` M2M tabeli sa ``(subject_id_iz_path, current_user.id)``.

    Argumenti:
        subject_id_param: ime path/query parametra koji nosi UUID
            subject-a (default ``"subject_id"``). Dependency factory
            čita ``request.path_params[subject_id_param]`` ili
            ``request.query_params[subject_id_param]`` da zatvori
            generičkim potpisom (FastAPI ne dozvoljava parametrizaciju
            dependency-jeve potpisa runtime-om bez Request injection-a).

    Tipično korišćenje (na nekom budućem subject-scoped endpoint-u):

        @router.get("/subjects/{subject_id}/...")
        async def handler(
            subject_id: UUID,
            user: Annotated[User, Depends(require_subject_assistant())],
        ): ...

    NB: za CRM rute koje primaju ``student_id`` (ne ``subject_id``)
    koristi se :func:`crm_service._assert_assistant_can_access_student`
    koji ide jedan korak dalje — proverava da je student bio na nekom
    appointment-u za jedan od asistentovih predmeta.
    """
    async def _check(
        request: Request,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        if current_user.role in (UserRole.PROFESOR, UserRole.ADMIN):
            return current_user

        if current_user.role != UserRole.ASISTENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pristup odbijen. Potrebna uloga: PROFESOR ili ASISTENT.",
            )

        raw = request.path_params.get(subject_id_param) or request.query_params.get(
            subject_id_param
        )
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nedostaje '{subject_id_param}' parametar za RBAC proveru.",
            )
        try:
            subject_uuid = UUID(str(raw))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nevalidan UUID za '{subject_id_param}'.",
            ) from None

        # Lazy import — circular bi se moglo desiti ako bi neki model fajl
        # importovao dependencies.py (trenutno ne radi, ali defenzivno).
        from app.models.subject import subject_assistants

        result = await db.execute(
            select(subject_assistants.c.subject_id).where(
                subject_assistants.c.subject_id == subject_uuid,
                subject_assistants.c.assistant_id == current_user.id,
            )
        )
        if result.first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Niste asistent dodeljen ovom predmetu. CRM/operacije "
                    "predmeta su dostupne samo profesoru predmeta i njegovim "
                    "asistentima."
                ),
            )
        return current_user

    return _check


# ── Typed shortcuts ────────────────────────────────────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
CurrentAdminActor = Annotated[User, Depends(get_current_admin_actor)]
CurrentProfesor = Annotated[User, Depends(require_role(UserRole.PROFESOR))]
CurrentProfesorOrAsistent = Annotated[
    User, Depends(require_role(UserRole.PROFESOR, UserRole.ASISTENT))
]
CurrentStudent = Annotated[User, Depends(require_role(UserRole.STUDENT))]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
