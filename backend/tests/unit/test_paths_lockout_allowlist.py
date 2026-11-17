"""Unit tests for paths, lockout, allowlist, and help guides."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.api.deps import get_client_ip
from app.core.config import Settings, clear_settings_cache, get_settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.services import allowlist as allowlist_service
from app.services import help_guides, lockout
from app.services.paths import resolve_under


def test_resolve_under_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    ok = resolve_under(root, "safe.txt")
    assert ok == (root / "safe.txt").resolve()
    with pytest.raises(ForbiddenError):
        resolve_under(root, "..", "outside.txt")


def test_lockout_trips_and_clears() -> None:
    lockout.reset_lockouts()
    settings = Settings(
        secret_key="test-secret-key-not-real",
        login_max_attempts=3,
        login_lockout_minutes=15,
    )
    lockout.assert_not_locked("admin_one", "127.0.0.1", settings)
    lockout.record_failure("admin_one", "127.0.0.1", settings)
    lockout.record_failure("admin_one", "127.0.0.1", settings)
    lockout.record_failure("admin_one", "127.0.0.1", settings)
    with pytest.raises(ForbiddenError):
        lockout.assert_not_locked("admin_one", "127.0.0.1", settings)
    lockout.clear_failures("admin_one", "127.0.0.1")
    lockout.assert_not_locked("admin_one", "127.0.0.1", settings)
    lockout.reset_lockouts()


def test_allowlist_and_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_SECRET_KEY", "test-secret-key-not-real")
    clear_settings_cache()
    settings = get_settings()
    entries = allowlist_service.add_allowlist_entry(settings, name="player_one")
    assert any(e.get("name") == "player_one" for e in entries)
    with pytest.raises(ConflictError):
        allowlist_service.add_allowlist_entry(settings, name="player_one")
    removed = allowlist_service.remove_allowlist_entry(settings, "player_one")
    assert all(e.get("name") != "player_one" for e in removed)
    with pytest.raises(NotFoundError):
        allowlist_service.remove_allowlist_entry(settings, "missing_player")

    ops = allowlist_service.set_permission(
        settings, xuid="2535400000000001", permission="operator", name="player_one"
    )
    assert any(e.get("xuid") == "2535400000000001" for e in ops)
    assert allowlist_service.list_ops(settings)
    cleared = allowlist_service.remove_permission(settings, "2535400000000001")
    assert all(e.get("xuid") != "2535400000000001" for e in cleared)
    clear_settings_cache()


def test_allowlist_write_permission_error_is_app_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.errors import AppError

    data = tmp_path / "ro-data"
    data.mkdir()
    data.chmod(0o555)
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_SECRET_KEY", "test-secret-key-not-real")
    clear_settings_cache()
    settings = get_settings()
    try:
        with pytest.raises(AppError, match="Cannot write allowlist"):
            allowlist_service.add_allowlist_entry(settings, name="player_one")
    finally:
        data.chmod(0o755)
        clear_settings_cache()


def test_help_guides_packaged() -> None:
    guides = help_guides.list_guides()
    assert len(guides) >= 5
    connecting = help_guides.get_guide("connecting")
    assert "19132" in connecting["markdown"]
    with pytest.raises(NotFoundError):
        help_guides.get_guide("../etc/passwd")
    with pytest.raises(NotFoundError):
        help_guides.get_guide("no-such-guide")


def test_get_client_ip_respects_proxy_flag() -> None:
    class _Client:
        host = "10.0.0.2"

    class _Req:
        def __init__(self, headers: dict[str, str]) -> None:
            self.headers = headers
            self.client = _Client()

    direct = Settings(
        secret_key="test-secret-key-not-real",
        trust_proxy_headers=False,
    )
    proxied = Settings(
        secret_key="test-secret-key-not-real",
        trust_proxy_headers=True,
    )
    req = _Req(
        {"x-forwarded-for": "203.0.113.50, 10.0.0.1", "x-real-ip": "198.51.100.9"}
    )
    assert get_client_ip(req, direct) == "10.0.0.2"  # type: ignore[arg-type]
    assert get_client_ip(req, proxied) == "203.0.113.50"  # type: ignore[arg-type]
