"""World switch A→B success and broken-B rollback."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import clear_settings_cache, get_settings
from app.services import console as console_service
from app.services.docker_client import (
    ContainerStatsSample,
    ContainerStatus,
    set_docker_client_override,
)
from app.services.operations import reset_locks_for_tests
from app.services.server_props import read_properties
from app.services.switch import reset_consents_for_tests, set_switch_fail_hook
from fastapi.testclient import TestClient

from tests.conftest import login


@dataclass
class FakeDocker:
    running: bool = True
    commands: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    fail_start: bool = False

    def status(self) -> ContainerStatus:
        return ContainerStatus(
            name="bedrock",
            exists=True,
            running=self.running,
            status="running" if self.running else "exited",
            started_at=self.started_at if self.running else None,
            image="itzg/minecraft-bedrock-server:test",
            exit_code=0,
        )

    def sample_stats(self) -> ContainerStatsSample:
        return ContainerStatsSample(
            cpu_pct=0.0,
            mem_bytes=0,
            mem_limit_bytes=0,
            net_rx_bytes=0,
            net_tx_bytes=0,
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
        if self.fail_start:
            raise RuntimeError("simulated start failure")
        self.running = True
        self.started_at = datetime.now(UTC)
        console_service.append_output("Server started.", stream="stdout")

    def stop(self, timeout: int = 30) -> None:
        self.running = False

    def restart(self, timeout: int = 30) -> None:
        self.start()

    def send_command(self, command: str) -> None:
        self.commands.append(command)
        cleaned = command.strip().lower()
        if cleaned == "save hold":
            console_service.append_output("Saving...", stream="stdout")
        elif cleaned == "save query":
            console_service.append_output(
                "Data saved. Files are now ready to be copied.", stream="stdout"
            )
            # sizes match seeded files
            console_service.append_output("worlds/WorldA/level.dat:8", stream="stdout")
            console_service.append_output(
                "worlds/WorldA/db/000001.ldb:5", stream="stdout"
            )
        elif cleaned == "save resume":
            console_service.append_output("Changes resumed.", stream="stdout")
        elif cleaned == "stop":
            self.running = False

    def follow_logs(self, since=None):
        if False:  # pragma: no cover
            yield ""


def _seed_world(data_dir: Path, name: str, payload: bytes) -> None:
    world = data_dir / "worlds" / name
    (world / "db").mkdir(parents=True, exist_ok=True)
    (world / "level.dat").write_bytes(payload)
    (world / "db" / "000001.ldb").write_bytes(b"db-v1")


def _seed_props(data_dir: Path, level: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "server.properties").write_text(
        f"server-name=TestServer\nlevel-name={level}\ngamemode=survival\ndifficulty=easy\n",
        encoding="utf-8",
    )


def _wait_op(client: TestClient, op_id: int, timeout: float = 45.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/operations/{op_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in {"succeeded", "failed", "rolled_back"}:
            return body
        time.sleep(0.2)
    raise AssertionError(f"operation {op_id} did not finish")


def test_switch_a_to_b_succeeds(
    client: TestClient, admin_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_props(data, "WorldA")
    _seed_world(data, "WorldA", b"level-A1")
    _seed_world(data, "WorldB", b"level-B1")
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_SWITCH_COUNTDOWN_SECONDS", "0")
    clear_settings_cache()
    reset_locks_for_tests()
    reset_consents_for_tests()
    set_switch_fail_hook(None)

    fake = FakeDocker(running=True)
    set_docker_client_override(fake)

    me = login(client, "admin_one", "admin-password-12")
    csrf = me["csrf_token"]

    worlds = client.get("/api/worlds").json()["worlds"]
    by_folder = {w["folder_name"]: w for w in worlds}
    assert "WorldA" in by_folder and "WorldB" in by_folder
    assert by_folder["WorldA"]["is_active"] is True

    switched = client.post(
        f"/api/worlds/{by_folder['WorldB']['id']}/switch",
        headers={"X-CSRF-Token": csrf},
        json={"skip_countdown": True},
    )
    assert switched.status_code == 200, switched.text
    result = _wait_op(client, switched.json()["operation"]["id"])
    assert result["status"] == "succeeded", result["log"]

    props = read_properties(get_settings())
    assert props["level-name"] == "WorldB"
    refreshed = client.get("/api/worlds").json()["worlds"]
    active = [w for w in refreshed if w["is_active"]]
    assert len(active) == 1
    assert active[0]["folder_name"] == "WorldB"


def test_switch_broken_b_rolls_back_to_a(
    client: TestClient, admin_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_props(data, "WorldA")
    _seed_world(data, "WorldA", b"level-A1")
    _seed_world(data, "WorldB", b"level-B1")
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_SWITCH_COUNTDOWN_SECONDS", "0")
    clear_settings_cache()
    reset_locks_for_tests()
    reset_consents_for_tests()

    fake = FakeDocker(running=True)
    set_docker_client_override(fake)

    def boom() -> None:
        raise RuntimeError("deliberately broken world B")

    set_switch_fail_hook(boom)
    try:
        me = login(client, "admin_one", "admin-password-12")
        csrf = me["csrf_token"]
        worlds = client.get("/api/worlds").json()["worlds"]
        world_b = next(w for w in worlds if w["folder_name"] == "WorldB")

        switched = client.post(
            f"/api/worlds/{world_b['id']}/switch",
            headers={"X-CSRF-Token": csrf},
            json={"skip_countdown": True, "force": True},
        )
        assert switched.status_code == 200
        result = _wait_op(client, switched.json()["operation"]["id"])
        assert result["status"] == "rolled_back", result
        assert result["rollback_performed"] is True
        assert "broken world B" in result["log"]

        props = read_properties(get_settings())
        assert props["level-name"] == "WorldA"
        refreshed = client.get("/api/worlds").json()["worlds"]
        active = next(w for w in refreshed if w["is_active"])
        assert active["folder_name"] == "WorldA"
        assert fake.running is True
    finally:
        set_switch_fail_hook(None)


def test_clone_and_player_blocked_without_consent(
    client: TestClient, admin_user, player_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_props(data, "WorldA")
    _seed_world(data, "WorldA", b"level-A1")
    _seed_world(data, "WorldB", b"level-B1")
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_SWITCH_COUNTDOWN_SECONDS", "0")
    clear_settings_cache()
    reset_locks_for_tests()
    reset_consents_for_tests()
    set_docker_client_override(FakeDocker(running=False))

    admin = login(client, "admin_one", "admin-password-12")
    worlds = client.get("/api/worlds").json()["worlds"]
    world_a = next(w for w in worlds if w["folder_name"] == "WorldA")
    cloned = client.post(
        f"/api/worlds/{world_a['id']}/clone",
        headers={"X-CSRF-Token": admin["csrf_token"]},
        json={"folder_name": "WorldA_copy", "display_name": "Copy"},
    )
    assert cloned.status_code == 200
    assert cloned.json()["folder_name"] == "WorldA_copy"
    client.post("/api/auth/logout", headers={"X-CSRF-Token": admin["csrf_token"]})

    # Simulate a player online via DB through logwatch isn't needed —
    # force online by inserting via handle_line after player login path.
    from app.services.logwatch import handle_line

    handle_line("Player connected: player_one, xuid: 2535400000000001")

    player = login(client, "player_one", "player-password-12")
    world_b = next(
        w
        for w in client.get("/api/worlds").json()["worlds"]
        if w["folder_name"] == "WorldB"
    )
    blocked = client.post(
        f"/api/worlds/{world_b['id']}/switch",
        headers={"X-CSRF-Token": player["csrf_token"]},
        json={},
    )
    assert blocked.status_code == 409
