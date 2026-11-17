"""Metrics sampling, aggregation, and retention.

Business logic for Phase 7: Docker stats snapshots, session playtime,
disk usage, and chart series for the Metrics UI.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, col, func, select

from app.core.config import Settings, get_settings
from app.models.backup import Backup
from app.models.metric_sample import MetricSample
from app.models.player_session import PlayerSession
from app.models.world import World
from app.services.archive_safety import dir_size
from app.services.backups import backups_dir
from app.services.docker_client import get_docker_client
from app.services.players import list_online_players

logger = logging.getLogger(__name__)


def sample_and_store(
    session: Session,
    settings: Settings | None = None,
) -> MetricSample | None:
    """Take one Docker stats + player-count sample and persist it.

    Returns the stored row, or None when metrics are disabled.
    Does not raise on Docker failures — stores a zeroed sample instead.
    """

    cfg = settings or get_settings()
    if not cfg.metrics_enabled:
        return None

    players = len(list_online_players(session))
    try:
        stats = get_docker_client(cfg).sample_stats()
        cpu = stats.cpu_pct
        mem = stats.mem_bytes
        mem_limit = stats.mem_limit_bytes
        net_rx = stats.net_rx_bytes
        net_tx = stats.net_tx_bytes
    except Exception:
        logger.exception("Metric sampling failed; storing zeros")
        cpu = mem = mem_limit = net_rx = net_tx = 0

    row = MetricSample(
        ts=datetime.now(UTC),
        cpu_pct=float(cpu),
        mem_bytes=int(mem),
        mem_limit_bytes=int(mem_limit),
        net_rx_bytes=int(net_rx),
        net_tx_bytes=int(net_tx),
        players_online=players,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def apply_metrics_retention(
    session: Session,
    settings: Settings | None = None,
) -> int:
    """Delete metric samples older than retention days. Returns rows removed."""

    cfg = settings or get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=max(1, cfg.metrics_retention_days))
    old = session.exec(select(MetricSample).where(col(MetricSample.ts) < cutoff)).all()
    count = len(old)
    for row in old:
        session.delete(row)
    if count:
        session.commit()
    return count


def run_scheduled_sample(settings: Settings) -> None:
    """Scheduler entrypoint: open a session and sample once."""

    from app.db.session import get_engine

    with Session(get_engine()) as session:
        sample_and_store(session, settings)


def run_scheduled_retention(settings: Settings) -> None:
    """Scheduler entrypoint: prune old metric samples."""

    from app.db.session import get_engine

    with Session(get_engine()) as session:
        removed = apply_metrics_retention(session, settings)
        if removed:
            logger.info("Metrics retention removed %s sample(s)", removed)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def list_samples(
    session: Session,
    *,
    hours: int = 24,
    limit: int = 2880,
) -> list[MetricSample]:
    """Return metric samples from the last ``hours``, oldest first.

    Default limit covers ~30s * 24h ≈ 2880 points.
    """

    hours = max(1, min(hours, 24 * 31))
    limit = max(1, min(limit, 10_000))
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    rows = session.exec(
        select(MetricSample)
        .where(col(MetricSample.ts) >= cutoff)
        .order_by(col(MetricSample.ts).asc())
        .limit(limit)
    ).all()
    return list(rows)


def sample_to_dict(row: MetricSample) -> dict[str, Any]:
    """Serialize a MetricSample for API responses."""

    return {
        "id": row.id,
        "ts": _ensure_aware(row.ts).isoformat(),
        "cpu_pct": row.cpu_pct,
        "mem_bytes": row.mem_bytes,
        "mem_limit_bytes": row.mem_limit_bytes,
        "net_rx_bytes": row.net_rx_bytes,
        "net_tx_bytes": row.net_tx_bytes,
        "players_online": row.players_online,
    }


def playtime_leaderboard(
    session: Session,
    *,
    days: int = 7,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Aggregate closed + open session seconds per gamertag over ``days``.

    Open sessions (left_at is None) count through now.
    """

    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    cutoff = datetime.now(UTC) - timedelta(days=days)
    now = datetime.now(UTC)
    rows = session.exec(
        select(PlayerSession).where(col(PlayerSession.joined_at) >= cutoff)
    ).all()

    totals: dict[str, float] = {}
    for row in rows:
        start = _ensure_aware(row.joined_at)
        end = _ensure_aware(row.left_at) if row.left_at else now
        if end < start:
            continue
        # Clip to window
        if start < cutoff:
            start = cutoff
        seconds = (end - start).total_seconds()
        if seconds <= 0:
            continue
        totals[row.gamertag] = totals.get(row.gamertag, 0.0) + seconds

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [
        {"gamertag": name, "seconds": int(secs), "hours": round(secs / 3600.0, 2)}
        for name, secs in ranked
    ]


