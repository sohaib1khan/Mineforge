"""Add-on upload flags, embedded merge, and test-mode auto-revert."""

from __future__ import annotations

import json
import time
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import clear_settings_cache, get_settings
from app.services import addons as addon_service
from app.services import console as console_service
from app.services.docker_client import (
    ContainerStatsSample,
    ContainerStatus,
    set_docker_client_override,
)
from app.services.operations import reset_locks_for_tests
from fastapi.testclient import TestClient

from tests.conftest import login

RP_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
BP_UUID = "11111111-2222-3333-4444-555555555555"
EMBED_UUID = "99999999-8888-7777-6666-555555555555"


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


def _manifest(
    *, name: str, pack_uuid: str, module_type: str, version: list[int] | None = None
) -> dict:
    return {
        "format_version": 2,
        "header": {
            "name": name,
            "description": "test",
            "uuid": pack_uuid,
            "version": version or [1, 0, 0],
            "min_engine_version": [1, 20, 0],
        },
        "modules": [
            {
                "type": module_type,
                "uuid": "00000000-0000-0000-0000-000000000001",
                "version": version or [1, 0, 0],
            }
        ],
    }


def _write_pack_zip(path: Path, *, name: str, pack_uuid: str, module_type: str) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                _manifest(name=name, pack_uuid=pack_uuid, module_type=module_type)
            ),
        )
        zf.writestr("pack_icon.png", b"\x89PNG\r\n")


def _seed_world(data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    (data / "server.properties").write_text(
        "level-name=TestWorld\ngamemode=survival\n", encoding="utf-8"
    )
    world = data / "worlds" / "TestWorld"
    (world / "db").mkdir(parents=True)
    (world / "level.dat").write_bytes(b"level-v1!")
    (world / "db" / "000001.ldb").write_bytes(b"db-v1")
    # Embedded behavior pack
    embed = world / "behavior_packs" / "EmbeddedBP"
    embed.mkdir(parents=True)
    (embed / "manifest.json").write_text(
        json.dumps(
            _manifest(name="EmbeddedBP", pack_uuid=EMBED_UUID, module_type="data")
        ),
        encoding="utf-8",
    )


def _wait_op(client: TestClient, op_id: int, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/operations/{op_id}").json()
        if body["status"] in {"succeeded", "failed", "rolled_back"}:
            return body
        time.sleep(0.2)
    raise AssertionError("operation did not finish")


def test_rp_only_upload_shows_missing_pair_warning(
    client: TestClient, admin_user, app_data_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_world(data)
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    clear_settings_cache()
    reset_locks_for_tests()
    set_docker_client_override(FakeDocker(running=False))

    pack = tmp_path / "only_rp.mcpack"
    _write_pack_zip(
        pack, name="PrettyTextures", pack_uuid=RP_UUID, module_type="resources"
    )

    me = login(client, "admin_one", "admin-password-12")
    with pack.open("rb") as handle:
        resp = client.post(
            "/api/addons/upload",
            headers={"X-CSRF-Token": me["csrf_token"]},
            files={"file": ("only_rp.mcpack", handle, "application/zip")},
        )
    assert resp.status_code == 200, resp.text
    addons = resp.json()["addons"]
    assert len(addons) == 1
    assert addons[0]["kind"] == "resource"
    assert addons[0]["missing_pair"] is True
    assert "missing_pair" in addons[0]["flags"]


def test_apply_preserves_embedded_packs_and_test_auto_reverts(
    client: TestClient, admin_user, app_data_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    data = app_data_dir.parent / "data"
    _seed_world(data)
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    clear_settings_cache()
    reset_locks_for_tests()
    addon_service.reset_pending_tests_for_tests()
    set_docker_client_override(FakeDocker(running=True))

    pack = tmp_path / "lib_bp.mcpack"
    _write_pack_zip(pack, name="LibraryBP", pack_uuid=BP_UUID, module_type="data")

    me = login(client, "admin_one", "admin-password-12")
    csrf = me["csrf_token"]
    with pack.open("rb") as handle:
        uploaded = client.post(
            "/api/addons/upload",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("lib_bp.mcpack", handle, "application/zip")},
        )
    assert uploaded.status_code == 200, uploaded.text
    addon_id = uploaded.json()["addons"][0]["id"]

    worlds = client.get("/api/worlds").json()["worlds"]
    world = next(w for w in worlds if w["folder_name"] == "TestWorld")

    profile = client.put(
        f"/api/addons/worlds/{world['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"entries": [{"addon_id": addon_id, "enabled": True, "load_order": 0}]},
    )
    assert profile.status_code == 200, profile.text

    # Snapshot original pack JSON (none) then apply in test mode
    world_dir = data / "worlds" / "TestWorld"
    bp_json = world_dir / "world_behavior_packs.json"
    assert not bp_json.exists() or EMBED_UUID not in bp_json.read_text(encoding="utf-8")

    applied = client.post(
        f"/api/addons/worlds/{world['id']}/apply",
        headers={"X-CSRF-Token": csrf},
        json={"test_mode": True},
    )
    assert applied.status_code == 200, applied.text
    result = _wait_op(client, applied.json()["operation"]["id"])
    assert result["status"] == "succeeded", result["log"]

    written = json.loads(bp_json.read_text(encoding="utf-8"))
    ids = {entry["pack_id"] for entry in written}
    assert EMBED_UUID in ids, "embedded pack must be preserved"
    assert BP_UUID in ids, "library pack must be present"

    # Force short auto-revert instead of waiting 10 minutes
    settings = get_settings()
    snapshot_bp = "[]\n"
    snapshot_rp = "[]\n"
    addon_service._schedule_test_revert(  # noqa: SLF001
        settings,
        operation_id=applied.json()["operation"]["id"],
        world_id=world["id"],
        world_folder="TestWorld",
        snapshot_bp=snapshot_bp,
        snapshot_rp=snapshot_rp,
        expires_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        if bp_json.read_text(encoding="utf-8").strip() in {"[]", ""}:
            break
        time.sleep(0.2)
    assert json.loads(bp_json.read_text(encoding="utf-8")) == []
    assert addon_service.list_pending_tests() == []
