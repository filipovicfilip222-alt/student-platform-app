"""WebSocket-specific authentication helper.

REST endpoints rely on FastAPI's ``Depends(get_current_user)`` which raises
``HTTPException(401)`` on bad input — fine for HTTP, but useless on a
WebSocket where we need to call ``websocket.close(code=4401)`` with the
custom code from ``docs/websocket-schema.md §2.3``. So we cannot reuse the
HTTP dependency directly; we expose a low-level helper that returns the
authenticated ``User`` or ``None`` and lets the caller own the close-code
decision.

This module is shared between Faza 4.1 (chat WS) and Faza 4.2 (notifications
stream).

Token transport reminder (schema §2.1):
    Browsers forbid custom Authorization headers on ``new WebSocket(...)``,
    so the access JWT is passed as a ``?token=...`` query param. The token
    contents and lifetime are identical to the REST access token.

Impersonation (schema §6.4):
    The WS handler ALWAYS binds to ``sub``. The ``imp`` claim, if present,
    is ignored at this layer — admin impersonation only swaps the access
    token in the browser, the WS subscriber is still scoped to the target
    user. We do not strip ``imp`` (the User object is the same regardless
    of impersonation; downstream RBAC reads ``user.role``).
"""

from __future__ import annotations

from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.models.user import User


async def decode_ws_token(token: str, db: AsyncSession) -> User | None:
    """Validate a WebSocket query-param JWT.

    Returns the active ``User`` ORM object on success, ``None`` on any
    failure (invalid signature, wrong type, ``sub`` missing, user not
    found, user deactivated). Callers MUST close the socket with code
    4401 when this returns ``None``.

    Implementation notes:
        - We do NOT raise — exceptions on a WebSocket would skip our
          carefully chosen close code and produce 1011 instead.
        - We do NOT log: token validation failures are routine (expired
          tokens during reconnect storms) and would flood the log.
    """
    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except JWTError:
        return None

    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None

    try:
        user_id = UUID(sub)
    except (TypeError, ValueError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user
