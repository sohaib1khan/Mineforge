"""Settings loading tests (placeholder values only)."""

import pytest
from app.core.config import Settings


def test_default_settings_use_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults must be placeholders — never real secrets or hosts."""

    # Clear MineForge env so we assert code defaults, not container env.
    for name in (
        "MINEFORGE_SECRET_KEY",
        "MINEFORGE_PUBLIC_URL",
        "MINEFORGE_APP_NAME",
        "MINEFORGE_COOKIE_SECURE",
        "MINEFORGE_APP_DATA_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)
    assert "CHANGE_ME" in settings.secret_key
    assert "example.com" in settings.public_url
    assert settings.app_name == "MineForge"
