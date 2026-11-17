"""First-run setup endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import SessionDep, SettingsDep, get_client_ip
from app.core.rate_limit import limiter
from app.schemas.auth import SetupRequest, SetupStatusResponse, UserPublic
from app.services import setup as setup_service

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusResponse)
def setup_status(session: SessionDep, settings: SettingsDep) -> SetupStatusResponse:
    """Report whether first-run setup is still required."""

    return SetupStatusResponse(
        needs_setup=setup_service.needs_setup(session),
        app_name=settings.app_name,
    )


@router.post("", response_model=UserPublic)
@limiter.limit("5/minute")
def complete_setup(
    body: SetupRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> UserPublic:
    """Create the initial admin when none exists yet."""

    admin = setup_service.complete_setup(
        session,
        settings,
        username=body.username,
        password=body.password,
        ip=get_client_ip(request),
        setup_code=body.setup_code,
    )
    return UserPublic.model_validate(admin)
