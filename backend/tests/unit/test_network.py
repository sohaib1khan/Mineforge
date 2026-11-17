"""Unit tests for public IP / server-udp-ports helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.errors import AppError
from app.services import network as network_service
from app.services.docker_client import (
    ContainerStatsSample,
    ContainerStatus,
    ContainerVersionInfo,
    set_docker_client_override,
)

from tests.conftest import login


class _FakeDocker:
    running = True

    def status(self) -> ContainerStatus:
        from datetime import UTC, datetime

        return ContainerStatus(
            name="bedrock",
            exists=True,
            running=self.running,
            status="running",
            started_at=datetime.now(UTC),
            image="itzg/minecraft-bedrock-server:test",
            exit_code=0,
        )

    def sample_stats(self) -> ContainerStatsSample:
        return ContainerStatsSample(0.0, 0, 0, 0, 0, True)

    def version_info(self) -> ContainerVersionInfo:
        return ContainerVersionInfo(
            image="itzg/minecraft-bedrock-server:test",
            version_env="1.21.50",
            pinned=True,
            guidance="Pinned.",
        )

    def start(self) -> None:
        self.running = True

    def stop(self, timeout: int = 30) -> None:
        self.running = False

    def restart(self, timeout: int = 30) -> None:
        self.running = True

    def send_command(self, command: str) -> None:
        return None

    def follow_logs(self, since=None):
        if False:  # pragma: no cover
            yield ""


def test_build_and_parse_udp_ports() -> None:
    value = network_service.build_udp_ports("203.0.113.10")
    assert value == "203.0.113.10:19140-19155:19140-19155"
    assert network_service.parse_advertised_ip(value) == "203.0.113.10"
    assert (
        network_service.parse_advertised_ip("<public_ip>:19140-19155:19140-19155")
        is None
    )
    with pytest.raises(AppError):
        network_service.validate_ipv4("not-an-ip")


def test_apply_public_ip_writes_properties(
    client, admin_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    data.mkdir(exist_ok=True)
    props = data / "server.properties"
    props.write_text(
        "server-name=Test\nlevel-name=TestWorld\nserver-port=19132\n"
        "server-udp-ports=198.51.100.1:19140-19155:19140-19155\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    from app.core.config import clear_settings_cache

    clear_settings_cache()

    network_service.set_ip_lookup_override(lambda _s: "203.0.113.10")
    set_docker_client_override(_FakeDocker())
    try:
        me = login(client, "admin_one", "admin-password-12")
        csrf = me["csrf_token"]
        detected = client.post(
            "/api/server/network/detect",
            headers={"X-CSRF-Token": csrf},
        )
        assert detected.status_code == 200, detected.text
        body = detected.json()
        assert body["detected_public_ip"] == "203.0.113.10"
        assert body["proposed_server_udp_ports"].startswith("203.0.113.10:")

        applied = client.post(
            "/api/server/network/apply",
            headers={"X-CSRF-Token": csrf},
            json={"restart": True},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["advertised_public_ip"] == "203.0.113.10"
        assert applied.json()["restarted"] is True

        text = props.read_text(encoding="utf-8")
        assert "203.0.113.10:19140-19155:19140-19155" in text

        version = client.get("/api/server/version")
        assert version.status_code == 200
        assert version.json()["pinned"] is True
    finally:
        network_service.set_ip_lookup_override(None)
        set_docker_client_override(None)
        clear_settings_cache()


def test_help_guides_list_and_get(client, admin_user) -> None:
    login(client, "admin_one", "admin-password-12")
    listed = client.get("/api/help")
    assert listed.status_code == 200
    guides = listed.json()["guides"]
    assert len(guides) >= 5
    slug = guides[0]["slug"]
    one = client.get(f"/api/help/{slug}")
    assert one.status_code == 200
    assert "markdown" in one.json()
    assert one.json()["title"]
