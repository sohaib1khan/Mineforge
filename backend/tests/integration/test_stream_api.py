"""Stream API auth, settings, and internal MediaMTX callback."""

from __future__ import annotations

from app.core.config import clear_settings_cache
from app.services.stream import reset_stream_cache_for_tests
from fastapi.testclient import TestClient

from tests.conftest import login


def test_stream_requires_login(client: TestClient) -> None:
    assert client.get("/api/stream/status").status_code == 401
    assert client.get("/api/stream/hls/live/index.m3u8").status_code == 401


def test_stream_status_and_key_rotate(
    client: TestClient, admin_user, monkeypatch
) -> None:
    monkeypatch.setenv(
        "MINEFORGE_INTERNAL_STREAM_SECRET", "test-internal-stream-secret"
    )
    clear_settings_cache()
    reset_stream_cache_for_tests()

    me = login(client, "admin_one", "admin-password-12")
    csrf = me["csrf_token"]

    status = client.get("/api/stream/status")
    assert status.status_code == 200
    body = status.json()
    assert body["live"] is False
    assert "title" in body

    settings = client.get("/api/stream/settings")
    assert settings.status_code == 200
    assert settings.json()["key_configured"] is False

    rotated = client.post(
        "/api/stream/key/rotate",
        headers={"X-CSRF-Token": csrf},
    )
    assert rotated.status_code == 200
    payload = rotated.json()
    key = payload["stream_key"]
    assert len(key) >= 32
    assert payload["obs_stream_key"].startswith("stream?user=publish&pass=")
    assert key in payload["obs_stream_key"]
    assert payload["rtmp_server"].endswith(":1935/live")
    assert "pass=" in payload["rtmp_url_example"]

    # Internal auth: wrong token
    denied = client.post(
        "/internal/stream/auth?token=wrong",
        json={
            "user": "publish",
            "password": key,
            "action": "publish",
            "path": "live",
            "protocol": "rtmp",
            "ip": "10.0.0.5",
        },
    )
    assert denied.status_code == 403

    # Internal auth: good token + key (TestClient IP is often "testclient" —
    # private IP check uses body.ip for publish audit; caller IP may fail.
    # Force trust: monkeypatch private check by using 127.0.0.1 via headers
    # when trust_proxy is on, or call service path. For HTTP, client.host in
    # Starlette TestClient is "testclient" which is not a private IP.
    monkeypatch.setenv("MINEFORGE_TRUST_PROXY_HEADERS", "true")
    clear_settings_cache()
    ok = client.post(
        "/internal/stream/auth?token=test-internal-stream-secret",
        headers={"X-Real-IP": "172.18.0.4"},
        json={
            "user": "publish",
            "password": key,
            "action": "publish",
            "path": "live",
            "protocol": "rtmp",
            "ip": "10.0.0.5",
        },
    )
    assert ok.status_code == 200, ok.text

    bad_key = client.post(
        "/internal/stream/auth?token=test-internal-stream-secret",
        headers={"X-Real-IP": "172.18.0.4"},
        json={
            "user": "publish",
            "password": "not-the-key",
            "action": "publish",
            "path": "live",
            "protocol": "rtmp",
            "ip": "10.0.0.5",
        },
    )
    assert bad_key.status_code == 401


def test_hls_path_rejection_when_authed(
    client: TestClient, admin_user, monkeypatch
) -> None:
    monkeypatch.setenv(
        "MINEFORGE_INTERNAL_STREAM_SECRET", "test-internal-stream-secret"
    )
    clear_settings_cache()
    login(client, "admin_one", "admin-password-12")
    resp = client.get("/api/stream/hls/../../etc/passwd")
    assert resp.status_code in {403, 404}
    resp2 = client.get("/api/stream/hls/other/index.m3u8")
    assert resp2.status_code == 403


def test_player_can_view_status_not_settings(
    client: TestClient, admin_user, player_user
) -> None:
    login(client, "player_one", "player-password-12")
    assert client.get("/api/stream/status").status_code == 200
    assert client.get("/api/stream/settings").status_code == 403
