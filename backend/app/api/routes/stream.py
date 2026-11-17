"""Stream status, settings, key rotation, HLS proxy, and MediaMTX auth."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AdminCsrfDep,
    AuthDep,
    SessionDep,
    SettingsDep,
    get_client_ip,
)
from app.core.errors import ForbiddenError
from app.core.rate_limit import limiter
from app.schemas.stream import (
    MediaMtxAuthRequest,
    StreamKeyRotateResponse,
    StreamSettingsResponse,
    StreamSettingsUpdateRequest,
    StreamStatusResponse,
)
from app.services import stream as stream_service

router = APIRouter(tags=["stream"])
api_router = APIRouter(prefix="/api/stream", tags=["stream"])
internal_router = APIRouter(prefix="/internal/stream", tags=["stream-internal"])


@api_router.get("/status", response_model=StreamStatusResponse)
def stream_status(
    session: SessionDep,
    settings: SettingsDep,
    _auth: AuthDep,
) -> StreamStatusResponse:
    """Live/offline status for any logged-in user."""

    return StreamStatusResponse.model_validate(
        stream_service.get_status(session, settings)
    )


@api_router.get("/settings", response_model=StreamSettingsResponse)
def get_stream_settings(
    session: SessionDep,
    settings: SettingsDep,
    auth: AuthDep,
) -> StreamSettingsResponse:
    """Admin stream settings + OBS hints (admins only for full panel)."""

    if auth.user.role.value != "admin":
        raise ForbiddenError("Admin access required")
    row = stream_service.get_or_create_settings(session, settings)
    return StreamSettingsResponse.model_validate(
        stream_service.settings_to_dict(row, settings)
    )


@api_router.put("/settings", response_model=StreamSettingsResponse)
def update_stream_settings(
    body: StreamSettingsUpdateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> StreamSettingsResponse:
    row = stream_service.update_settings(
        session,
        settings,
        user=auth.user,
        title=body.title,
        description=body.description,
        enabled=body.enabled,
        ip=get_client_ip(request),
    )
    return StreamSettingsResponse.model_validate(
        stream_service.settings_to_dict(row, settings)
    )


@api_router.post("/key/rotate", response_model=StreamKeyRotateResponse)
def rotate_stream_key(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    auth: AdminCsrfDep,
) -> StreamKeyRotateResponse:
    plaintext, row = stream_service.rotate_key(
        session,
        settings,
        user=auth.user,
        ip=get_client_ip(request),
    )
    assert row.key_rotated_at is not None
    return StreamKeyRotateResponse(
        stream_key=plaintext,
        rtmp_server=stream_service.rtmp_server_url(settings),
        rtmp_url_example=stream_service.rtmp_url_with_key(settings, plaintext),
        key_rotated_at=row.key_rotated_at.isoformat(),
    )


@api_router.get("/hls/{path:path}")
def proxy_hls(
    path: str,
    settings: SettingsDep,
    _auth: AuthDep,
) -> StreamingResponse:
    """Proxy HLS playlists/segments for logged-in viewers."""

    body, media_type, headers = stream_service.proxy_hls(settings, path)
    return StreamingResponse(body, media_type=media_type, headers=headers)


@internal_router.post("/auth")
@limiter.limit("60/minute")
def mediamtx_auth(
    body: MediaMtxAuthRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    """MediaMTX HTTP auth callback (internal Docker network only)."""

    token = request.query_params.get("token")
    stream_service.verify_internal_caller(
        settings,
        client_ip=get_client_ip(request, settings),
        token=token,
    )
    allowed = stream_service.authorize_publish(
        session,
        settings,
        action=body.action,
        path=body.path,
        password=body.password,
        token=body.token,
        publisher_ip=body.ip or get_client_ip(request, settings),
        protocol=body.protocol,
    )
    if not allowed:
        return Response(status_code=401)
    return Response(status_code=200)


router.include_router(api_router)
router.include_router(internal_router)
