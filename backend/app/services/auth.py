"""Login, logout, and password-change flows."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models.session import AuthSession
from app.models.user import User
from app.services import lockout
from app.services.audit import record_audit
from app.services.sessions import create_session, destroy_session, get_session_by_token


def authenticate(
    session: Session,
    settings: Settings,
    *,
    username: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, AuthSession, str]:
    """Validate credentials and open a session.

    Returns:
        (user, auth_session, raw_session_token)

    Raises:
        UnauthorizedError: on bad credentials (generic message).
        ForbiddenError: when locked out or inactive.
    """

    lockout.assert_not_locked(username, ip, settings)
    user = session.exec(select(User).where(User.username == username.strip())).first()
    if user is None or not verify_password(user.password_hash, password):
        lockout.record_failure(username, ip, settings)
        raise UnauthorizedError("Invalid username or password")
    if not user.is_active:
        raise ForbiddenError("Account is deactivated")

    lockout.clear_failures(username, ip)
    user.last_login_at = datetime.now(UTC)
    session.add(user)
    auth_session, raw_token = create_session(
        session, settings, user, ip=ip, user_agent=user_agent
    )
    record_audit(
        session,
        action="auth.login",
        user_id=user.id,
        target=f"user:{user.username}",
        ip=ip,
    )
    session.commit()
    session.refresh(user)
    session.refresh(auth_session)
    return user, auth_session, raw_token


def logout(
    session: Session,
    *,
    raw_token: str | None,
    user_id: int | None = None,
    ip: str | None = None,
) -> None:
    """Invalidate the current session cookie."""

    destroy_session(session, raw_token)
    if user_id is not None:
        record_audit(
            session,
            action="auth.logout",
            user_id=user_id,
            ip=ip,
        )
    session.commit()


def change_own_password(
    session: Session,
    user: User,
    *,
    current_password: str,
    new_password: str,
    raw_token: str | None,
    ip: str | None = None,
) -> None:
    """Change the current user's password after verifying the current one.

    Raises:
        ForbiddenError: if the current password is wrong.
    """

    if not verify_password(user.password_hash, current_password):
        raise ForbiddenError("Current password is incorrect")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    session.add(user)

    current = get_session_by_token(session, raw_token) if raw_token else None
    others = session.exec(
        select(AuthSession).where(AuthSession.user_id == user.id)
    ).all()
    for row in others:
        if current is None or row.id != current.id:
            session.delete(row)

    record_audit(
        session,
        action="auth.password_change",
        user_id=user.id,
        target=f"user:{user.username}",
        ip=ip,
    )
    session.commit()
