"""Add-on library, per-world profiles, apply/test."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile

from app.api.deps import (
    AdminCsrfDep,
    AdminDep,
    AuthDep,
    SessionDep,
    SettingsDep,
    get_client_ip,
)
from app.core.errors import AppError
from app.schemas.addons import (
    AddonApplyRequest,
    AddonApplyResponse,
    AddonListResponse,
    AddonResponse,
    AddonUploadResponse,
    PendingTestsResponse,
    TexturepackRequiredRequest,
    WorldAddonEntry,
    WorldProfileResponse,
    WorldProfileUpdateRequest,
)
from app.schemas.operations import MessageResponse, OperationResponse
from app.services import addons as addon_service

router = APIRouter(prefix="/api/addons", tags=["addons"])


def _addon(session, addon) -> AddonResponse:
    return AddonResponse.model_validate(addon_service.addon_to_dict(session, addon))


@router.get("", response_model=AddonListResponse)
def list_addons(
    session: SessionDep, settings: SettingsDep, _auth: AuthDep
) -> AddonListResponse:
    # Pull custom packs already present under /data into the library (idempotent).
    addon_service.import_packs_from_server_data(session, settings)
    items = addon_service.list_addons(session)
    return AddonListResponse(addons=[_addon(session, a) for a in items])


@router.get("/pending-tests", response_model=PendingTestsResponse)
def pending_tests(_admin: AdminDep) -> PendingTestsResponse:
    return PendingTestsResponse(pending=addon_service.list_pending_tests())


@router.post("/upload", response_model=AddonUploadResponse)
async def upload_addon(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
    file: UploadFile = File(...),
) -> AddonUploadResponse:
    filename = file.filename or "upload.mcaddon"
    suffix = Path(filename).suffix.lower() or ".mcaddon"
    if suffix not in {".mcaddon", ".mcpack", ".zip"}:
        raise AppError("Only .mcaddon, .mcpack, or .zip uploads are supported")
    max_bytes = settings.upload_max_mb * 1024 * 1024
    fd, tmp_name = tempfile.mkstemp(
        prefix="mf-addon-upload-", suffix=suffix, dir=str(settings.app_data_dir)
    )
    tmp_path = Path(tmp_name)
    try:
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
        created = addon_service.upload_addon(
            session,
            settings,
            upload_path=tmp_path,
            original_filename=filename,
            user_id=auth.user.id,  # type: ignore[arg-type]
            role=auth.user.role,
            ip=get_client_ip(request),
        )
        return AddonUploadResponse(addons=[_addon(session, a) for a in created])
    finally:
        tmp_path.unlink(missing_ok=True)
        await file.close()


@router.delete("/{addon_id}", response_model=MessageResponse)
def delete_addon(
    addon_id: int,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> MessageResponse:
    addon_service.delete_addon(
        session,
        settings,
        addon_id=addon_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return MessageResponse(detail="Deleted")


@router.get("/worlds/{world_id}", response_model=WorldProfileResponse)
def get_world_profile(
    world_id: int, session: SessionDep, settings: SettingsDep, _auth: AuthDep
) -> WorldProfileResponse:
    entries = addon_service.get_world_profile(session, world_id)
    return WorldProfileResponse(
        world_id=world_id,
        entries=[WorldAddonEntry.model_validate(e) for e in entries],
        download_size=addon_service.world_download_size(session, settings, world_id),
    )


@router.put("/worlds/{world_id}", response_model=WorldProfileResponse)
def put_world_profile(
    world_id: int,
    body: WorldProfileUpdateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> WorldProfileResponse:
    entries = addon_service.set_world_profile(
        session,
        world_id=world_id,
        entries=[e.model_dump() for e in body.entries],
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return WorldProfileResponse(
        world_id=world_id,
        entries=[WorldAddonEntry.model_validate(e) for e in entries],
        download_size=addon_service.world_download_size(session, settings, world_id),
    )


@router.post("/worlds/{world_id}/apply", response_model=AddonApplyResponse)
def apply_world_profile(
    world_id: int,
    body: AddonApplyRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> AddonApplyResponse:
    operation = addon_service.start_apply(
        session,
        settings,
        world_id=world_id,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
        test_mode=body.test_mode,
    )
    return AddonApplyResponse(operation=OperationResponse.model_validate(operation))


@router.post("/worlds/{world_id}/keep", response_model=MessageResponse)
def keep_test(
    world_id: int,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> MessageResponse:
    addon_service.keep_test(
        session, settings, world_id=world_id, user_id=auth.user.id  # type: ignore[arg-type]
    )
    return MessageResponse(detail="Kept")


@router.post("/worlds/{world_id}/revert", response_model=MessageResponse)
def revert_test(
    world_id: int,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> MessageResponse:
    addon_service.revert_test_now(
        session, settings, world_id=world_id, user_id=auth.user.id  # type: ignore[arg-type]
    )
    return MessageResponse(detail="Reverted")


@router.put("/texturepack-required", response_model=MessageResponse)
def texturepack_required(
    body: TexturepackRequiredRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> MessageResponse:
    addon_service.set_texturepack_required(
        session,
        settings,
        required=body.required,
        user_id=auth.user.id,  # type: ignore[arg-type]
        role=auth.user.role,
        ip=get_client_ip(request),
    )
    return MessageResponse(
        detail="texturepack-required=" + ("true" if body.required else "false")
    )
