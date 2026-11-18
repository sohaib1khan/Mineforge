"""Server control orchestration (status, start/stop/restart, dashboard bits)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from app.core.config import Settings
from app.services import server_props
from app.services.audit import record_audit
from app.services.docker_client import (
    ContainerRuntimeSnapshot,
    ContainerStatus,
    get_docker_client,
)
from app.services.logwatch import get_server_started_at
from app.services.players import list_online_players

# Keys from server.properties useful on the status panel.
_PROP_KEYS = (
    "server-name",
    "level-name",
    "gamemode",
    "difficulty",
    "max-players",
    "online-mode",
    "allow-list",
    "server-port",
    "server-portv6",
    "view-distance",
    "tick-distance",
)


def get_status(session: Session, settings: Settings) -> dict:
    """Compose dashboard/server status payload with container runtime details."""

    docker = get_docker_client(settings)
    status: ContainerStatus = docker.status()
    runtime = _runtime_or_none(docker)
    online = list_online_players(session)
    level_name = None
    props: dict[str, str] = {}
    try:
        props = server_props.read_properties(settings)
        level_name = props.get("level-name")
    except Exception:
        props = {}

    started = status.started_at or get_server_started_at()
    if runtime and runtime.started_at and status.started_at is None:
        started = runtime.started_at
    uptime_seconds = None
    if status.running and started is not None:
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        uptime_seconds = int((datetime.now(UTC) - started).total_seconds())

    container = _container_payload(status, runtime, started, uptime_seconds)
    resources = _resources_payload(runtime)
    warnings = _status_warnings(runtime, level_name)

    return {
        "container": container,
        "resources": resources,
        "ports": [
            {"private": p.private, "public": p.public}
            for p in (runtime.ports if runtime and runtime.ports else [])
        ],
        "mounts": [
            {"destination": m.destination, "mode": m.mode, "type": m.type}
            for m in (runtime.mounts if runtime and runtime.mounts else [])
        ],
        "safe_env": dict(runtime.safe_env) if runtime and runtime.safe_env else {},
        "server_settings": {
            key: props[key] for key in _PROP_KEYS if key in props and props[key] != ""
        },
        "warnings": warnings,
        "level_name": level_name,
        "players_online": [
            {
                "gamertag": p.gamertag,
                "xuid": p.xuid,
                "joined_at": p.joined_at.isoformat() if p.joined_at else None,
            }
            for p in online
        ],
        "player_count": len(online),
        "properties_present": bool(props),
    }


def _runtime_or_none(docker: Any) -> ContainerRuntimeSnapshot | None:
    fn = getattr(docker, "runtime_snapshot", None)
    if not callable(fn):
        return None
    try:
        return fn()
    except Exception:
        return None


def _container_payload(
    status: ContainerStatus,
    runtime: ContainerRuntimeSnapshot | None,
    started: datetime | None,
    uptime_seconds: int | None,
) -> dict[str, Any]:
    return {
        "name": status.name,
        "exists": status.exists,
        "running": status.running,
        "status": status.status,
        "image": status.image or (runtime.image if runtime else None),
        "started_at": started.isoformat() if started else None,
        "uptime_seconds": uptime_seconds,
        "finished_at": (
            runtime.finished_at.isoformat() if runtime and runtime.finished_at else None
        ),
        "created_at": (
            runtime.created_at.isoformat() if runtime and runtime.created_at else None
        ),
        "exit_code": (
            runtime.exit_code
            if runtime and runtime.exit_code is not None
            else status.exit_code
        ),
        "pid": runtime.pid if runtime else None,
        "restart_count": runtime.restart_count if runtime else 0,
        "oom_killed": bool(runtime.oom_killed) if runtime else False,
        "error": runtime.error if runtime else None,
        "health": runtime.health if runtime else None,
        "restart_policy": runtime.restart_policy if runtime else None,
        "platform": runtime.platform if runtime else None,
    }


def _resources_payload(
    runtime: ContainerRuntimeSnapshot | None,
) -> dict[str, Any] | None:
    if not runtime or not runtime.stats or not runtime.stats.running:
        return None
    stats = runtime.stats
    mem_pct = None
    if stats.mem_limit_bytes > 0:
        mem_pct = round(100.0 * stats.mem_bytes / stats.mem_limit_bytes, 1)
    return {
        "cpu_pct": stats.cpu_pct,
        "mem_bytes": stats.mem_bytes,
        "mem_limit_bytes": stats.mem_limit_bytes,
        "mem_pct": mem_pct,
        "net_rx_bytes": stats.net_rx_bytes,
        "net_tx_bytes": stats.net_tx_bytes,
    }


def _status_warnings(
    runtime: ContainerRuntimeSnapshot | None, level_name: str | None
) -> list[str]:
    warnings: list[str] = []
    if runtime and runtime.oom_killed:
        warnings.append("Container was OOM-killed. Check memory limits.")
    if runtime and runtime.error:
        warnings.append(f"Docker reported: {runtime.error}")
    if runtime and runtime.level_name_env:
        warnings.append(
            "Container env LEVEL_NAME is set — itzg may overwrite server.properties "
            "on start and undo world switches. Remove LEVEL_NAME from the Bedrock "
            "compose/env."
        )
        if level_name and runtime.level_name_env != level_name:
            warnings.append(
                f"LEVEL_NAME env ({runtime.level_name_env}) differs from "
                f"server.properties level-name ({level_name})."
            )
    if (
        runtime
        and runtime.health
        and runtime.health.lower() in {"unhealthy", "starting"}
    ):
        warnings.append(f"Container health is {runtime.health}.")
    return warnings


def start_server(
    session: Session, settings: Settings, *, user_id: int, ip: str | None
) -> None:
    """Start the Bedrock container and audit the action."""

    get_docker_client(settings).start()
    record_audit(session, action="server.start", user_id=user_id, ip=ip)
    session.commit()


def stop_server(
    session: Session, settings: Settings, *, user_id: int, ip: str | None
) -> None:
    """Stop the Bedrock container and audit the action."""

    get_docker_client(settings).stop()
    record_audit(session, action="server.stop", user_id=user_id, ip=ip)
    session.commit()


def restart_server(
    session: Session, settings: Settings, *, user_id: int, ip: str | None
) -> None:
    """Restart the Bedrock container and audit the action."""

    get_docker_client(settings).restart()
    record_audit(session, action="server.restart", user_id=user_id, ip=ip)
    session.commit()
