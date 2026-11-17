"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets must come from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="MINEFORGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MineForge"
    public_url: str = "https://mineforge.example.com"
    secret_key: str = "CHANGE_ME_LONG_RANDOM"
    bedrock_container: str = "bedrock"
    backup_retention_days: int = 7
    upload_max_mb: int = 512
    static_dir: str | None = None
    app_data_dir: Path = Path("./app-data")
    data_dir: Path = Path("/data")
    database_url: str | None = None
    session_days: int = 7
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    cookie_secure: bool | None = None
    docker_host: str | None = None
    bedrock_uid: int = 1000
    bedrock_gid: int = 1000
    logwatch_enabled: bool = True
    scheduler_enabled: bool = True
    switch_cooldown_minutes: int = 10
    switch_countdown_seconds: int = 30
    addon_test_minutes: int = 10
    metrics_sample_seconds: int = 30
    metrics_retention_days: int = 30
    metrics_enabled: bool = True
    public_ip_lookup_url: str = "https://api.ipify.org"
    public_ip_lookup_timeout_seconds: float = 5.0
    help_guides_dir: Path | None = None
    # When true (behind a trusted reverse proxy), use X-Forwarded-For / X-Real-IP.
    trust_proxy_headers: bool = False

    def resolved_database_url(self) -> str:
        """Return the SQLite URL, creating the app-data directory if needed."""

        if self.database_url:
            return self.database_url
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        db_path = (self.app_data_dir / "mineforge.db").resolve()
        return f"sqlite:///{db_path}"

    def resolved_cookie_secure(self) -> bool:
        """Secure cookies default to on when the public URL is HTTPS."""

        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.public_url.startswith("https://")

    def resolved_docker_host(self) -> str | None:
        """Docker host URL (socket proxy). None uses the SDK default."""

        return self.docker_host


@lru_cache
def get_settings() -> Settings:
    """Return cached settings from the current environment."""

    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache (used by tests)."""

    get_settings.cache_clear()
