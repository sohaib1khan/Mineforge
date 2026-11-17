"""Unit tests for users, sessions, and audit helpers."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.security import verify_password
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.services import audit as audit_service
from app.services import sessions as session_service
from app.services import users as user_service
from sqlmodel import Session, select


def test_user_crud_and_sessions(admin_user: User, db_session: Session) -> None:
    settings = get_settings()
    created = user_service.create_user(
        db_session,
        username="player_two",
        password="player-password-99",
        role=UserRole.PLAYER,
        actor=admin_user,
    )
    assert created.id is not None
    assert created.role == UserRole.PLAYER
    assert verify_password(created.password_hash, "player-password-99")

    listed = user_service.list_users(db_session)
    names = {u.username for u in listed}
    assert "admin_one" in names and "player_two" in names

    auth_row, raw = session_service.create_session(
        db_session, settings, created, ip="127.0.0.1", user_agent="test"
    )
    db_session.commit()
    assert auth_row.token_hash
    found = session_service.get_session_by_token(db_session, raw)
    assert found is not None
    assert found.id == auth_row.id

    session_service.destroy_session(db_session, raw)
    db_session.commit()
    assert session_service.get_session_by_token(db_session, raw) is None

    _, raw2 = session_service.create_session(db_session, settings, created)
    db_session.commit()
    session_service.destroy_user_sessions(db_session, created.id)  # type: ignore[arg-type]
    db_session.commit()
    assert session_service.get_session_by_token(db_session, raw2) is None

    updated = user_service.update_user(
        db_session,
        created.id,  # type: ignore[arg-type]
        actor=admin_user,
        is_active=False,
    )
    assert updated.is_active is False

    reset = user_service.reset_password(
        db_session,
        created.id,  # type: ignore[arg-type]
        new_password="reset-password-12",
        actor=admin_user,
    )
    assert verify_password(reset.password_hash, "reset-password-12")
    assert reset.must_change_password is True

    user_service.delete_user(
        db_session,
        created.id,  # type: ignore[arg-type]
        actor=admin_user,
    )
    assert db_session.get(User, created.id) is None


def test_audit_record_and_list(admin_user: User, db_session: Session) -> None:
    audit_service.record_audit(
        db_session,
        action="test.action",
        user_id=admin_user.id,
        target="player_one",
        details={"ok": True},
        ip="203.0.113.10",
    )
    db_session.commit()
    rows = audit_service.list_audit_logs(db_session, action="test.action")
    assert len(rows) == 1
    assert rows[0].target == "player_one"
    assert db_session.exec(
        select(AuditLog).where(AuditLog.action == "test.action")
    ).first()
