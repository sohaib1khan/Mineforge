"""Archive create / verify / extract safety."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.errors import AppError
from app.services.archive_safety import (
    create_tar_zst,
    create_tar_zst_mixed,
    extract_tar_zst,
    sha256_file,
    verify_tar_zst,
)


def test_create_verify_extract_roundtrip(tmp_path: Path) -> None:
    world = tmp_path / "TestWorld"
    (world / "db").mkdir(parents=True)
    (world / "level.dat").write_bytes(b"level-data")
    (world / "db" / "000001.ldb").write_bytes(b"x" * 100)

    archive = tmp_path / "TestWorld.tar.zst"
    size = create_tar_zst(world, archive)
    assert size > 0
    assert archive.is_file()

    members = verify_tar_zst(archive)
    assert any("level.dat" in m for m in members)
    digest = sha256_file(archive)
    assert len(digest) == 64

    out = tmp_path / "out"
    extracted = extract_tar_zst(archive, out)
    assert (extracted / "level.dat").read_bytes() == b"level-data"
    assert (extracted / "db" / "000001.ldb").read_bytes() == b"x" * 100


def test_create_tar_zst_mixed_streams_without_staging(tmp_path: Path) -> None:
    packs = tmp_path / "packs"
    (packs / "behavior" / "TestPack").mkdir(parents=True)
    (packs / "behavior" / "TestPack" / "pack.txt").write_text("hi", encoding="utf-8")
    archive = tmp_path / "lib.tar.zst"
    create_tar_zst_mixed(
        archive,
        inline_files={"addon-library/manifest.json": b'{"version":1}'},
        directories={"addon-library/packs": packs},
    )
    members = verify_tar_zst(archive)
    assert "addon-library/manifest.json" in members
    assert any(m.endswith("pack.txt") for m in members)
    out = tmp_path / "out"
    extracted = extract_tar_zst(archive, out)
    root = extracted if (extracted / "manifest.json").is_file() else extracted
    if not (root / "manifest.json").is_file():
        root = next(p for p in out.iterdir() if p.is_dir())
    assert (root / "manifest.json").read_bytes() == b'{"version":1}'
    assert (root / "packs" / "behavior" / "TestPack" / "pack.txt").read_text(
        encoding="utf-8"
    ) == "hi"


def test_extract_rejects_empty_dest_with_contents(tmp_path: Path) -> None:
    world = tmp_path / "W"
    world.mkdir()
    (world / "level.dat").write_bytes(b"a")
    (world / "db").mkdir()
    archive = tmp_path / "w.tar.zst"
    create_tar_zst(world, archive)

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "existing").write_text("nope", encoding="utf-8")
    with pytest.raises(AppError, match="not empty"):
        extract_tar_zst(archive, dest)
