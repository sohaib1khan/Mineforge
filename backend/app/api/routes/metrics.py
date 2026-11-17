"""Metrics overview and dashboard widgets."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import AuthDep, SessionDep, SettingsDep
from app.schemas.metrics import (
    BackupHistoryEntry,
    DiskSummaryResponse,
    JoinsDayEntry,
    MetricSampleResponse,
    MetricsDashboardResponse,
    MetricsOverviewResponse,
    PlaytimeEntry,
    WorldDiskEntry,
)
from app.services import metrics as metrics_service

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/overview", response_model=MetricsOverviewResponse)
def metrics_overview(
    session: SessionDep,
    settings: SettingsDep,
    _auth: AuthDep,
    hours: int = Query(default=24, ge=1, le=24 * 31),
    playtime_days: int = Query(default=7, ge=1, le=90),
) -> MetricsOverviewResponse:
    """Full Metrics page payload (authenticated)."""

    samples = metrics_service.list_samples(session, hours=hours)
    disk = metrics_service.disk_summary(session, settings)
    return MetricsOverviewResponse(
        samples=[
            MetricSampleResponse.model_validate(metrics_service.sample_to_dict(s))
            for s in samples
        ],
        playtime=[
            PlaytimeEntry.model_validate(row)
            for row in metrics_service.playtime_leaderboard(session, days=playtime_days)
        ],
        joins=[
            JoinsDayEntry.model_validate(row)
            for row in metrics_service.joins_over_time(session, days=playtime_days)
        ],
        disk=DiskSummaryResponse(
            worlds=[WorldDiskEntry.model_validate(w) for w in disk["worlds"]],
            worlds_bytes=disk["worlds_bytes"],
            backups_bytes=disk["backups_bytes"],
            backup_count=disk["backup_count"],
        ),
        backups=[
            BackupHistoryEntry.model_validate(row)
            for row in metrics_service.backup_history(session)
        ],
        sample_interval_seconds=settings.metrics_sample_seconds,
        retention_days=settings.metrics_retention_days,
    )


@router.get("/dashboard", response_model=MetricsDashboardResponse)
def metrics_dashboard(
    session: SessionDep,
    settings: SettingsDep,
    _auth: AuthDep,
) -> MetricsDashboardResponse:
    """Compact snapshot for Home dashboard widgets."""

    snap = metrics_service.dashboard_snapshot(session, settings)
    latest = snap["latest"]
    return MetricsDashboardResponse(
        latest=MetricSampleResponse.model_validate(latest) if latest else None,
        playtime_week=[
            PlaytimeEntry.model_validate(row) for row in snap["playtime_week"]
        ],
        disk=snap["disk"],
        players_online=snap["players_online"],
    )
