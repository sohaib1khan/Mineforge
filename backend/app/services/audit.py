"""Audit log writes and queries."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.audit import AuditLog


def record_audit(
    session: Session,
    *,
    action: str,
    user_id: int | None = None,
    target: str | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Persist an audit log row.

    Does not commit — the caller owns the transaction.
    """

    entry = AuditLog(
        user_id=user_id,
        action=action,
        target=target,
        details=details,
        ip=ip,
    )
    session.add(entry)
    session.flush()
    return entry


def list_audit_logs(
    session: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    action: str | None = None,
) -> list[AuditLog]:
    """Return recent audit log entries, newest first.

    Raises:
        ValueError: if limit is out of bounds.
    """

    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    statement = select(AuditLog).order_by(AuditLog.ts.desc())
    if action:
        statement = statement.where(AuditLog.action == action)
    statement = statement.offset(offset).limit(limit)
    return list(session.exec(statement).all())
