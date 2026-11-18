"""Unit coverage for world reset folder wipe helpers."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.worlds import _recreate_empty_world_folder


def test_recreate_empty_world_folder_wipes_level_dat(app_data_dir: Path) -> None:
    settings = get_settings()
    world = settings.data_dir / "worlds" / "ResetMe"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"old")
    (world / "db").mkdir()
    (world / "db" / "chunk.bin").write_bytes(b"x")

    _recreate_empty_world_folder(
        settings, world, seed="42", gamemode="survival", difficulty="easy"
    )

    assert world.is_dir()
    assert not (world / "level.dat").exists()
    assert (world / "db").is_dir()
    assert (world / ".mineforge-new").is_file()
    text = (world / ".mineforge-new").read_text(encoding="utf-8")
    assert "seed=42" in text
    assert "gamemode=survival" in text
