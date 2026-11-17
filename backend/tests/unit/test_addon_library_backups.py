"""Pack-library backup / restore round-trip."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.models.addon import Addon, AddonKind, WorldAddon
from app.models.world import World
from app.services import addon_backups as backup_service
from app.services import addons as addon_service
from sqlmodel import Session, select


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        app_data_dir=tmp_path / "app-data",
        bedrock_uid=0,
        bedrock_gid=0,
        secret_key="test-secret-key-not-real",
        _env_file=None,
    )


def test_addon_library_backup_and_restore_roundtrip(
    tmp_path: Path, db_session: Session
) -> None:
    settings = _settings(tmp_path)
    packs = addon_service.packs_library_dir(settings)
    storage_rel = "behavior/TestPack_bp"
    pack_dir = packs / storage_rel
    pack_dir.mkdir(parents=True)
    (pack_dir / "manifest.json").write_text(
        json.dumps({"header": {"name": "TestPack", "uuid": "u-1"}}),
        encoding="utf-8",
    )
    (pack_dir / "pack.txt").write_text("hello", encoding="utf-8")

    world = World(
        display_name="TestWorld",
        folder_name="TestWorld",
        size_bytes=0,
        is_active=True,
    )
    db_session.add(world)
    db_session.commit()
    db_session.refresh(world)

    addon = Addon(
        name="TestPack",
        pack_uuid="11111111-1111-1111-1111-111111111111",
        version="1.0.0",
        kind=AddonKind.BEHAVIOR,
        source_filename="TestPack.mcpack",
        sha256="a" * 64,
        size_bytes=5,
        storage_path=storage_rel,
    )
    db_session.add(addon)
    db_session.commit()
    db_session.refresh(addon)
    assert world.id is not None and addon.id is not None
    db_session.add(
        WorldAddon(world_id=world.id, addon_id=addon.id, enabled=True, load_order=1)
    )
    db_session.commit()

    row = backup_service.create_addon_library_backup_sync(
        db_session, settings, created_by=1, note="unit"
    )
    assert row.id is not None
    assert row.pack_count == 1
    assert Path(row.path).is_file()
    assert row.verified is True

    # Mutate library then restore
    (pack_dir / "pack.txt").write_text("changed", encoding="utf-8")
    addon.name = "Changed"
    db_session.add(addon)
    db_session.commit()

    restored = backup_service.restore_addon_library_sync(
        db_session, settings, backup_id=row.id
    )
    assert restored == 1
    assert (packs / storage_rel / "pack.txt").read_text(encoding="utf-8") == "hello"
    rows = list(db_session.exec(select(Addon)).all())
    assert len(rows) == 1
    assert rows[0].name == "TestPack"
    links = list(db_session.exec(select(WorldAddon)).all())
    assert len(links) == 1
    assert links[0].load_order == 1
