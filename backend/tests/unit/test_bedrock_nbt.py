"""Bedrock little-endian level.dat parsing."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.services.bedrock_nbt import (
    level_dat_insight,
    parse_bedrock_level_dat,
    patch_level_dat_ints,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "level.dat_min"


def test_parse_minimal_level_dat() -> None:
    root = parse_bedrock_level_dat(FIXTURE)
    assert root["LevelName"] == "TestWorld"
    assert root["RandomSeed"] == 123456789
    assert root["GameType"] == 1
    assert root["SpawnX"] == 10
    assert root["SpawnY"] == 64
    assert root["SpawnZ"] == -20
    assert root["MultiplayerGame"] == 1


def test_level_dat_insight_fields() -> None:
    insight = level_dat_insight(FIXTURE)
    assert insight["level_name"] == "TestWorld"
    assert insight["seed"] == "123456789"
    assert insight["spawn"] == {"x": 10, "y": 64, "z": -20}
    assert insight["multiplayer"] is True


def test_patch_level_dat_ints_updates_gametype(tmp_path: Path) -> None:
    target = tmp_path / "level.dat"
    shutil.copy(FIXTURE, target)
    assert parse_bedrock_level_dat(target)["GameType"] == 1

    patched = patch_level_dat_ints(target, {"GameType": 2}, uid=0, gid=0)
    assert patched == ["GameType"]
    again = parse_bedrock_level_dat(target)
    assert again["GameType"] == 2
    assert again["LevelName"] == "TestWorld"
    assert again["RandomSeed"] == 123456789
