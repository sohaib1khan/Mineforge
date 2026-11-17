"""First-run admin setup when no admin account exists yet."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.errors import ConflictError
from app.core.security import hash_password
from app.models.setting import Setting
from app.models.user import User, UserRole
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

SETUP_CODE_HASH_KEY = "setup_code_hash"
SETUP_CODE_FILENAME = "setup_code"


def admin_count(session: Session) -> int:
    """Return the number of admin users."""

    return len(
        list(session.exec(select(User.id).where(User.role == UserRole.ADMIN)).all())
    )


def needs_setup(session: Session) -> bool:
    """True when no admin user exists yet (fresh install / first-run)."""

    return admin_count(session) == 0


def _setup_code_path(settings: Settings) -> Path:
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    return settings.app_data_dir / SETUP_CODE_FILENAME


def _delete_setting(session: Session, key: str) -> None:
    row = session.get(Setting, key)
    if row is not None:
        session.delete(row)


def ensure_setup_code(session: Session, settings: Settings) -> None:
    """Log first-run guidance when setup is still required.

    Setup no longer requires a code from logs — opening the UI is enough —
    but we still log a clear reminder for operators.
    """

    if not needs_setup(session):
        return
    logger.warning(
        "MineForge first-run setup required: open the UI and create the admin account."
    )
    # Clear any leftover Phase-1 setup-code artifacts.
    code_path = _setup_code_path(settings)
    if code_path.exists():
        code_path.unlink(missing_ok=True)
    _delete_setting(session, SETUP_CODE_HASH_KEY)
    session.commit()


def complete_setup(
    session: Session,
    settings: Settings,
    *,
    username: str,
    password: str,
    ip: str | None = None,
    setup_code: str | None = None,
) -> User:
    """Create the first admin user when none exists.

    Raises:
        ConflictError: if an admin already exists.
    """

    _ = setup_code  # accepted for backward-compatible clients; ignored
    if not needs_setup(session):
        raise ConflictError("Setup has already been completed")

    existing = session.exec(
        select(User).where(User.username == username.strip())
    ).first()
    if existing is not None:
        raise ConflictError("Username already exists")

    admin = User(
        username=username.strip(),
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
        must_change_password=False,
    )
    session.add(admin)
    session.flush()

    code_path = _setup_code_path(settings)
    if code_path.exists():
        code_path.unlink(missing_ok=True)
    _delete_setting(session, SETUP_CODE_HASH_KEY)

    record_audit(
        session,
        action="setup.complete",
        user_id=admin.id,
        target=f"user:{admin.username}",
        ip=ip,
    )
    session.commit()
    session.refresh(admin)
    logger.info("First-run admin created: %s", admin.username)
    return admin
