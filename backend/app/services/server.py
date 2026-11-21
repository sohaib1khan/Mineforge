"""Server control orchestration (status, start/stop/restart, dashboard bits)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.errors import AppError
from app.models.world import World
from app.services import bedrock_nbt, server_props
from app.services.audit import record_audit
from app.services.docker_client import (
    ContainerRuntimeSnapshot,
    ContainerStatus,
    get_docker_client,
)
from app.services.logwatch import get_server_started_at
from app.services.players import list_online_players

logger = logging.getLogger(__name__)

GAMEMODE_TO_INT = {"survival": 0, "creative": 1, "adventure": 2}
DIFFICULTY_TO_INT = {"peaceful": 0, "easy": 1, "normal": 2, "hard": 3}

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


def update_properties(
    session: Session,
    settings: Settings,
    *,
    updates: dict[str, str],
    user_id: int,
    ip: str | None,
) -> dict[str, Any]:
    """Write whitelisted server.properties and sync gamemode/difficulty to the world.

    Bedrock keeps GameType/Difficulty in the active world's ``level.dat``. Editing
    only ``server.properties`` leaves imported creative worlds stuck in creative,
    so gamemode/difficulty changes also patch ``level.dat`` (server stopped briefly
    while the file is written). When gamemode changes, ``force-gamemode`` defaults
    to true so existing players pick up the mode on rejoin.

    Returns:
        Payload for PropertiesResponse including apply notes.

    Raises:
        AppError / ForbiddenError from validation, Docker, or level.dat patching.
    """

    pending = dict(updates)
    if "gamemode" in pending and "force-gamemode" not in pending:
        pending["force-gamemode"] = "true"

    needs_world_sync = "gamemode" in pending or "difficulty" in pending
    docker = get_docker_client(settings)
    was_running = False
    restarted = False
    world_synced = False
    patched_fields: list[str] = []
    notes: list[str] = []

    if needs_world_sync:
        was_running = bool(docker.status().running)
        if was_running:
            docker.stop()

    try:
        values = server_props.write_properties(settings, pending)
        if needs_world_sync:
            level_name = (values.get("level-name") or "").strip()
            if not level_name:
                raise AppError("level-name is not set; cannot sync world settings")
            level_dat = settings.data_dir / "worlds" / level_name / "level.dat"
            patch: dict[str, int] = {}
            if "gamemode" in pending:
                patch["GameType"] = GAMEMODE_TO_INT[pending["gamemode"]]
            if "difficulty" in pending:
                patch["Difficulty"] = DIFFICULTY_TO_INT[pending["difficulty"]]
            if level_dat.is_file():
                patched_fields = bedrock_nbt.patch_level_dat_ints(
                    level_dat,
                    patch,
                    uid=settings.bedrock_uid,
                    gid=settings.bedrock_gid,
                    strict=False,
                )
                world_synced = bool(patched_fields)
                skipped = [key for key in patch if key not in patched_fields]
                if skipped:
                    notes.append(
                        "level.dat was missing "
                        + ", ".join(skipped)
                        + "; those keys were left to server.properties only."
                    )
            else:
                notes.append(
                    "level.dat is not on disk yet; properties will apply when "
                    "Bedrock creates the world."
                )

            world = session.exec(
                select(World).where(World.folder_name == level_name)
            ).first()
            if world is not None:
                if "gamemode" in pending:
                    world.gamemode = pending["gamemode"]
                if "difficulty" in pending:
                    world.difficulty = pending["difficulty"]
                session.add(world)
    finally:
        if was_running:
            docker.start()
            restarted = True

    if world_synced:
        notes.append(
            "Synced GameType/Difficulty in the active world's level.dat"
            + (f" ({', '.join(patched_fields)})" if patched_fields else "")
            + "."
        )
    if "gamemode" in pending:
        notes.append(
            "force-gamemode is on — players should rejoin to pick up the new mode."
        )
    if restarted:
        notes.append("Bedrock was restarted to apply world settings safely.")

    record_audit(
        session,
        action="server.properties_update",
        user_id=user_id,
        details={
            "keys": sorted(pending.keys()),
            "world_synced": world_synced,
            "restarted": restarted,
            "patched_fields": patched_fields,
        },
        ip=ip,
    )
    session.commit()
    note = " ".join(notes) if notes else None
    if note:
        logger.info("Properties update: %s", note)
    return {
        "values": values,
        "catalog": server_props.property_catalog(),
        "world_synced": world_synced,
        "restarted": restarted,
        "note": note,
    }
