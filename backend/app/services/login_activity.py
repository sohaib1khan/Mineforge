"""Panel user login activity derived from audit logs and user rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, col, select

from app.models.audit import AuditLog
from app.models.user import User


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def recent_logins(
    session: Session,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Recent successful panel logins from the audit log."""

    limit = max(1, min(limit, 100))
    rows = session.exec(
        select(AuditLog)
        .where(AuditLog.action == "auth.login")
        .order_by(col(AuditLog.ts).desc())
        .limit(limit)
    ).all()
    users = {
        u.id: u.username for u in session.exec(select(User)).all() if u.id is not None
    }
    out: list[dict[str, Any]] = []
    for row in rows:
        username = users.get(row.user_id) if row.user_id else None
        if not username and row.target and row.target.startswith("user:"):
            username = row.target.split(":", 1)[1]
        out.append(
            {
                "ts": _ensure_aware(row.ts).isoformat(),
                "user_id": row.user_id,
                "username": username or "unknown",
                "ip": row.ip,
            }
        )
    return out


def logins_over_time(
    session: Session,
    *,
    days: int = 14,
) -> list[dict[str, Any]]:
    """Count panel logins per UTC day."""

    days = max(1, min(days, 90))
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = session.exec(
        select(AuditLog).where(
            AuditLog.action == "auth.login",
            col(AuditLog.ts) >= cutoff,
        )
    ).all()
    buckets: dict[str, int] = {}
    for row in rows:
        day = _ensure_aware(row.ts).date().isoformat()
        buckets[day] = buckets.get(day, 0) + 1
    out: list[dict[str, Any]] = []
    for offset in range(days, -1, -1):
        day = (datetime.now(UTC) - timedelta(days=offset)).date().isoformat()
        out.append({"day": day, "logins": buckets.get(day, 0)})
    return out


def user_login_roster(session: Session) -> list[dict[str, Any]]:
    """All panel users with last login timestamps (no secrets)."""

    rows = session.exec(select(User).order_by(col(User.username).asc())).all()
    out: list[dict[str, Any]] = []
    for user in rows:
        out.append(
            {
                "id": user.id,
                "username": user.username,
                "role": (
                    user.role.value if hasattr(user.role, "value") else str(user.role)
                ),
                "is_active": bool(user.is_active),
                "last_login_at": (
                    _ensure_aware(user.last_login_at).isoformat()
                    if user.last_login_at
                    else None
                ),
                "created_at": (
                    _ensure_aware(user.created_at).isoformat()
                    if user.created_at
                    else None
                ),
            }
        )
    return out


def login_activity_snapshot(
    session: Session,
    *,
    days: int = 14,
    recent_limit: int = 15,
) -> dict[str, Any]:
    """Bundle login activity for dashboard / metrics."""

    recent = recent_logins(session, limit=recent_limit)
    series = logins_over_time(session, days=days)
    roster = user_login_roster(session)
    return {
        "recent": recent,
        "logins_by_day": series,
        "users": roster,
        "login_count_window": sum(item["logins"] for item in series),
        "users_total": len(roster),
        "users_active": sum(1 for u in roster if u["is_active"]),
        "users_never_logged_in": sum(1 for u in roster if not u["last_login_at"]),
    }
