"""Panel login activity aggregations."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.user import User, UserRole
from app.services import login_activity as login_service
from app.services.audit import record_audit
from sqlmodel import Session


def test_login_activity_snapshot(db_session: Session) -> None:
    admin = User(
        username="admin_one",
        password_hash="x",
        role=UserRole.ADMIN,
        is_active=True,
        last_login_at=datetime.now(UTC),
    )
    player = User(
        username="player_one",
        password_hash="x",
        role=UserRole.PLAYER,
        is_active=True,
        last_login_at=None,
    )
    db_session.add(admin)
    db_session.add(player)
    db_session.commit()
    db_session.refresh(admin)

    record_audit(
        db_session,
        action="auth.login",
        user_id=admin.id,
        target="user:admin_one",
        ip="203.0.113.10",
    )
    db_session.commit()

    snap = login_service.login_activity_snapshot(db_session, days=7, recent_limit=5)
    assert snap["login_count_window"] >= 1
    assert snap["users_total"] == 2
    assert snap["users_never_logged_in"] == 1
    assert snap["recent"][0]["username"] == "admin_one"
    assert snap["recent"][0]["ip"] == "203.0.113.10"
    assert any(u["username"] == "player_one" for u in snap["users"])
