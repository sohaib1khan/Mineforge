"""Extra unit coverage for server controls, metrics retention, network edges."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_engine
from app.models.metric_sample import MetricSample
from app.services import metrics as metrics_service
from app.services import network as network_service
from app.services import server as server_service
from app.services.docker_client import (
    ContainerRuntimeSnapshot,
    ContainerStatsSample,
    ContainerStatus,
    ContainerVersionInfo,
    set_docker_client_override,
)
from sqlmodel import Session


class _FakeDocker:
    running = True

    def status(self) -> ContainerStatus:
        return ContainerStatus(
            name="bedrock",
            exists=True,
            running=self.running,
            status="running" if self.running else "exited",
            started_at=datetime.now(UTC),
            image="itzg/minecraft-bedrock-server:test",
            exit_code=0,
        )

    def sample_stats(self) -> ContainerStatsSample:
        return ContainerStatsSample(1.0, 10, 100, 1, 2, self.running)

    def runtime_snapshot(self) -> ContainerRuntimeSnapshot:
        return ContainerRuntimeSnapshot(
            name="bedrock",
            exists=True,
            running=self.running,
            status="running" if self.running else "exited",
            image="itzg/minecraft-bedrock-server:test",
            started_at=datetime.now(UTC),
            exit_code=0,
            health="healthy" if self.running else None,
            safe_env={"VERSION": "1.21.0"},
            stats=self.sample_stats() if self.running else None,
        )

    def version_info(self) -> ContainerVersionInfo:
        return ContainerVersionInfo("img", "1.21.0", True, "ok")

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


def test_server_start_stop_restart(admin_user, app_data_dir: Path) -> None:
    fake = _FakeDocker()
    set_docker_client_override(fake)
    try:
        with Session(get_engine()) as session:
            settings = get_settings()
            server_service.stop_server(
                session, settings, user_id=admin_user.id, ip="127.0.0.1"  # type: ignore[arg-type]
            )
            assert fake.running is False
            server_service.start_server(
                session, settings, user_id=admin_user.id, ip="127.0.0.1"  # type: ignore[arg-type]
            )
            assert fake.running is True
            server_service.restart_server(
                session, settings, user_id=admin_user.id, ip="127.0.0.1"  # type: ignore[arg-type]
            )
            assert fake.running is True
            status = server_service.get_status(session, settings)
            assert status["container"]["exists"] is True
            assert status["resources"] is not None
            assert status["resources"]["cpu_pct"] == 1.0
            assert status["safe_env"]["VERSION"] == "1.21.0"
    finally:
        set_docker_client_override(None)


def test_server_status_warns_on_level_name_env_and_oom(
    admin_user, app_data_dir: Path
) -> None:
    class _WarnDocker(_FakeDocker):
        def runtime_snapshot(self) -> ContainerRuntimeSnapshot:
            return ContainerRuntimeSnapshot(
                name="bedrock",
                exists=True,
                running=True,
                status="running",
                image="itzg/minecraft-bedrock-server:test",
                started_at=datetime.now(UTC),
                exit_code=0,
                oom_killed=True,
                error="engine error",
                health="unhealthy",
                level_name_env="OldWorld",
                safe_env={"LEVEL_NAME": "OldWorld", "VERSION": "1.21.0"},
                stats=self.sample_stats(),
            )

    data = app_data_dir.parent / "data"
    data.mkdir(exist_ok=True)
    (data / "server.properties").write_text(
        "level-name=TestWorld\ngamemode=survival\n", encoding="utf-8"
    )
    fake = _WarnDocker()
    set_docker_client_override(fake)
    try:
        with Session(get_engine()) as session:
            status = server_service.get_status(session, get_settings())
            assert status["container"]["oom_killed"] is True
            assert status["container"]["health"] == "unhealthy"
            joined = " ".join(status["warnings"])
            assert "OOM" in joined
            assert "LEVEL_NAME" in joined
            assert "unhealthy" in joined.lower()
            assert "engine error" in joined
    finally:
        set_docker_client_override(None)


def test_metrics_retention_removes_old_rows(admin_user) -> None:
    settings = get_settings()
    with Session(get_engine()) as session:
        old = MetricSample(
            ts=datetime.now(UTC) - timedelta(days=settings.metrics_retention_days + 5),
            cpu_pct=1.0,
            mem_bytes=1,
            mem_limit_bytes=2,
            net_rx_bytes=0,
            net_tx_bytes=0,
            players_online=0,
        )
        session.add(old)
        session.commit()
        removed = metrics_service.apply_metrics_retention(session, settings)
        assert removed >= 1


def test_network_rejects_bad_ip() -> None:
    with pytest.raises(AppError):
        network_service.build_udp_ports("999.0.0.1")
    with pytest.raises(AppError):
        network_service.build_udp_ports("203.0.113.10", udp_range="bad")
