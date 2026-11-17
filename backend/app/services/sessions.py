"""Server-side session create / validate / destroy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import generate_token, hash_token
from app.models.session import AuthSession
from app.models.user import User


def create_session(
    session: Session,
    settings: Settings,
    user: User,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[AuthSession, str]:
    """Create a server-side session and return (row, raw_token).

    Does not commit — the caller owns the transaction.
    The raw token is only returned once for the cookie; only the hash is stored.
    """

    if user.id is None:
        raise ValueError("user must be persisted before creating a session")

    raw_token = generate_token(32)
    csrf_token = generate_token(24)
    now = datetime.now(UTC)
    row = AuthSession(
        user_id=user.id,
        token_hash=hash_token(raw_token, secret=settings.secret_key),
        csrf_token=csrf_token,
        created_at=now,
        expires_at=now + timedelta(days=settings.session_days),
        ip=ip,
        user_agent=(user_agent or "")[:512] or None,
    )
    session.add(row)
    session.flush()
    return row, raw_token


def get_session_by_token(
    session: Session,
    raw_token: str,
    *,
    secret: str | None = None,
) -> AuthSession | None:
    """Look up a non-expired session by the raw cookie token."""

    if not raw_token:
        return None
    if secret is None:
        from app.core.config import get_settings

        secret = get_settings().secret_key
    token_hash = hash_token(raw_token, secret=secret)
    row = session.exec(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    ).first()
    if row is None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        session.delete(row)
        session.commit()
        return None
    return row


def require_session(
    session: Session, raw_token: str | None
) -> tuple[AuthSession, User]:
    """Resolve cookie token to an active user session.

    Raises:
        UnauthorizedError: if the session is missing, expired, or user inactive.
    """

    if not raw_token:
        raise UnauthorizedError()
    auth_session = get_session_by_token(session, raw_token)
    if auth_session is None:
        raise UnauthorizedError()
    user = session.get(User, auth_session.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError()
    return auth_session, user


def destroy_session(session: Session, raw_token: str | None) -> None:
    """Invalidate a session by raw cookie token (logout). Does not commit."""

    if not raw_token:
        return
    from app.core.config import get_settings

    token_hash = hash_token(raw_token, secret=get_settings().secret_key)
    auth_session = session.exec(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    ).first()
    if auth_session is not None:
        session.delete(auth_session)
        session.flush()


def destroy_user_sessions(session: Session, user_id: int) -> None:
    """Invalidate all sessions for a user. Does not commit."""

    rows = session.exec(select(AuthSession).where(AuthSession.user_id == user_id)).all()
    for row in rows:
        session.delete(row)
    session.flush()
