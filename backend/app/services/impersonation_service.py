"""impersonation_service.py — Admin → Target token swap (Faza 4.4).

Po :doc:`docs/websocket-schema.md §6` + CLAUDE.md §14:

- ``IMPERSONATION_TOKEN_TTL_MINUTES = 30`` (config), no refresh — kad istekne,
  401 i admin re-impersonira.
- Impersonation token nosi claim-ove: ``sub`` = TARGET user id,
  ``role``/``email`` = TARGET-ovi (current_user u svim endpoint-ima je TARGET),
  ``imp = true``, ``imp_email``/``imp_name`` = original admin (audit + UI).
- Audit log obavezan za START/END (CLAUDE.md §15) — IP iz request.client.host
  ili X-Forwarded-For (rute pripreme string, servis ga prosledi).

Re-impersonation flow: admin u imp-u na A klikne "Impersoniraj B" — backend
**implicitno** upiše IMPERSONATION_END(A) i odmah IMPERSONATION_START(B) u
istoj transakciji (jedan rollback briše oboje). Single-session per admin —
nikad 2 paralelne sesije.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.services import audit_log_service


async def _load_user(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Korisnik ne postoji",
        )
    return user


async def start_impersonation(
    db: AsyncSession,
    *,
    admin: User,
    target_user_id: UUID,
    ip_address: str,
) -> tuple[str, datetime, User]:
    """
    Start an impersonation session: ``admin`` glumi ``target_user_id``.

    Vraća ``(access_token, imp_expires_at_utc, target_user_orm)``.

    Validacije (svaka padne kao HTTP 4xx — biznis greška, ne 500):

    - Admin mora imati ``role == ADMIN`` (rute koje pozivaju ovo prolaze
      kroz ``require_role(ADMIN)``, pa je ovo defensiv check).
    - Target mora postojati i biti ``is_active``.
    - Admin NE sme da impersonira sam sebe (besmisleno — i banner bi se
      poludeo na self-heal-u).
    - Admin NE sme da impersonira drugog admina (security gap — nema
      legitimnog use case-a; ako adminu treba debug drugog admina, neka
      mu admin direktno preda kredencijale).

    Re-impersonation: ako je admin već u imp-u (provera kroz
    :func:`audit_log_service.get_active_impersonation_target`), prvo se
    upiše IMPERSONATION_END za prethodnog target-a, pa onda START za novog
    — sve u istoj transakciji.
    """
    if admin.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Samo admin može da impersonira korisnika",
        )

    target = await _load_user(db, target_user_id)

    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin ne može da impersonira sam sebe",
        )
    if not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ciljani korisnički nalog nije aktivan",
        )
    if target.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impersonacija drugog admina nije dozvoljena",
        )

    # ── Re-impersonation path: zatvori prethodnu sesiju u istoj transakciji ──
    previous_target_id = await audit_log_service.get_active_impersonation_target(
        db, admin_id=admin.id
    )
    if previous_target_id is not None and previous_target_id != target.id:
        await audit_log_service.log_action(
            db,
            admin_id=admin.id,
            action=AuditAction.IMPERSONATION_END,
            ip_address=ip_address,
            impersonated_user_id=previous_target_id,
        )
    elif previous_target_id == target.id:
        # Već impersonira ovog target-a — re-issue tokena (admin možda
        # izgubio token na frontend-u po hard reload-u). Bez novog START
        # entry-ja, da log ne pukne na duplikate.
        token, expires_at = _issue_impersonation_token(admin=admin, target=target)
        return token, expires_at, target

    # ── Normalna START putanja ─────────────────────────────────────────────────
    await audit_log_service.log_action(
        db,
        admin_id=admin.id,
        action=AuditAction.IMPERSONATION_START,
        ip_address=ip_address,
        impersonated_user_id=target.id,
    )

    token, expires_at = _issue_impersonation_token(admin=admin, target=target)
    return token, expires_at, target


async def end_impersonation(
    db: AsyncSession,
    *,
    admin: User,
    target_user_id: UUID | None,
    ip_address: str,
) -> tuple[str, User]:
    """
    Close the impersonation session: vraća admina u svoj nalog. Vraća svež
    regularni admin access token (bez ``imp`` claim-a) i admin User za
    response.

    ``target_user_id`` je ID kog je admin impersonirao (čita se sa
    impersonation tokena u ruti — ``current_user.id``). Može biti None ako
    target više ne postoji (audit kolona je SET NULL na delete).

    Idempotentnost: ako nema otvorene sesije (npr. admin pokušava END dva
    puta), upisujemo END svejedno — audit log je istorijski zapis, nije
    state machine. Frontend ne sme to da očekuje, ali backend ne pravi 409
    da bi izbegli toast spam.
    """
    if admin.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Samo admin može da završi impersonation sesiju",
        )

    await audit_log_service.log_action(
        db,
        admin_id=admin.id,
        action=AuditAction.IMPERSONATION_END,
        ip_address=ip_address,
        impersonated_user_id=target_user_id,
    )

    # Regularni access token za admina (default TTL = ACCESS_TOKEN_EXPIRE_MINUTES).
    token = create_access_token(
        {
            "sub": str(admin.id),
            "role": admin.role.value,
            "email": admin.email,
        }
    )
    return token, admin


# ── Internal helpers ──────────────────────────────────────────────────────────


def _issue_impersonation_token(*, admin: User, target: User) -> tuple[str, datetime]:
    """Build the JWT and compute its UTC expiry. Pure compute — no IO."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.IMPERSONATION_TOKEN_TTL_MINUTES
    )
    token = create_access_token(
        {
            "sub": str(target.id),
            "role": target.role.value,
            "email": target.email,
            "imp": True,
            "imp_email": admin.email,
            "imp_name": f"{admin.first_name} {admin.last_name}",
        },
        expires_minutes=settings.IMPERSONATION_TOKEN_TTL_MINUTES,
    )
    return token, expires_at
