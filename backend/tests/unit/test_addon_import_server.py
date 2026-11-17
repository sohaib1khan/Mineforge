"""Import packs already present under /data into the library."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.models.addon import Addon
from app.services import addons as addon_service
from sqlmodel import Session, select


def _write_manifest(folder: Path, *, name: str, uuid: str, kind: str) -> None:
    folder.mkdir(parents=True)
    module_type = "data" if kind == "behavior" else "resources"
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 2,
                "header": {
                    "name": name,
                    "uuid": uuid,
                    "version": [1, 2, 3],
                },
                "modules": [{"type": module_type, "uuid": uuid, "version": [1, 2, 3]}],
            }
        ),
        encoding="utf-8",
    )


def test_import_packs_from_server_data_skips_stock(
    tmp_path: Path, db_session: Session
) -> None:
    data = tmp_path / "data"
    bp = data / "behavior_packs"
    _write_manifest(
        bp / "Gamer_Tech_BP",
        name="GamerTech BP",
        uuid="c06733b6-8734-4e38-8488-ba5940ca3566",
        kind="behavior",
    )
    _write_manifest(
        bp / "vanilla",
        name="Vanilla Behavior",
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        kind="behavior",
    )
    settings = Settings(
        data_dir=data,
        app_data_dir=tmp_path / "app-data",
        bedrock_uid=0,
        bedrock_gid=0,
        secret_key="test-secret-key-not-real",
        _env_file=None,
    )

    created = addon_service.import_packs_from_server_data(db_session, settings)
    assert created == 1
    rows = list(db_session.exec(select(Addon)).all())
    assert len(rows) == 1
    assert rows[0].name == "GamerTech BP"
    assert "Imported from server data" in (rows[0].notes or "")

    # Idempotent
    assert addon_service.import_packs_from_server_data(db_session, settings) == 0
