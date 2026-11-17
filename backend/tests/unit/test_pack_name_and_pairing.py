"""Pack display-name resolution and pairing warnings."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.models.addon import Addon, AddonKind
from app.services.addons import (
    _refresh_pairing,
    _resolve_pack_display_name,
    packs_library_dir,
    parse_manifest,
)
from sqlmodel import Session


def test_resolve_pack_name_from_lang(tmp_path: Path) -> None:
    root = tmp_path / "CoolFurniture"
    texts = root / "texts"
    texts.mkdir(parents=True)
    (texts / "en_US.lang").write_text("pack.name=Cool Furniture\n", encoding="utf-8")
    assert _resolve_pack_display_name(root, "pack.name") == "Cool Furniture"
    assert _resolve_pack_display_name(root, "Already Named") == "Already Named"


def test_parse_manifest_uses_lang_name(tmp_path: Path) -> None:
    root = tmp_path / "PackFolder"
    texts = root / "texts"
    texts.mkdir(parents=True)
    (texts / "en_US.lang").write_text(
        "pack.name=Instant Structures\n", encoding="utf-8"
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 2,
                "header": {
                    "name": "pack.name",
                    "uuid": "11111111-2222-3333-4444-555555555555",
                    "version": [8, 0, 0],
                },
                "modules": [
                    {
                        "type": "resources",
                        "uuid": "11111111-2222-3333-4444-555555555556",
                        "version": [8, 0, 0],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    parsed = parse_manifest(root)
    assert parsed.name == "Instant Structures"
    assert parsed.kind == AddonKind.RESOURCE


def test_standalone_resource_not_flagged_missing(
    tmp_path: Path, db_session: Session
) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        app_data_dir=tmp_path / "app-data",
        bedrock_uid=0,
        bedrock_gid=0,
        secret_key="test-secret-key-not-real",
        _env_file=None,
    )
    storage_rel = "abc/pack"
    storage = packs_library_dir(settings) / storage_rel
    storage.mkdir(parents=True)
    (storage / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 2,
                "header": {
                    "name": "Cars RP",
                    "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "version": [1, 0, 0],
                },
                "modules": [
                    {
                        "type": "resources",
                        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeef",
                        "version": [1, 0, 0],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    addon = Addon(
        name="Cars RP",
        pack_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        version="1.0.0",
        kind=AddonKind.RESOURCE,
        source_filename="cars",
        sha256="abc",
        size_bytes=10,
        missing_pair=True,
        storage_path=storage_rel,
    )
    db_session.add(addon)
    db_session.commit()

    _refresh_pairing(db_session, settings)
    db_session.refresh(addon)
    assert addon.missing_pair is False
