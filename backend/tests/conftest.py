"""Shared pytest fixtures — fake data only."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from app.core.config import clear_settings_cache
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.db.session import get_engine, get_session, init_db, reset_engine
from app.main import create_app
from app.models.user import User, UserRole
from app.services import lockout
from fastapi.testclient import TestClient
from sqlmodel import Session

# SlowAPI shares one in-memory bucket for TestClient's "testclient" IP across
# the whole pytest process — disable it for unit/integration tests.
limiter.enabled = False


def _reset_rate_limits() -> None:
    """Keep SlowAPI disabled and clear any in-memory counters."""

    limiter.enabled = False
    try:
        storage = getattr(limiter, "_storage", None) or getattr(
            getattr(limiter, "limiter", None), "_storage", None
        )
        if storage is not None and hasattr(storage, "reset"):
            storage.reset()
        elif storage is not None and hasattr(storage, "storage"):
            storage.storage.clear()
    except Exception:
        pass


@pytest.fixture()
def app_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "app-data"
    data.mkdir()
    bedrock_data = tmp_path / "data"
    bedrock_data.mkdir()
    monkeypatch.setenv("MINEFORGE_APP_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(bedrock_data))
    monkeypatch.setenv("MINEFORGE_SECRET_KEY", "test-secret-key-not-real")
    monkeypatch.setenv("MINEFORGE_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("MINEFORGE_COOKIE_SECURE", "false")
    monkeypatch.setenv("MINEFORGE_LOGWATCH_ENABLED", "false")
    monkeypatch.setenv("MINEFORGE_SCHEDULER_ENABLED", "false")
    clear_settings_cache()
    reset_engine()
    lockout.reset_lockouts()
    _reset_rate_limits()
    init_db()
    yield data
    from app.services.docker_client import set_docker_client_override
    from app.services.logwatch import stop_log_watcher

    stop_log_watcher()
    set_docker_client_override(None)
    from app.services.addons import reset_pending_tests_for_tests, set_apply_fail_hook
    from app.services.backups import set_restore_fail_hook
    from app.services.operations import reset_locks_for_tests
    from app.services.switch import reset_consents_for_tests, set_switch_fail_hook
    from app.workers.scheduler import stop_scheduler

    set_restore_fail_hook(None)
    set_switch_fail_hook(None)
    set_apply_fail_hook(None)
    reset_consents_for_tests()
    reset_pending_tests_for_tests()
    reset_locks_for_tests()
    stop_scheduler()
    reset_engine()
    clear_settings_cache()
    lockout.reset_lockouts()
    _reset_rate_limits()


@pytest.fixture()
def db_session(app_data_dir: Path) -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


@pytest.fixture()
def client(app_data_dir: Path) -> Generator[TestClient, None, None]:
    application = create_app()

    def _override_session() -> Generator[Session, None, None]:
        with Session(get_engine()) as session:
            yield session

    application.dependency_overrides[get_session] = _override_session
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db_session: Session) -> User:
    user = User(
        username="admin_one",
        password_hash=hash_password("admin-password-12"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def player_user(db_session: Session) -> User:
    user = User(
        username="player_one",
        password_hash=hash_password("player-password-12"),
        role=UserRole.PLAYER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()
