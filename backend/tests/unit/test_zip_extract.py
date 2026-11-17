"""Safe zip / mcworld extraction."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from app.core.errors import AppError
from app.services.archive_safety import extract_zip_safe


def test_extract_zip_roundtrip(tmp_path: Path) -> None:
    archive = tmp_path / "w.mcworld"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("level.dat", b"level")
        zf.writestr("db/0001.ldb", b"data")

    dest = tmp_path / "out"
    extract_zip_safe(archive, dest)
    assert (dest / "level.dat").read_bytes() == b"level"
    assert (dest / "db" / "0001.ldb").read_bytes() == b"data"


def test_extract_rejects_path_escape(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", b"nope")
    with pytest.raises(AppError, match="Unsafe"):
        extract_zip_safe(archive, tmp_path / "out")
