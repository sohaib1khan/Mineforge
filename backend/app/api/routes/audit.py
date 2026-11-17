"""Audit log listing (admin)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import AdminDep, SessionDep
from app.schemas.audit import AuditLogListResponse, AuditLogPublic
from app.services import audit as audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
def list_audit(
    session: SessionDep,
    _admin: AdminDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: str | None = None,
) -> AuditLogListResponse:
    """List audit log entries (admin)."""

    items = audit_service.list_audit_logs(
        session, limit=limit, offset=offset, action=action
    )
    return AuditLogListResponse(items=[AuditLogPublic.model_validate(i) for i in items])
