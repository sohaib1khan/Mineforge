"""Minimal little-endian NBT reader for Bedrock ``level.dat``.

Only implements the tag types needed for world insight (compound, list,
string, numeric). Does not write NBT.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from app.core.errors import AppError

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


class _Reader:
    def __init__(self, data: bytes, offset: int = 0) -> None:
        self.data = data
        self.offset = offset

    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read(self, n: int) -> bytes:
        if self.remaining() < n:
            raise AppError("Truncated NBT data")
        out = self.data[self.offset : self.offset + n]
        self.offset += n
        return out

    def u8(self) -> int:
        return self.read(1)[0]

    def i16(self) -> int:
        return struct.unpack("<h", self.read(2))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.read(4))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.read(8))[0]

    def string(self) -> str:
        length = struct.unpack("<H", self.read(2))[0]
        raw = self.read(length)
        return raw.decode("utf-8", errors="replace")


def _read_payload(reader: _Reader, tag_type: int) -> Any:
    if tag_type == TAG_BYTE:
        return reader.u8()
    if tag_type == TAG_SHORT:
        return reader.i16()
    if tag_type == TAG_INT:
        return reader.i32()
    if tag_type == TAG_LONG:
        return reader.i64()
    if tag_type == TAG_FLOAT:
        return reader.f32()
    if tag_type == TAG_DOUBLE:
        return reader.f64()
    if tag_type == TAG_BYTE_ARRAY:
        count = reader.i32()
        return list(reader.read(max(0, count)))
    if tag_type == TAG_STRING:
        return reader.string()
    if tag_type == TAG_LIST:
        item_type = reader.u8()
        count = reader.i32()
        if count < 0:
            raise AppError("Invalid NBT list length")
        return [_read_payload(reader, item_type) for _ in range(count)]
    if tag_type == TAG_COMPOUND:
        return _read_compound(reader)
    if tag_type == TAG_INT_ARRAY:
        count = reader.i32()
        return [struct.unpack("<i", reader.read(4))[0] for _ in range(max(0, count))]
    if tag_type == TAG_LONG_ARRAY:
        count = reader.i32()
        return [struct.unpack("<q", reader.read(8))[0] for _ in range(max(0, count))]
    raise AppError(f"Unsupported NBT tag type {tag_type}")


def _read_compound(reader: _Reader) -> dict[str, Any]:
    out: dict[str, Any] = {}
    while True:
        tag_type = reader.u8()
        if tag_type == TAG_END:
            return out
        name = reader.string()
        out[name] = _read_payload(reader, tag_type)


def parse_bedrock_level_dat(path: Path) -> dict[str, Any]:
    """Parse a Bedrock ``level.dat`` into a Python dict (root compound).

    Raises:
        AppError: missing file or corrupt NBT.
    """

    if not path.is_file():
        raise AppError("level.dat not found", status_code=404)
    data = path.read_bytes()
    if len(data) < 8:
        raise AppError("level.dat too small")
    # 4-byte storage version + 4-byte length, then little-endian NBT.
    reader = _Reader(data, offset=8)
    tag_type = reader.u8()
    if tag_type != TAG_COMPOUND:
        raise AppError("level.dat root is not a compound")
    _ = reader.string()  # root name (often empty)
    return _read_compound(reader)


def level_dat_insight(path: Path) -> dict[str, Any]:
    """Extract dashboard-friendly fields from ``level.dat``."""

    root = parse_bedrock_level_dat(path)
    experiments = root.get("experiments")
    experiment_flags: list[str] = []
    if isinstance(experiments, dict):
        for key, value in experiments.items():
            if key in {"experiments_ever_used", "saved_with_toggled_experiments"}:
                continue
            if value in (1, True) or value == 1.0:
                experiment_flags.append(str(key))

    def _num(*keys: str) -> int | float | None:
        for key in keys:
            if key in root and isinstance(root[key], int | float):
                return root[key]
        return None

    seed = root.get("RandomSeed")
    return {
        "level_name": str(root.get("LevelName") or "") or None,
        "seed": str(seed) if seed is not None else None,
        "game_type": _num("GameType"),
        "generator": _num("Generator"),
        "spawn": {
            "x": _num("SpawnX"),
            "y": _num("SpawnY"),
            "z": _num("SpawnZ"),
        },
        "time": _num("Time"),
        "current_tick": _num("currentTick"),
        "rain_level": _num("rainLevel"),
        "lightning_level": _num("lightningLevel"),
        "has_been_loaded_in_creative": bool(root.get("hasBeenLoadedInCreative")),
        "bonus_chest": bool(root.get("bonusChestEnabled") or root.get("bonusChest")),
        "start_with_map": bool(root.get("startWithMapEnabled")),
        "experiments": sorted(experiment_flags),
        "multiplayer": bool(root.get("MultiplayerGame")),
        "commands_enabled": bool(root.get("commandsEnabled")),
        "world_start_count": _num("worldStartCount"),
    }
