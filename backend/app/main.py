"""Application factory: mounts API routers and (later) the built SPA."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session

from app import __version__
from app.api.routes import (
    addons,
    audit,
    auth,
    backups,
    console,
    health,
    help,
    metrics,
    operations,
    server,
    setup,
    stream,
    users,
    worlds,
)
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.db.session import get_engine, init_db
from app.services import operations as operations_service
from app.services.logwatch import (
    close_duplicate_open_sessions,
    start_log_watcher,
    stop_log_watcher,
)
from app.services.setup import ensure_setup_code
from app.workers.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize DB, setup code, log watcher, and scheduler."""

    settings = get_settings()
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    (settings.app_data_dir / "backups").mkdir(parents=True, exist_ok=True)
    (settings.app_data_dir / "packs").mkdir(parents=True, exist_ok=True)
    init_db()
    with Session(get_engine()) as session:
        ensure_setup_code(session, settings)
        operations_service.recover_orphaned_operations(session)
        close_duplicate_open_sessions(session)
    start_log_watcher(settings)
    if settings.scheduler_enabled:
        start_scheduler(settings)
    logger.info("%s %s ready", settings.app_name, __version__)
    yield
    stop_scheduler()
    stop_log_watcher()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""

    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(setup.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(audit.router)
    app.include_router(server.router)
    app.include_router(console.router)
    app.include_router(backups.router)
    app.include_router(operations.router)
    app.include_router(worlds.router)
    app.include_router(addons.router)
    app.include_router(metrics.router)
    app.include_router(help.router)
    app.include_router(stream.router)

    static_dir = settings.static_dir
    if static_dir:
        static_path = Path(static_dir)
        if static_path.is_dir():
            assets = static_path / "assets"
            if assets.is_dir():
                app.mount("/assets", StaticFiles(directory=assets), name="assets")

            @app.get("/{full_path:path}")
            def spa_fallback(full_path: str) -> FileResponse:
                """Serve the SPA shell for non-API routes when static files exist."""

                candidate = static_path / full_path
                if full_path and candidate.is_file():
                    return FileResponse(candidate)
                return FileResponse(static_path / "index.html")

    return app


app = create_app()
