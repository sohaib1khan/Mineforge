"""Metrics overview and dashboard widgets."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import AuthDep, SessionDep, SettingsDep
from app.models.user import UserRole
from app.schemas.metrics import (
    BackupHistoryEntry,
    DiskSummaryResponse,
    JoinsDayEntry,
    LoginActivityResponse,
    MetricSampleResponse,
    MetricsDashboardResponse,
    MetricsOverviewResponse,
    PlaytimeEntry,
    WorldDiskEntry,
    WorldInsightResponse,
)
from app.services import metrics as metrics_service

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _login_activity_for_viewer(
    payload: dict[str, Any], *, is_admin: bool
) -> LoginActivityResponse:
    """Hide login IPs (and user roster detail) from non-admins."""

    data = dict(payload)
    if not is_admin:
        data["recent"] = [{**row, "ip": None} for row in list(data.get("recent") or [])]
        data["users"] = []
    return LoginActivityResponse.model_validate(data)


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
    extras = metrics_service.overview_extras(session, settings)
    is_admin = _auth.user.role == UserRole.ADMIN
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
        world_insight=WorldInsightResponse.model_validate(extras["world_insight"]),
        login_activity=_login_activity_for_viewer(
            extras["login_activity"], is_admin=is_admin
        ),
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
    is_admin = _auth.user.role == UserRole.ADMIN
    return MetricsDashboardResponse(
        latest=MetricSampleResponse.model_validate(latest) if latest else None,
        playtime_week=[
            PlaytimeEntry.model_validate(row) for row in snap["playtime_week"]
        ],
        disk=snap["disk"],
        players_online=snap["players_online"],
        world_insight=WorldInsightResponse.model_validate(snap["world_insight"]),
        login_activity=_login_activity_for_viewer(
            snap["login_activity"], is_admin=is_admin
        ),
    )
