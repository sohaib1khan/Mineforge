"""Unit tests for Docker stats parsing and metrics aggregation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.session import get_engine
from app.models.player_session import PlayerSession
from app.services import metrics as metrics_service
from app.services.docker_client import (
    ContainerStatsSample,
    parse_docker_stats,
    set_docker_client_override,
)
from sqlmodel import Session


def test_parse_docker_stats_cpu_and_net() -> None:
    raw = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 2000, "percpu_usage": [1000, 1000]},
            "system_cpu_usage": 10_000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 1000},
            "system_cpu_usage": 5000,
        },
        "memory_stats": {"usage": 1200, "limit": 4096, "stats": {"cache": 200}},
        "networks": {
            "eth0": {"rx_bytes": 10, "tx_bytes": 20},
            "eth1": {"rx_bytes": 5, "tx_bytes": 7},
        },
    }
    sample = parse_docker_stats(raw)
    assert sample.mem_bytes == 1000
    assert sample.mem_limit_bytes == 4096
    assert sample.net_rx_bytes == 15
    assert sample.net_tx_bytes == 27
    assert sample.cpu_pct > 0


def test_sample_and_store_and_playtime(admin_user) -> None:
    class FakeDocker:
        def sample_stats(self) -> ContainerStatsSample:
            return ContainerStatsSample(
                cpu_pct=12.5,
                mem_bytes=100,
                mem_limit_bytes=1000,
                net_rx_bytes=1,
                net_tx_bytes=2,
                running=True,
            )

        def status(self):  # pragma: no cover - unused
            raise NotImplementedError

    set_docker_client_override(FakeDocker())  # type: ignore[arg-type]
    try:
        with Session(get_engine()) as session:
            now = datetime.now(UTC)
            session.add(
                PlayerSession(
                    gamertag="player_one",
                    xuid="2535400000000001",
                    joined_at=now - timedelta(hours=2),
                    left_at=now - timedelta(hours=1),
                )
            )
            session.add(
                PlayerSession(
                    gamertag="player_one",
                    joined_at=now - timedelta(minutes=30),
                    left_at=None,
                )
            )
            session.commit()

            row = metrics_service.sample_and_store(session, get_settings())
            assert row is not None
            assert row.cpu_pct == 12.5
            assert row.players_online == 1

            board = metrics_service.playtime_leaderboard(session, days=1)
            assert board
            assert board[0]["gamertag"] == "player_one"
            assert board[0]["seconds"] > 0

            overview_samples = metrics_service.list_samples(session, hours=1)
            assert len(overview_samples) >= 1

            removed = metrics_service.apply_metrics_retention(session, get_settings())
            assert removed == 0
    finally:
        set_docker_client_override(None)


def test_metrics_overview_endpoint(client, admin_user) -> None:
    from tests.conftest import login

    class FakeDocker:
        def sample_stats(self) -> ContainerStatsSample:
            return ContainerStatsSample(
                cpu_pct=3.0,
                mem_bytes=50,
                mem_limit_bytes=500,
                net_rx_bytes=0,
                net_tx_bytes=0,
                running=True,
            )

        def status(self):  # pragma: no cover
            raise NotImplementedError

    set_docker_client_override(FakeDocker())  # type: ignore[arg-type]
    try:
        with Session(get_engine()) as session:
            metrics_service.sample_and_store(session, get_settings())
        login(client, "admin_one", "admin-password-12")
        res = client.get("/api/metrics/overview")
        assert res.status_code == 200
        body = res.json()
        assert "samples" in body
        assert body["sample_interval_seconds"] >= 15
        dash = client.get("/api/metrics/dashboard")
        assert dash.status_code == 200
        assert dash.json()["latest"] is not None
    finally:
        set_docker_client_override(None)