def joins_over_time(
    session: Session,
    *,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Count joins per UTC calendar day for the last ``days``."""

    days = max(1, min(days, 90))
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = session.exec(
        select(PlayerSession).where(col(PlayerSession.joined_at) >= cutoff)
    ).all()
    buckets: dict[str, int] = {}
    for row in rows:
        day = _ensure_aware(row.joined_at).date().isoformat()
        buckets[day] = buckets.get(day, 0) + 1
    # Fill empty days for a continuous chart
    out: list[dict[str, Any]] = []
    for offset in range(days, -1, -1):
        day = (datetime.now(UTC) - timedelta(days=offset)).date().isoformat()
        out.append({"day": day, "joins": buckets.get(day, 0)})
    return out


def disk_summary(session: Session, settings: Settings) -> dict[str, Any]:
    """World sizes + backup storage for the Metrics overview."""

    worlds = session.exec(select(World).order_by(col(World.display_name).asc())).all()
    world_rows = [
        {
            "id": w.id,
            "display_name": w.display_name,
            "folder_name": w.folder_name,
            "size_bytes": int(w.size_bytes or 0),
            "is_active": bool(w.is_active),
        }
        for w in worlds
    ]
    bdir = backups_dir(settings)
    backup_count = session.exec(select(func.count()).select_from(Backup)).one()
    return {
        "worlds": world_rows,
        "worlds_bytes": sum(w["size_bytes"] for w in world_rows),
        "backups_bytes": dir_size(bdir),
        "backup_count": int(backup_count or 0),
    }


def backup_history(
    session: Session,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Recent backups for a simple history chart/list."""

    limit = max(1, min(limit, 100))
    rows = session.exec(
        select(Backup).order_by(col(Backup.created_at).desc()).limit(limit)
    ).all()
    out: list[dict[str, Any]] = []
    for b in reversed(rows):
        created = b.created_at
        ts = _ensure_aware(created).isoformat() if created else None
        out.append(
            {
                "id": b.id,
                "world_folder": b.world_folder,
                "kind": b.kind.value if hasattr(b.kind, "value") else str(b.kind),
                "size_bytes": int(b.size_bytes or 0),
                "verified": bool(b.verified),
                "created_at": ts,
            }
        )
    return out


def latest_sample(session: Session) -> MetricSample | None:
    """Return the most recent metric sample, if any."""

    return session.exec(
        select(MetricSample).order_by(col(MetricSample.ts).desc()).limit(1)
    ).first()


def dashboard_snapshot(
    session: Session,
    settings: Settings,
) -> dict[str, Any]:
    """Compact payload for Home dashboard widgets."""

    latest = latest_sample(session)
    playtime = playtime_leaderboard(session, days=7, limit=5)
    disk = disk_summary(session, settings)
    return {
        "latest": sample_to_dict(latest) if latest else None,
        "playtime_week": playtime,
        "disk": {
            "worlds_bytes": disk["worlds_bytes"],
            "backups_bytes": disk["backups_bytes"],
            "backup_count": disk["backup_count"],
        },
        "players_online": len(list_online_players(session)),
    }
