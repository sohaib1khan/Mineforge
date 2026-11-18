"""World library and switch endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.api.deps import (
    AdminCsrfDep,
    AuthDep,
    CsrfAuthDep,
    SessionDep,
    SettingsDep,
    get_client_ip,
)
from app.core.errors import AppError, ForbiddenError
from app.models.user import UserRole
from app.schemas.operations import MessageResponse, OperationResponse
from app.schemas.worlds import (
    SwitchConsentResponse,
    SwitchRequest,
    SwitchStartResponse,
    SwitchStatusResponse,
    WorldCloneRequest,
    WorldCreateRequest,
    WorldImportResponse,
    WorldListResponse,
    WorldRenameRequest,
    WorldResetResponse,
    WorldResponse,
)
from app.services import switch as switch_service
from app.services import worlds as worlds_service

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


def _world(settings, world) -> WorldResponse:
    return WorldResponse.model_validate(worlds_service.world_to_dict(settings, world))


@router.get("", response_model=WorldListResponse)
def list_worlds(
    session: SessionDep, settings: SettingsDep, _auth: AuthDep
) -> WorldListResponse:
    """List worlds (syncs from disk)."""

    items = worlds_service.sync_from_disk(session, settings)
    return WorldListResponse(worlds=[_world(settings, w) for w in items])


@router.get("/switch-status", response_model=SwitchStatusResponse)
def switch_status(
    session: SessionDep, settings: SettingsDep, _auth: AuthDep
) -> SwitchStatusResponse:
    return SwitchStatusResponse.model_validate(
        switch_service.switch_status(session, settings)
    )


@router.get("/{world_id}", response_model=WorldResponse)
def get_world(
    world_id: int, session: SessionDep, settings: SettingsDep, _auth: AuthDep
) -> WorldResponse:
    world = worlds_service.get_world(session, world_id)
    return _world(settings, world)


@router.post("", response_model=WorldResponse)
def create_world(
    body: WorldCreateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> WorldResponse:
    world = worlds_service.create_world(
        session,
        settings,
        display_name=body.display_name,
        folder_name=body.folder_name,
        description=body.description,
        gamemode=body.gamemode,
        difficulty=body.difficulty,
        seed=body.seed,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return _world(settings, world)


@router.post("/import", response_model=WorldImportResponse)
async def import_world(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
    file: UploadFile = File(...),
    display_name: str | None = Form(default=None),
    folder_name: str | None = Form(default=None),
) -> WorldImportResponse:
    """Import a `.mcworld` / `.zip` upload (admin)."""

    suffix = Path(file.filename or "upload.mcworld").suffix.lower() or ".mcworld"
    if suffix not in {".mcworld", ".zip"}:
        raise AppError("Only .mcworld or .zip uploads are supported")
    max_bytes = settings.upload_max_mb * 1024 * 1024
    fd, tmp_name = tempfile.mkstemp(
        prefix="mf-upload-", suffix=suffix, dir=str(settings.app_data_dir)
    )
    tmp_path = Path(tmp_name)
    try:
        import os

        written = 0
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise AppError(f"Upload exceeds {settings.upload_max_mb} MB limit")
                out.write(chunk)
        world, warnings = worlds_service.import_mcworld(
            session,
            settings,
            upload_path=tmp_path,
            display_name=display_name,
            folder_name=folder_name,
            user_id=auth.user.id,  # type: ignore[arg-type]
            role=auth.user.role,
            ip=get_client_ip(request),
        )
        return WorldImportResponse(world=_world(settings, world), warnings=warnings)
    finally:
        tmp_path.unlink(missing_ok=True)
        await file.close()


@router.patch("/{world_id}", response_model=WorldResponse)
def rename_world(
    world_id: int,
    body: WorldRenameRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> WorldResponse:
    world = worlds_service.rename_world(
        session,
        settings,
        world_id=world_id,
        display_name=body.display_name,
        folder_name=body.folder_name,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return _world(settings, world)


@router.post("/{world_id}/reset", response_model=WorldResetResponse)
def reset_world(
    world_id: int,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> WorldResetResponse:
    """Wipe world files after a safety backup; keeps the world entry (admin)."""

    operation = worlds_service.reset_world(
        session,
        settings,
        world_id=world_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return WorldResetResponse(operation=OperationResponse.model_validate(operation))


@router.post("/{world_id}/clone", response_model=WorldResponse)
def clone_world(
    world_id: int,
    body: WorldCloneRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> WorldResponse:
    world = worlds_service.clone_world(
        session,
        settings,
        world_id=world_id,
        new_folder_name=body.folder_name,
        display_name=body.display_name,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return _world(settings, world)


@router.delete("/{world_id}", response_model=MessageResponse)
def delete_world(
    world_id: int,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> MessageResponse:
    worlds_service.delete_world(
        session,
        settings,
        world_id=world_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return MessageResponse(detail="Deleted")


@router.get("/{world_id}/export")
def export_world(
    world_id: int,
    session: SessionDep,
    settings: SettingsDep,
    auth: AuthDep,
) -> FileResponse:
    if auth.user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    world = worlds_service.get_world(session, world_id)
    path = worlds_service.export_world(settings, world)

    def _cleanup() -> None:
        path.unlink(missing_ok=True)

    return FileResponse(
        path,
        filename=f"{world.folder_name}.mcworld",
        media_type="application/zip",
        background=BackgroundTask(_cleanup),
    )


@router.post("/{world_id}/switch", response_model=SwitchStartResponse)
def switch_world(
    world_id: int,
    body: SwitchRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: CsrfAuthDep,
) -> SwitchStartResponse:
    """Start a safe world switch (players with rules; admin may force)."""

    operation = switch_service.start_switch(
        session,
        settings,
        target_world_id=world_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
        force=body.force,
        skip_countdown=body.skip_countdown,
        consent_id=body.consent_id,
    )
    return SwitchStartResponse(operation=OperationResponse.model_validate(operation))


@router.post("/{world_id}/switch-request", response_model=SwitchConsentResponse)
def create_switch_request(
    world_id: int,
    session: SessionDep,
    settings: SettingsDep,
    auth: CsrfAuthDep,
) -> SwitchConsentResponse:
    world = worlds_service.get_world(session, world_id)
    payload = switch_service.create_consent_request(
        session,
        target_world_id=world_id,
        target_folder=world.folder_name,
        user_id=auth.user.id,  # type: ignore[arg-type]
    )
    return SwitchConsentResponse.model_validate(payload)


@router.post(
    "/switch-requests/{request_id}/approve", response_model=SwitchConsentResponse
)
def approve_switch_request(request_id: str, auth: CsrfAuthDep) -> SwitchConsentResponse:
    payload = switch_service.approve_consent(request_id, auth.user.id)  # type: ignore[arg-type]
    return SwitchConsentResponse.model_validate(payload)
