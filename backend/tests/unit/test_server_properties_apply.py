"""Gamemode/difficulty save syncs active world level.dat."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.db.session import get_engine
from app.models.world import World
from app.services import bedrock_nbt
from app.services import server as server_service
from app.services.docker_client import (
    ContainerStatsSample,
    ContainerStatus,
    set_docker_client_override,
)
from sqlmodel import Session, select


@dataclass
class FakeDocker:
    running: bool = True
    stops: int = 0
    starts: int = 0
    commands: list[str] = field(default_factory=list)

    def status(self) -> ContainerStatus:
        return ContainerStatus(
            name="bedrock",
            exists=True,
            running=self.running,
            status="running" if self.running else "exited",
            started_at=datetime.now(UTC) if self.running else None,
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

    def start(self) -> None:
        self.starts += 1
        self.running = True

    def stop(self, timeout: int = 30) -> None:
        self.stops += 1
        self.running = False

    def restart(self, timeout: int = 30) -> None:
        self.stop()
        self.start()

    def send_command(self, command: str) -> None:
        self.commands.append(command)


FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "level.dat_min"


def test_update_properties_patches_gametype_and_restarts(app_data_dir: Path) -> None:
    settings = get_settings()
    data = settings.data_dir
    world = data / "worlds" / "TestWorld"
    world.mkdir(parents=True)
    shutil.copy(FIXTURE, world / "level.dat")
    (data / "server.properties").write_text(
        "server-name=Test\nlevel-name=TestWorld\ngamemode=survival\ndifficulty=easy\n",
        encoding="utf-8",
    )

    with Session(get_engine()) as session:
        session.add(
            World(
                display_name="TestWorld",
                folder_name="TestWorld",
                is_active=True,
                gamemode="survival",
                difficulty="easy",
            )
        )
        session.commit()

    fake = FakeDocker(running=True)
    set_docker_client_override(fake)
    try:
        with Session(get_engine()) as session:
            result = server_service.update_properties(
                session,
                settings,
                updates={"gamemode": "adventure", "difficulty": "peaceful"},
                user_id=1,
                ip=None,
            )
        assert result["values"]["gamemode"] == "adventure"
        assert result["values"]["difficulty"] == "peaceful"
        assert result["values"]["force-gamemode"] == "true"
        assert result["world_synced"] is True
        assert result["restarted"] is True
        assert fake.stops == 1
        assert fake.starts == 1

        root = bedrock_nbt.parse_bedrock_level_dat(world / "level.dat")
        assert root["GameType"] == 2

        with Session(get_engine()) as session:
            row = session.exec(
                select(World).where(World.folder_name == "TestWorld")
            ).one()
            assert row.gamemode == "adventure"
            assert row.difficulty == "peaceful"
    finally:
        set_docker_client_override(None)
