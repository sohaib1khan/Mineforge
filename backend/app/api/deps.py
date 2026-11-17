"""FastAPI dependencies for auth, roles, and CSRF."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import constant_time_equals
from app.db.session import get_session
from app.models.session import AuthSession
from app.models.user import User, UserRole
from app.services.sessions import require_session

SESSION_COOKIE = "mf_session"
CSRF_HEADER = "X-CSRF-Token"


@dataclass
class AuthContext:
    user: User
    auth_session: AuthSession
    raw_token: str


def get_client_ip(request: Request, settings: Settings | None = None) -> str | None:
    """Best-effort client IP for audit, lockout, and rate limiting.

    When ``trust_proxy_headers`` is enabled, prefer ``X-Forwarded-For``
    (leftmost / original client) or ``X-Real-IP``. Only enable behind a
    reverse proxy that overwrites these headers.
    """

    cfg = settings or get_settings()
    if cfg.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()
    if request.client:
        return request.client.host
    return None


def get_optional_auth(
    session: Annotated[Session, Depends(get_session)],
    mf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuthContext | None:
    """Return the current auth context when a valid session cookie exists."""

    if not mf_session:
        return None
    try:
        auth_session, user = require_session(session, mf_session)
    except UnauthorizedError:
        return None
    return AuthContext(user=user, auth_session=auth_session, raw_token=mf_session)


def get_current_auth(
    auth: Annotated[AuthContext | None, Depends(get_optional_auth)],
) -> AuthContext:
    """Require a logged-in user."""

    if auth is None:
        raise UnauthorizedError()
    return auth


def require_csrf(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    x_csrf_token: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
) -> AuthContext:
    """Require a matching CSRF token on state-changing requests."""

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return auth
    if not x_csrf_token or not constant_time_equals(
        x_csrf_token, auth.auth_session.csrf_token
    ):
        raise ForbiddenError("CSRF token missing or invalid")
    return auth


def require_admin(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> AuthContext:
    """Require an admin role."""

    if auth.user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    return auth


def require_admin_csrf(
    auth: Annotated[AuthContext, Depends(require_csrf)],
) -> AuthContext:
    """Require admin + CSRF for mutations."""

    if auth.user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    return auth


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
OptionalAuthDep = Annotated[AuthContext | None, Depends(get_optional_auth)]
AuthDep = Annotated[AuthContext, Depends(get_current_auth)]
CsrfAuthDep = Annotated[AuthContext, Depends(require_csrf)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]
AdminCsrfDep = Annotated[AuthContext, Depends(require_admin_csrf)]
