"""Live backup while 'online', restore, and forced mid-restore rollback."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import clear_settings_cache
from app.db.session import get_engine
from app.models.backup import Backup
from app.models.operation import Operation, OperationStatus
from app.services import console as console_service
from app.services.backups import set_restore_fail_hook
from app.services.docker_client import (
    ContainerStatsSample,
    ContainerStatus,
    set_docker_client_override,
)
from app.services.logwatch import handle_line
from app.services.operations import reset_locks_for_tests
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests.conftest import login


@dataclass
class FakeDocker:
    running: bool = True
    commands: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

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
            console_service.append_output(
                "worlds/TestWorld/level.dat:9", stream="stdout"
            )
            console_service.append_output(
                "worlds/TestWorld/db/000001.ldb:5", stream="stdout"
            )
        elif cleaned == "save resume":
            console_service.append_output("Changes resumed.", stream="stdout")
        elif cleaned == "stop":
            self.running = False

    def follow_logs(self, since=None):
        if False:  # pragma: no cover
            yield ""


def _seed_world(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "server.properties").write_text(
        "server-name=TestServer\nlevel-name=TestWorld\ngamemode=survival\n",
        encoding="utf-8",
    )
    world = data_dir / "worlds" / "TestWorld"
    (world / "db").mkdir(parents=True)
    (world / "level.dat").write_bytes(b"level-v1")
    (world / "db" / "000001.ldb").write_bytes(b"db-v1")


def _wait_op(client: TestClient, op_id: int, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/operations/{op_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in {"succeeded", "failed", "rolled_back"}:
            return body
        time.sleep(0.2)
    raise AssertionError(f"operation {op_id} did not finish")


def test_live_backup_with_player_online_and_restore(
    client: TestClient, admin_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_world(data)
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    clear_settings_cache()
    reset_locks_for_tests()

    fake = FakeDocker(running=True)
    set_docker_client_override(fake)
    handle_line("Player connected: player_one, xuid: 2535400000000001")

    me = login(client, "admin_one", "admin-password-12")
    csrf = me["csrf_token"]

    created = client.post("/api/backups", headers={"X-CSRF-Token": csrf})
    assert created.status_code == 200, created.text
    op_id = created.json()["operation"]["id"]
    finished = _wait_op(client, op_id)
    assert finished["status"] == "succeeded", finished["log"]
    assert "save hold" in " ".join(fake.commands)

    listing = client.get("/api/backups")
    assert listing.status_code == 200
    backups = listing.json()["backups"]
    assert len(backups) >= 1
    assert backups[0]["verified"] is True
    assert backups[0]["world_folder"] == "TestWorld"
    backup_id = backups[0]["id"]

    # Mutate world so restore is observable
    world = data / "worlds" / "TestWorld"
    (world / "level.dat").write_bytes(b"level-DIRTY")

    restored = client.post(
        f"/api/backups/{backup_id}/restore",
        headers={"X-CSRF-Token": csrf},
    )
    assert restored.status_code == 200, restored.text
    restore_op = _wait_op(client, restored.json()["operation"]["id"], timeout=30)
    assert restore_op["status"] == "succeeded", restore_op["log"]
    assert (world / "level.dat").read_bytes() == b"level-v1"
    assert fake.running is True


def test_restore_forced_failure_rolls_back(
    client: TestClient, admin_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_world(data)
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    clear_settings_cache()
    reset_locks_for_tests()
    set_restore_fail_hook(None)

    fake = FakeDocker(running=True)
    set_docker_client_override(fake)

    me = login(client, "admin_one", "admin-password-12")
    csrf = me["csrf_token"]

    # Cold-ish path still works with running fake
    created = client.post("/api/backups", headers={"X-CSRF-Token": csrf})
    op = _wait_op(client, created.json()["operation"]["id"])
    assert op["status"] == "succeeded", op["log"]
    backup_id = client.get("/api/backups").json()["backups"][0]["id"]

    world = data / "worlds" / "TestWorld"
    (world / "level.dat").write_bytes(b"pre-restore-state")

    def boom() -> None:
        raise RuntimeError("forced mid-restore failure")

    set_restore_fail_hook(boom)
    try:
        restored = client.post(
            f"/api/backups/{backup_id}/restore",
            headers={"X-CSRF-Token": csrf},
        )
        assert restored.status_code == 200
        result = _wait_op(client, restored.json()["operation"]["id"], timeout=30)
        assert result["status"] == "rolled_back", result
        assert result["rollback_performed"] is True
        # World should be back to pre-restore-state (the live world before swap)
        assert (world / "level.dat").read_bytes() == b"pre-restore-state"
        assert fake.running is True
    finally:
        set_restore_fail_hook(None)

    with Session(get_engine()) as session:
        ops = list(session.exec(select(Operation)).all())
        assert any(o.status == OperationStatus.ROLLED_BACK for o in ops)
        assert session.exec(select(Backup)).first() is not None


def test_player_can_create_but_not_restore(
    client: TestClient, admin_user, player_user, app_data_dir: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_world(data)
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    clear_settings_cache()
    reset_locks_for_tests()
    set_docker_client_override(FakeDocker(running=False))

    # Admin creates a backup first
    admin = login(client, "admin_one", "admin-password-12")
    created = client.post("/api/backups", headers={"X-CSRF-Token": admin["csrf_token"]})
    assert _wait_op(client, created.json()["operation"]["id"])["status"] == "succeeded"
    backup_id = client.get("/api/backups").json()["backups"][0]["id"]
    client.post("/api/auth/logout", headers={"X-CSRF-Token": admin["csrf_token"]})

    player = login(client, "player_one", "player-password-12")
    csrf = player["csrf_token"]
    # Player may create
    p_create = client.post("/api/backups", headers={"X-CSRF-Token": csrf})
    assert p_create.status_code == 200
    assert _wait_op(client, p_create.json()["operation"]["id"])["status"] == "succeeded"

    denied = client.post(
        f"/api/backups/{backup_id}/restore",
        headers={"X-CSRF-Token": csrf},
    )
    assert denied.status_code == 403
