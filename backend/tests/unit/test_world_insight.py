"""World insight pack classification and active-world scan."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.core.config import Settings, clear_settings_cache
from app.models.addon import Addon, AddonKind, WorldAddon
from app.models.world import World
from app.services import world_insight as insight
from app.services.world_insight import reset_insight_cache_for_tests
from sqlmodel import Session

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "level.dat_min"


def _settings(tmp_path: Path) -> Settings:
    clear_settings_cache()
    reset_insight_cache_for_tests()
    data = tmp_path / "data"
    app = tmp_path / "app-data"
    data.mkdir(exist_ok=True)
    app.mkdir(exist_ok=True)
    return Settings(
        data_dir=data,
        app_data_dir=app,
        secret_key="test-secret-key-not-real",
        public_url="http://localhost:8080",
        _env_file=None,
    )


def test_classify_pack_categories() -> None:
    assert insight._classify_pack("Aplok Guns Public", "guns_bp") == "weapons_combat"
    assert insight._classify_pack("Instant Structures", "bp") == "structures_builds"
    assert insight._classify_pack("Kitchen Craft", "kitchen") == "furniture_decor"
    assert insight._classify_pack("LAMBORGHINI BP", "car") == "vehicles"
    assert insight._classify_pack("AI Companions", "mobs") == "mobs_ai"
    assert insight._classify_pack("Mystery Pack", "xyz") == "other"


def test_build_world_insight_scans_enabled_pack(
    tmp_path: Path, db_session: Session
) -> None:
    settings = _settings(tmp_path)
    world_dir = settings.data_dir / "worlds" / "TestWorld"
    world_dir.mkdir(parents=True)
    shutil.copy(FIXTURE, world_dir / "level.dat")
    (world_dir / "db").mkdir()
    (world_dir / "db" / "CURRENT").write_text("1\n", encoding="utf-8")

    pack_root = (
        settings.app_data_dir
        / "packs"
        / "abc123"
        / "11111111-1111-1111-1111-111111111111"
    )
    pack_root.mkdir(parents=True)
    (pack_root / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 2,
                "header": {
                    "name": "Aplok Guns Public Beta",
                    "uuid": "11111111-1111-1111-1111-111111111111",
                    "version": [1, 0, 0],
                },
                "modules": [
                    {
                        "type": "data",
                        "uuid": "22222222-2222-2222-2222-222222222222",
                        "version": [1, 0, 0],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    items = pack_root / "items"
    items.mkdir()
    (items / "rifle.json").write_text("{}", encoding="utf-8")
    (items / "apple.json").write_text("{}", encoding="utf-8")
    structures = pack_root / "structures"
    structures.mkdir()
    (structures / "bunker.mcstructure").write_bytes(b"x")

    world = World(
        folder_name="TestWorld",
        display_name="TestWorld",
        is_active=True,
        size_bytes=100,
    )
    db_session.add(world)
    db_session.commit()
    db_session.refresh(world)

    addon = Addon(
        name="Aplok Guns Public Beta",
        pack_uuid="11111111-1111-1111-1111-111111111111",
        version="1.0.0",
        kind=AddonKind.BEHAVIOR,
        source_filename="guns.mcpack",
        sha256="a" * 64,
        size_bytes=10,
        storage_path="abc123/11111111-1111-1111-1111-111111111111",
    )
    db_session.add(addon)
    db_session.commit()
    db_session.refresh(addon)
    db_session.add(
        WorldAddon(world_id=world.id, addon_id=addon.id, enabled=True, load_order=0)
    )
    db_session.commit()

    payload = insight.build_world_insight(db_session, settings, use_cache=False)
    assert payload["available"] is True
    assert payload["level"]["level_name"] == "TestWorld"
    assert payload["totals"]["packs"] == 1
    assert payload["totals"]["items"] == 2
    assert payload["totals"]["structures"] == 1
    assert payload["totals"]["weapon_like_items"] >= 1
    assert payload["categories"]["weapons_combat"] == 1
    assert payload["packs"][0]["name"] == "Aplok Guns Public Beta"
