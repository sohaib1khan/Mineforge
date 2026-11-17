"""Deep read-only insight into the active Bedrock world and its packs.

Scans ``level.dat``, enabled world pack JSON, and pack folders under
``/data`` for items, entities, structures, weapons-like content, etc.
Does not open LevelDB player inventories (fragile / version-specific).
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.core.config import Settings
from app.core.errors import AppError
from app.models.addon import Addon, AddonKind, WorldAddon
from app.models.world import World
from app.services import addons as addons_service
from app.services.archive_safety import dir_size
from app.services.bedrock_nbt import level_dat_insight
from app.services.worlds import world_path

logger = logging.getLogger(__name__)

_CACHE: dict[str, Any] = {"key": None, "at": 0.0, "payload": None}
_CACHE_TTL_SECONDS = 45.0

WEAPON_RE = re.compile(
    r"(gun|weapon|sword|bow|crossbow|rifle|pistol|ammo|bullet|grenade|"
    r"blaster|katana|axe|spear|trident|staff|wand)",
    re.IGNORECASE,
)
STRUCTURE_RE = re.compile(
    r"(structure|house|build|schematic|instant.?struct|village|castle|"
    r"tower|dungeon|temple|ruin)",
    re.IGNORECASE,
)
FURNITURE_RE = re.compile(
    r"(furniture|kitchen|bedroom|sofa|chair|table|decor|appliance|" r"electronics)",
    re.IGNORECASE,
)
VEHICLE_RE = re.compile(
    r"(car|truck|bike|vehicle|plane|heli|boat|lamborghini|tesla|train)",
    re.IGNORECASE,
)
MOB_RE = re.compile(
    r"(mob|companion|npc|ai.?player|animal|creature|pet)",
    re.IGNORECASE,
)
TECH_RE = re.compile(
    r"(tech|machine|factory|pipeline|cable|circuit|computer|automat)",
    re.IGNORECASE,
)

CONTENT_DIRS = (
    "items",
    "entities",
    "blocks",
    "structures",
    "recipes",
    "loot_tables",
    "functions",
    "trading",
    "animations",
    "animation_controllers",
    "particles",
    "sounds",
    "texts",
)


def _cache_get(key: str) -> dict[str, Any] | None:
    if _CACHE["key"] != key:
        return None
    if time.monotonic() - float(_CACHE["at"]) > _CACHE_TTL_SECONDS:
        return None
    payload = _CACHE["payload"]
    return payload if isinstance(payload, dict) else None


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    _CACHE["key"] = key
    _CACHE["at"] = time.monotonic()
    _CACHE["payload"] = payload


def reset_insight_cache_for_tests() -> None:
    """Clear insight cache between tests."""

    _CACHE["key"] = None
    _CACHE["at"] = 0.0
    _CACHE["payload"] = None


def _count_files(root: Path, relative: str) -> int:
    target = root / relative
    if not target.is_dir():
        return 0
    return sum(1 for path in target.rglob("*") if path.is_file())


def _classify_pack(name: str, folder: str) -> str:
    blob = f"{name} {folder}"
    if WEAPON_RE.search(blob):
        return "weapons_combat"
    if STRUCTURE_RE.search(blob):
        return "structures_builds"
    if FURNITURE_RE.search(blob):
        return "furniture_decor"
    if VEHICLE_RE.search(blob):
        return "vehicles"
    if MOB_RE.search(blob):
        return "mobs_ai"
    if TECH_RE.search(blob):
        return "tech_automation"
    return "other"


def _scan_pack_root(
    root: Path, *, name: str, kind: str, pack_uuid: str
) -> dict[str, Any]:
    counts = {key: _count_files(root, key) for key in CONTENT_DIRS}
    structure_files = counts["structures"]
    # Some packs drop .mcstructure under nested folders without structures/
    if structure_files == 0:
        structure_files = sum(
            1 for path in root.rglob("*.mcstructure") if path.is_file()
        )
        counts["structures"] = structure_files

    weaponish = 0
    items_dir = root / "items"
    if items_dir.is_dir():
        for path in items_dir.rglob("*"):
            if path.is_file() and WEAPON_RE.search(str(path.relative_to(root))):
                weaponish += 1

    category = _classify_pack(name, root.name)
    return {
        "name": name,
        "kind": kind,
        "pack_uuid": pack_uuid,
        "folder": root.name,
        "category": category,
        "size_bytes": dir_size(root) if root.is_dir() else 0,
        "counts": counts,
        "weapon_like_items": weaponish,
        "structure_files": structure_files,
    }


def _world_pack_entries(world_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for filename in ("world_behavior_packs.json", "world_resource_packs.json"):
        path = world_dir / filename
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict):
                entries.append(item)
    return entries


def _resolve_pack_dirs(settings: Settings) -> list[Path]:
    roots: list[Path] = []
    for rel in (
        "behavior_packs",
        "resource_packs",
        "development_behavior_packs",
        "development_resource_packs",
    ):
        path = settings.data_dir / rel
        if path.is_dir():
            roots.append(path)
    library = addons_service.packs_library_dir(settings)
    if library.is_dir():
        roots.append(library)
    return roots


def _index_pack_roots(settings: Settings) -> dict[str, Path]:
    """Map pack UUID (lower) → first on-disk pack root with that manifest uuid."""

    index: dict[str, Path] = {}
    for base in _resolve_pack_dirs(settings):
        try:
            children = list(base.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            manifest = child / "manifest.json"
            if not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            uuid = str((data.get("header") or {}).get("uuid") or "").strip().lower()
            if uuid and uuid not in index:
                index[uuid] = child
    return index


def _active_world(session: Session) -> World | None:
    return session.exec(select(World).where(World.is_active.is_(True))).first()  # type: ignore[union-attr]


def build_world_insight(
    session: Session,
    settings: Settings,
    *,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Return deep insight for the active world (cached briefly)."""

    world = _active_world(session)
    if world is None:
        return {
            "available": False,
            "reason": "No active world",
            "world": None,
            "level": None,
            "packs": [],
            "totals": {},
            "categories": {},
        }

    folder = world.folder_name
    wdir = world_path(settings, folder)
    cache_key = f"{folder}:{int(wdir.stat().st_mtime) if wdir.exists() else 0}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    level: dict[str, Any] | None = None
    level_path = wdir / "level.dat"
    if level_path.is_file():
        try:
            level = level_dat_insight(level_path)
        except AppError as exc:
            logger.info("level.dat insight skipped: %s", exc)
            level = {"error": str(exc)}

    pack_index = _index_pack_roots(settings)
    enabled_rows = []
    if world.id is not None:
        enabled_rows = list(
            session.exec(
                select(WorldAddon, Addon)
                .join(Addon, col(WorldAddon.addon_id) == col(Addon.id))
                .where(
                    WorldAddon.world_id == world.id,
                    WorldAddon.enabled.is_(True),  # type: ignore[union-attr]
                )
            ).all()
        )

    packs: list[dict[str, Any]] = []
    seen_uuids: set[str] = set()

    for _link, addon in enabled_rows:
        root: Path | None = None
        if addon.storage_path:
            candidate = addons_service.packs_library_dir(settings) / addon.storage_path
            if candidate.is_dir():
                root = candidate
        if root is None:
            root = pack_index.get(addon.pack_uuid.lower())
        if root is None:
            continue
        if addon.pack_uuid.lower() in seen_uuids:
            continue
        seen_uuids.add(addon.pack_uuid.lower())
        kind = (
            addon.kind.value if isinstance(addon.kind, AddonKind) else str(addon.kind)
        )
        packs.append(
            _scan_pack_root(
                root,
                name=addon.name,
                kind=kind,
                pack_uuid=addon.pack_uuid,
            )
        )

    # Also include packs listed in world_* JSON that are not in WorldAddon yet.
    for entry in _world_pack_entries(wdir):
        pack_id = str(entry.get("pack_id") or entry.get("uuid") or "").strip().lower()
        if not pack_id or pack_id in seen_uuids:
            continue
        root = pack_index.get(pack_id)
        if root is None:
            continue
        try:
            parsed = addons_service.parse_manifest(root)
        except AppError:
            continue
        seen_uuids.add(pack_id)
        packs.append(
            _scan_pack_root(
                root,
                name=parsed.name,
                kind=parsed.kind.value,
                pack_uuid=parsed.pack_uuid,
            )
        )

    categories: dict[str, int] = {}
    totals = {
        "packs": len(packs),
        "behavior_packs": sum(1 for p in packs if p["kind"] == "behavior"),
        "resource_packs": sum(1 for p in packs if p["kind"] == "resource"),
        "items": 0,
        "entities": 0,
        "blocks": 0,
        "structures": 0,
        "recipes": 0,
        "loot_tables": 0,
        "functions": 0,
        "weapon_like_items": 0,
        "pack_bytes": 0,
    }
    for pack in packs:
        categories[pack["category"]] = categories.get(pack["category"], 0) + 1
        for key in (
            "items",
            "entities",
            "blocks",
            "structures",
            "recipes",
            "loot_tables",
            "functions",
        ):
            totals[key] += int(pack["counts"].get(key, 0))
        totals["weapon_like_items"] += int(pack["weapon_like_items"])
        totals["pack_bytes"] += int(pack["size_bytes"])

    highlights = sorted(
        packs,
        key=lambda p: (
            int(p["structure_files"])
            + int(p["weapon_like_items"])
            + int(p["counts"].get("items", 0))
            + int(p["counts"].get("entities", 0))
        ),
        reverse=True,
    )[:12]

    db_bytes = dir_size(wdir / "db") if (wdir / "db").is_dir() else 0
    payload = {
        "available": True,
        "reason": None,
        "world": {
            "id": world.id,
            "display_name": world.display_name,
            "folder_name": world.folder_name,
            "size_bytes": int(world.size_bytes or 0),
            "db_bytes": db_bytes,
            "gamemode": world.gamemode,
            "difficulty": world.difficulty,
            "seed": world.seed,
            "last_played_at": (
                world.last_played_at.isoformat() if world.last_played_at else None
            ),
        },
        "level": level,
        "packs": highlights,
        "all_pack_names": [p["name"] for p in packs],
        "totals": totals,
        "categories": categories,
    }
    _cache_set(cache_key, payload)
    return payload
