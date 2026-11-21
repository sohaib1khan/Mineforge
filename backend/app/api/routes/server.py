"""Server status, controls, properties, allowlist, network, and ops."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import (
    AdminCsrfDep,
    AdminDep,
    AuthDep,
    SessionDep,
    SettingsDep,
    get_client_ip,
)
from app.schemas.network import (
    ApplyPublicIpRequest,
    NetworkStatusResponse,
    VersionInfoResponse,
)
from app.schemas.server import (
    AllowlistAddRequest,
    AllowlistResponse,
    MessageResponse,
    PermissionEntryRequest,
    PermissionsResponse,
    PropertiesResponse,
    PropertiesUpdateRequest,
    ServerStatusResponse,
)
from app.services import allowlist as allowlist_service
from app.services import network as network_service
from app.services import server as server_service
from app.services import server_props
from app.services.audit import record_audit
from app.services.docker_client import get_docker_client

router = APIRouter(prefix="/api/server", tags=["server"])


@router.get("/status", response_model=ServerStatusResponse)
def server_status(
    session: SessionDep, settings: SettingsDep, _auth: AuthDep
) -> ServerStatusResponse:
    """Return container status, active level, and online players."""

    payload = server_service.get_status(session, settings)
    return ServerStatusResponse.model_validate(payload)


@router.post("/start", response_model=MessageResponse)
def start_server(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> MessageResponse:
    """Start the Bedrock container (admin)."""

    server_service.start_server(
        session, settings, user_id=admin.user.id, ip=get_client_ip(request)  # type: ignore[arg-type]
    )
    return MessageResponse(detail="Starting")


@router.post("/stop", response_model=MessageResponse)
def stop_server(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> MessageResponse:
    """Stop the Bedrock container (admin)."""

    server_service.stop_server(
        session, settings, user_id=admin.user.id, ip=get_client_ip(request)  # type: ignore[arg-type]
    )
    return MessageResponse(detail="Stopping")


@router.post("/restart", response_model=MessageResponse)
def restart_server(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> MessageResponse:
    """Restart the Bedrock container (admin)."""

    server_service.restart_server(
        session, settings, user_id=admin.user.id, ip=get_client_ip(request)  # type: ignore[arg-type]
    )
    return MessageResponse(detail="Restarting")


@router.get("/properties", response_model=PropertiesResponse)
def get_properties(settings: SettingsDep, _admin: AdminDep) -> PropertiesResponse:
    """Read server.properties plus the editable catalog (admin)."""

    try:
        values = server_props.read_properties(settings)
    except Exception:
        values = {}
    return PropertiesResponse(values=values, catalog=server_props.property_catalog())


@router.put("/properties", response_model=PropertiesResponse)
def update_properties(
    body: PropertiesUpdateRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> PropertiesResponse:
    """Update whitelisted server.properties keys (admin).

    Gamemode/difficulty also sync into the active world's level.dat.
    """

    result = server_service.update_properties(
        session,
        settings,
        updates=body.updates,
        user_id=admin.user.id,
        ip=get_client_ip(request),
    )
    return PropertiesResponse.model_validate(result)


@router.get("/network", response_model=NetworkStatusResponse)
def get_network(settings: SettingsDep, _admin: AdminDep) -> NetworkStatusResponse:
    """NetherNet network panel (admin, no external lookup)."""

    return NetworkStatusResponse.model_validate(
        network_service.network_status(settings)
    )


@router.post("/network/detect", response_model=NetworkStatusResponse)
def detect_network(
    settings: SettingsDep,
    _admin: AdminCsrfDep,
) -> NetworkStatusResponse:
    """Lookup public IP and compare with advertised server-udp-ports (admin)."""

    return NetworkStatusResponse.model_validate(
        network_service.detect_public_ip(settings)
    )


@router.post("/network/apply", response_model=NetworkStatusResponse)
def apply_network(
    body: ApplyPublicIpRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> NetworkStatusResponse:
    """Write server-udp-ports for the public IP and restart Bedrock (admin)."""

    result = network_service.apply_public_ip(
        session,
        settings,
        user_id=admin.user.id,  # type: ignore[arg-type]
        ip_address=body.ip_address,
        restart=body.restart,
        client_ip=get_client_ip(request),
    )
    return NetworkStatusResponse.model_validate(result)


@router.get("/version", response_model=VersionInfoResponse)
def get_version(settings: SettingsDep, _admin: AdminDep) -> VersionInfoResponse:
    """Bedrock VERSION env / image pinning guidance (admin)."""

    info = get_docker_client(settings).version_info()
    return VersionInfoResponse(
        image=info.image,
        version_env=info.version_env,
        pinned=info.pinned,
        guidance=info.guidance,
    )


@router.get("/allowlist", response_model=AllowlistResponse)
def get_allowlist(settings: SettingsDep, _admin: AdminDep) -> AllowlistResponse:
    return AllowlistResponse(entries=allowlist_service.list_allowlist(settings))


@router.post("/allowlist", response_model=AllowlistResponse)
def add_allowlist(
    body: AllowlistAddRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> AllowlistResponse:
    entries = allowlist_service.add_allowlist_entry(
        settings, name=body.name, xuid=body.xuid
    )
    record_audit(
        session,
        action="server.allowlist_add",
        user_id=admin.user.id,
        target=body.name,
        ip=get_client_ip(request),
    )
    session.commit()
    return AllowlistResponse(entries=entries)


@router.delete("/allowlist/{name}", response_model=AllowlistResponse)
def delete_allowlist(
    name: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> AllowlistResponse:
    entries = allowlist_service.remove_allowlist_entry(settings, name)
    record_audit(
        session,
        action="server.allowlist_remove",
        user_id=admin.user.id,
        target=name,
        ip=get_client_ip(request),
    )
    session.commit()
    return AllowlistResponse(entries=entries)


@router.get("/permissions", response_model=PermissionsResponse)
def get_permissions(settings: SettingsDep, _admin: AdminDep) -> PermissionsResponse:
    return PermissionsResponse(entries=allowlist_service.list_ops(settings))


@router.put("/permissions", response_model=PermissionsResponse)
def put_permission(
    body: PermissionEntryRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> PermissionsResponse:
    entries = allowlist_service.set_permission(
        settings, xuid=body.xuid, permission=body.permission, name=body.name
    )
    record_audit(
        session,
        action="server.permissions_set",
        user_id=admin.user.id,
        target=body.xuid,
        details={"permission": body.permission},
        ip=get_client_ip(request),
    )
    session.commit()
    return PermissionsResponse(entries=entries)


@router.delete("/permissions/{xuid}", response_model=PermissionsResponse)
def delete_permission(
    xuid: str,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> PermissionsResponse:
    entries = allowlist_service.remove_permission(settings, xuid)
    record_audit(
        session,
        action="server.permissions_remove",
        user_id=admin.user.id,
        target=xuid,
        ip=get_client_ip(request),
    )
    session.commit()
    return PermissionsResponse(entries=entries)
