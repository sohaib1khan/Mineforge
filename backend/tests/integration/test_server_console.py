"""Server status, console list, and join/leave recording."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.db.session import get_engine
from app.models.player_session import PlayerSession
from app.services.docker_client import (
    ContainerStatsSample,
    ContainerStatus,
    set_docker_client_override,
)
from app.services.logwatch import handle_line
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests.conftest import login


@dataclass
class FakeDocker:
    running: bool = True
    commands: list[str] = field(default_factory=list)

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
        return ContainerStatsSample(
            cpu_pct=1.5,
            mem_bytes=64 * 1024 * 1024,
            mem_limit_bytes=512 * 1024 * 1024,
            net_rx_bytes=1000,
            net_tx_bytes=2000,
            running=self.running,
        )

    def version_info(self):
        from app.services.docker_client import ContainerVersionInfo

        return ContainerVersionInfo(
            image="itzg/minecraft-bedrock-server:test",
            version_env="1.21.0",
            pinned=True,
            guidance="Pinned for tests.",
        )

    def start(self) -> None:
        self.running = True

    def stop(self, timeout: int = 30) -> None:
        self.running = False

    def restart(self, timeout: int = 30) -> None:
        self.running = True

    def send_command(self, command: str) -> None:
        self.commands.append(command)

    def follow_logs(self, since=None):
        if False:  # pragma: no cover
            yield ""


def test_joins_leaves_recorded_and_console_list(
    client: TestClient, admin_user, app_data_dir, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    data.mkdir(exist_ok=True)
    (data / "server.properties").write_text(
        "server-name=TestServer\nlevel-name=TestWorld\ngamemode=survival\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    from app.core.config import clear_settings_cache

    clear_settings_cache()

    fake = FakeDocker()
    set_docker_client_override(fake)
    try:
        handle_line("Player connected: player_one, xuid: 2535400000000001")
        with Session(get_engine()) as session:
            online = session.exec(
                select(PlayerSession).where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
            ).all()
            assert len(online) == 1
            assert online[0].gamertag == "player_one"

        payload = login(client, "admin_one", "admin-password-12")
        csrf = payload["csrf_token"]

        status = client.get("/api/server/status")
        assert status.status_code == 200
        body = status.json()
        assert body["player_count"] == 1
        assert body["players_online"][0]["gamertag"] == "player_one"
        assert body["container"]["running"] is True

        sent = client.post(
            "/api/console/command",
            headers={"X-CSRF-Token": csrf},
            json={"command": "list"},
        )
        assert sent.status_code == 200
        assert fake.commands == ["list"]

        history = client.get("/api/console/history")
        assert history.status_code == 200
        texts = " ".join(line["text"] for line in history.json()["lines"])
        assert "player_one" in texts
        assert "1/" in texts or "There are 1" in texts

        handle_line("Player disconnected: player_one, xuid: 2535400000000001")
        status2 = client.get("/api/server/status")
        assert status2.json()["player_count"] == 0
    finally:
        set_docker_client_override(None)
        clear_settings_cache()


def test_player_forbidden_from_console(
    client: TestClient, player_user, admin_user
) -> None:
    set_docker_client_override(FakeDocker())
    try:
        login(client, "player_one", "player-password-12")
        me = client.get("/api/auth/me").json()
        resp = client.post(
            "/api/console/command",
            headers={"X-CSRF-Token": me["csrf_token"]},
            json={"command": "list"},
        )
        assert resp.status_code == 403
    finally:
        set_docker_client_override(None)
