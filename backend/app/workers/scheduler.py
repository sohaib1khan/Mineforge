"""APScheduler jobs: backups, retention, and metrics sampling."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import Settings, get_settings
from app.services import backups as backup_service
from app.services import metrics as metrics_service

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler(settings: Settings | None = None) -> None:
    """Start the background scheduler (idempotent)."""

    global _scheduler
    if _scheduler is not None:
        return
    cfg = settings or get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _nightly_backup,
        CronTrigger(hour=5, minute=15),
        id="nightly_backup",
        replace_existing=True,
        kwargs={"settings": cfg},
    )
    scheduler.add_job(
        _retention,
        CronTrigger(hour=6, minute=0),
        id="backup_retention",
        replace_existing=True,
        kwargs={"settings": cfg},
    )
    if cfg.metrics_enabled:
        interval = max(15, int(cfg.metrics_sample_seconds))
        scheduler.add_job(
            _metrics_sample,
            IntervalTrigger(seconds=interval),
            id="metrics_sample",
            replace_existing=True,
            kwargs={"settings": cfg},
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            _metrics_retention,
            CronTrigger(hour=6, minute=30),
            id="metrics_retention",
            replace_existing=True,
            kwargs={"settings": cfg},
        )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started (nightly backup 05:15 UTC, retention 06:00 UTC, "
        "metrics every %ss)",
        max(15, int(cfg.metrics_sample_seconds)) if cfg.metrics_enabled else "off",
    )


def stop_scheduler() -> None:
    """Shut down the scheduler if running."""

    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


def _nightly_backup(settings: Settings) -> None:
    logger.info("Running scheduled backup job")
    try:
        backup_service.run_scheduled_backup(settings)
    except Exception:
        logger.exception("Scheduled backup job crashed")


def _retention(settings: Settings) -> None:
    from sqlmodel import Session

    from app.db.session import get_engine

    logger.info("Running backup retention job")
    try:
        with Session(get_engine()) as session:
            removed = backup_service.apply_retention(session, settings)
            logger.info("Retention removed %s backup(s)", removed)
    except Exception:
        logger.exception("Retention job crashed")


def _metrics_sample(settings: Settings) -> None:
    try:
        metrics_service.run_scheduled_sample(settings)
    except Exception:
        logger.exception("Metrics sample job crashed")


def _metrics_retention(settings: Settings) -> None:
    try:
        metrics_service.run_scheduled_retention(settings)
    except Exception:
        logger.exception("Metrics retention job crashed")
