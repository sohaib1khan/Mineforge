"""Backup list, create, restore, delete, download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api.deps import (
    AdminCsrfDep,
    AuthDep,
    CsrfAuthDep,
    SessionDep,
    SettingsDep,
    get_client_ip,
)
from app.core.errors import ForbiddenError, NotFoundError
from app.schemas.backups import (
    BackupCreateResponse,
    BackupListResponse,
    BackupResponse,
    RestoreResponse,
)
from app.schemas.operations import MessageResponse, OperationResponse
from app.services import backups as backup_service

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.get("", response_model=BackupListResponse)
def list_backups(
    session: SessionDep,
    settings: SettingsDep,
    _auth: AuthDep,
    world_id: int | None = None,
) -> BackupListResponse:
    """List backups (any authenticated user)."""

    items = backup_service.list_backups(session, world_id=world_id)
    return BackupListResponse(
        backups=[
            BackupResponse.model_validate(backup_service.backup_to_dict(b))
            for b in items
        ],
        storage=backup_service.disk_usage_summary(settings),
    )


@router.post("", response_model=BackupCreateResponse)
def create_backup(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: CsrfAuthDep,
) -> BackupCreateResponse:
    """Start a manual backup of the active world."""

    operation = backup_service.start_manual_backup(
        session,
        settings,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return BackupCreateResponse(operation=OperationResponse.model_validate(operation))


@router.post("/{backup_id}/restore", response_model=RestoreResponse)
def restore_backup(
    backup_id: int,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> RestoreResponse:
    """Restore a backup (admin). Runs as a background operation with rollback."""

    operation = backup_service.start_restore(
        session,
        settings,
        backup_id=backup_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return RestoreResponse(operation=OperationResponse.model_validate(operation))


@router.delete("/{backup_id}", response_model=MessageResponse)
def delete_backup(
    backup_id: int,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> MessageResponse:
    backup_service.delete_backup(
        session,
        settings,
        backup_id=backup_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return MessageResponse(detail="Deleted")


@router.get("/{backup_id}/download")
def download_backup(
    backup_id: int,
    session: SessionDep,
    settings: SettingsDep,
    auth: AuthDep,
) -> FileResponse:
    """Download a backup archive (admin only)."""

    if auth.user.role.value != "admin":
        raise ForbiddenError("Admin access required")
    backup = backup_service.get_backup(session, backup_id)
    path = Path(backup.path)
    root = backup_service.backups_dir(settings).resolve()
    try:
        resolved = path.resolve()
    except FileNotFoundError as exc:
        raise NotFoundError("Backup file missing") from exc
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise NotFoundError("Backup file missing")
    return FileResponse(
        resolved,
        filename=resolved.name,
        media_type="application/zstd",
    )


@router.get("/{backup_id}", response_model=BackupResponse)
def get_backup(backup_id: int, session: SessionDep, _auth: AuthDep) -> BackupResponse:
    backup = backup_service.get_backup(session, backup_id)
    return BackupResponse.model_validate(backup_service.backup_to_dict(backup))
