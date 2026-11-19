"""Unit coverage for world reset baseline selection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.db.session import get_engine
from app.models.backup import Backup, BackupKind
from app.models.world import World
from app.services import backups as backup_service
from app.services.archive_safety import create_tar_zst
from sqlmodel import Session


def _write_mini_world(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "level.dat").write_bytes(b"level")
    (folder / "db").mkdir(exist_ok=True)
    (folder / "db" / "x").write_bytes(b"1")


def test_resolve_reset_baseline_prefers_original(app_data_dir: Path) -> None:
    settings = get_settings()
    with Session(get_engine()) as session:
        world = World(
            display_name="TestWorld", folder_name="TestWorld", is_active=False
        )
        session.add(world)
        session.commit()
        session.refresh(world)

        world_dir = settings.data_dir / "worlds" / "TestWorld"
        _write_mini_world(world_dir)
        staging = settings.app_data_dir / "backups"
        staging.mkdir(parents=True, exist_ok=True)
        old_src = staging / "stage-old"
        _write_mini_world(old_src / "TestWorld")
        old_archive = staging / "TestWorld-manual-old.tar.zst"
        create_tar_zst(old_src / "TestWorld", old_archive, arcname="TestWorld")

        orig_src = staging / "stage-orig"
        _write_mini_world(orig_src / "TestWorld")
        (orig_src / "TestWorld" / "level.dat").write_bytes(b"original")
        orig_archive = staging / "TestWorld-original.tar.zst"
        create_tar_zst(orig_src / "TestWorld", orig_archive, arcname="TestWorld")

        assert world.id is not None
        session.add(
            Backup(
                world_id=world.id,
                kind=BackupKind.MANUAL,
                path=str(old_archive),
                size_bytes=old_archive.stat().st_size,
                sha256="a" * 64,
                verified=True,
                world_folder="TestWorld",
                created_at=datetime.now(UTC) - timedelta(days=2),
            )
        )
        session.add(
            Backup(
                world_id=world.id,
                kind=BackupKind.ORIGINAL,
                path=str(orig_archive),
                size_bytes=orig_archive.stat().st_size,
                sha256="b" * 64,
                verified=True,
                world_folder="TestWorld",
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        session.commit()

        baseline = backup_service.resolve_reset_baseline(
            session,
            settings,
            world_id=world.id,
            world_folder="TestWorld",
        )
        assert baseline.kind == BackupKind.ORIGINAL
        assert Path(baseline.path).name.endswith("original.tar.zst")


def test_resolve_reset_baseline_promotes_oldest(app_data_dir: Path) -> None:
    settings = get_settings()
    with Session(get_engine()) as session:
        world = World(
            display_name="OldImport", folder_name="OldImport", is_active=False
        )
        session.add(world)
        session.commit()
        session.refresh(world)

        staging = settings.app_data_dir / "backups"
        staging.mkdir(parents=True, exist_ok=True)
        src = staging / "stage"
        _write_mini_world(src / "OldImport")
        archive = staging / "OldImport-manual.tar.zst"
        create_tar_zst(src / "OldImport", archive, arcname="OldImport")

        assert world.id is not None
        session.add(
            Backup(
                world_id=world.id,
                kind=BackupKind.MANUAL,
                path=str(archive),
                size_bytes=archive.stat().st_size,
                sha256="c" * 64,
                verified=True,
                world_folder="OldImport",
                created_at=datetime.now(UTC) - timedelta(days=5),
            )
        )
        session.commit()

        baseline = backup_service.resolve_reset_baseline(
            session,
            settings,
            world_id=world.id,
            world_folder="OldImport",
        )
        assert baseline.kind == BackupKind.ORIGINAL
        assert Path(baseline.path).is_file()
        assert backup_service.get_original_backup(session, world.id) is not None
