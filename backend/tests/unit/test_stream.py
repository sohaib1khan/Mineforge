"""Stream key, HLS path validation, and publish auth."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings, clear_settings_cache
from app.core.errors import ForbiddenError
from app.models.user import User, UserRole
from app.services import stream as stream_service
from app.services.stream import reset_stream_cache_for_tests
from sqlmodel import Session


def _settings(tmp_path: Path) -> Settings:
    clear_settings_cache()
    reset_stream_cache_for_tests()
    return Settings(
        data_dir=tmp_path / "data",
        app_data_dir=tmp_path / "app-data",
        secret_key="test-secret-key-not-real",
        public_url="http://localhost:8080",
        internal_stream_secret="test-internal-stream-secret",
        stream_rtmp_host="192.0.2.10",
        mediamtx_hls_url="http://mediamtx:8888",
        mediamtx_api_url="http://mediamtx:9997",
        _env_file=None,
    )


def test_validate_hls_path_allows_live_playlist() -> None:
    assert stream_service.validate_hls_rel_path("live/index.m3u8") == "live/index.m3u8"
    assert stream_service.validate_hls_rel_path("/live/seg.ts") == "live/seg.ts"


def test_validate_hls_path_rejects_traversal_and_other_roots() -> None:
    with pytest.raises(ForbiddenError):
        stream_service.validate_hls_rel_path("live/../secret.m3u8")
    with pytest.raises(ForbiddenError):
        stream_service.validate_hls_rel_path("other/index.m3u8")
    with pytest.raises(ForbiddenError):
        stream_service.validate_hls_rel_path("live/evil.exe")


def test_rotate_key_and_authorize_publish(tmp_path: Path, db_session: Session) -> None:
    settings = _settings(tmp_path)
    admin = User(
        username="stream_admin",
        password_hash="x",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    plaintext, row = stream_service.rotate_key(
        db_session, settings, user=admin, ip="127.0.0.1"
    )
    assert len(plaintext) >= 32
    assert row.key_hash is not None
    assert plaintext not in (row.key_hash or "")

    assert stream_service.authorize_publish(
        db_session,
        settings,
        action="publish",
        path="live",
        password=plaintext,
        token="",
        publisher_ip="10.0.0.2",
        protocol="rtmp",
    )
    assert not stream_service.authorize_publish(
        db_session,
        settings,
        action="publish",
        path="live",
        password="wrong-key-value",
        token="",
        publisher_ip="10.0.0.2",
        protocol="rtmp",
    )

    # Old key dies after rotate
    new_key, _ = stream_service.rotate_key(
        db_session, settings, user=admin, ip="127.0.0.1"
    )
    assert not stream_service.authorize_publish(
        db_session,
        settings,
        action="publish",
        path="live",
        password=plaintext,
        token="",
        publisher_ip="10.0.0.2",
        protocol="rtmp",
    )
    assert stream_service.authorize_publish(
        db_session,
        settings,
        action="publish",
        path="live",
        password=new_key,
        token="",
        publisher_ip="10.0.0.2",
        protocol="rtmp",
    )


def test_authorize_read_live_path(tmp_path: Path, db_session: Session) -> None:
    settings = _settings(tmp_path)
    assert stream_service.authorize_publish(
        db_session,
        settings,
        action="read",
        path="live",
        password="",
        token="",
        publisher_ip="172.18.0.2",
        protocol="hls",
    )


def test_verify_internal_caller(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stream_service.verify_internal_caller(
        settings, client_ip="172.18.0.3", token="test-internal-stream-secret"
    )
    with pytest.raises(ForbiddenError):
        stream_service.verify_internal_caller(
            settings, client_ip="172.18.0.3", token="wrong"
        )
    with pytest.raises(ForbiddenError):
        stream_service.verify_internal_caller(
            settings, client_ip="8.8.8.8", token="test-internal-stream-secret"
        )


def test_rtmp_urls(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert stream_service.rtmp_server_url(settings) == "rtmp://192.0.2.10:1935/live"
    assert stream_service.obs_stream_key_field("abc") == "?user=publish&pass=abc"
    example = stream_service.rtmp_url_with_key(settings, "abc")
    assert example.startswith("rtmp://192.0.2.10:1935/live?")
    assert "user=publish" in example
    assert "pass=abc" in example


def test_rtmp_host_falls_back_to_public_url(tmp_path: Path) -> None:
    clear_settings_cache()
    settings = Settings(
        data_dir=tmp_path / "data",
        app_data_dir=tmp_path / "app-data",
        secret_key="test-secret-key-not-real",
        public_url="https://mineforge.example.com",
        stream_rtmp_host="192.0.2.10",
        internal_stream_secret="test-internal-stream-secret",
        _env_file=None,
    )
    assert settings.resolved_stream_rtmp_host() == "mineforge.example.com"
    assert (
        stream_service.rtmp_server_url(settings)
        == "rtmp://mineforge.example.com:1935/live"
    )
