"""Server control orchestration (status, start/stop/restart, dashboard bits)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from app.core.config import Settings
from app.services import server_props
from app.services.audit import record_audit
from app.services.docker_client import ContainerStatus, get_docker_client
from app.services.logwatch import get_server_started_at
from app.services.players import list_online_players


def get_status(session: Session, settings: Settings) -> dict:
    """Compose dashboard/server status payload."""

    docker = get_docker_client(settings)
    status: ContainerStatus = docker.status()
    online = list_online_players(session)
    level_name = None
    try:
        props = server_props.read_properties(settings)
        level_name = props.get("level-name")
    except Exception:
        props = {}

    started = status.started_at or get_server_started_at()
    uptime_seconds = None
    if status.running and started is not None:
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        uptime_seconds = int((datetime.now(UTC) - started).total_seconds())

    return {
        "container": {
            "name": status.name,
            "exists": status.exists,
            "running": status.running,
            "status": status.status,
            "image": status.image,
            "started_at": started.isoformat() if started else None,
            "uptime_seconds": uptime_seconds,
        },
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
