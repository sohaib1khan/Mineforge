"""Database engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a process-wide SQLAlchemy engine for SQLite."""

    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.resolved_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args)
    return _engine


def reset_engine() -> None:
    """Dispose and clear the cached engine (used by tests)."""

    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLModel session."""

    with Session(get_engine()) as session:
        yield session


def init_db() -> None:
    """Create all tables if they do not exist (dev/bootstrap helper)."""

    from app import models  # noqa: F401
    from app.db.base import SQLModel

    SQLModel.metadata.create_all(get_engine())
