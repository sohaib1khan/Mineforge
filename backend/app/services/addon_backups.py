"""Backup and restore the MineForge pack library (+ world assignments).

Archives live under `/app-data/addon-backups/` as `.tar.zst` with a
`manifest.json` and a `packs/` tree. Restore replaces the library and
rebuilds Addon / WorldAddon rows from the manifest (matched by pack UUID
and world folder name).
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.models.addon import Addon, AddonKind, WorldAddon
from app.models.addon_backup import AddonLibraryBackup
from app.models.operation import OperationType
from app.models.user import UserRole
from app.models.world import World
from app.services import addons as addon_service
from app.services import operations as ops
from app.services.archive_safety import (
    atomic_replace_dir,
    copy_tree,
    create_tar_zst,
    extract_tar_zst,
    sha256_file,
    verify_tar_zst,
)
from app.services.audit import record_audit
from app.services.paths import resolve_under

logger = logging.getLogger(__name__)

MANIFEST_VERSION = 1


def addon_backups_dir(settings: Settings) -> Path:
    path = resolve_under(settings.app_data_dir, "addon-backups")
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_addon_backups(
    session: Session, *, limit: int = 100
) -> list[AddonLibraryBackup]:
    """Return pack-library backups newest first."""

    if limit < 1 or limit > 500:
        raise AppError("limit must be between 1 and 500")
    return list(
        session.exec(
            select(AddonLibraryBackup)
            .order_by(col(AddonLibraryBackup.created_at).desc())
            .limit(limit)
        ).all()
    )


def get_addon_backup(session: Session, backup_id: int) -> AddonLibraryBackup:
    backup = session.get(AddonLibraryBackup, backup_id)
    if backup is None:
        raise NotFoundError("Add-on library backup not found")
    return backup


def backup_to_dict(backup: AddonLibraryBackup) -> dict[str, Any]:
    return {
        "id": backup.id,
        "path": backup.path,
        "size_bytes": backup.size_bytes,
        "sha256": backup.sha256,
        "verified": backup.verified,
        "pack_count": backup.pack_count,
        "note": backup.note,
        "created_at": backup.created_at.isoformat() if backup.created_at else None,
        "created_by": backup.created_by,
    }


def _build_manifest(session: Session) -> dict[str, Any]:
    addons = list(session.exec(select(Addon).order_by(col(Addon.id).asc())).all())
    worlds = {
        w.id: w.folder_name
        for w in session.exec(select(World)).all()
        if w.id is not None
    }
    world_addons = list(session.exec(select(WorldAddon)).all())
    uuid_by_id = {a.id: a.pack_uuid for a in addons if a.id is not None}

    return {
        "version": MANIFEST_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "addons": [
            {
                "name": a.name,
                "pack_uuid": a.pack_uuid,
                "version": a.version,
                "kind": a.kind.value if isinstance(a.kind, AddonKind) else str(a.kind),
                "pair_pack_uuid": (
                    uuid_by_id.get(a.pair_addon_id) if a.pair_addon_id else None
                ),
                "source_filename": a.source_filename,
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
                "missing_pair": a.missing_pair,
                "encrypted": a.encrypted,
                "needs_beta_apis": a.needs_beta_apis,
                "notes": a.notes,
                "storage_path": a.storage_path,
            }
            for a in addons
        ],
        "world_addons": [
            {
                "world_folder": worlds.get(wa.world_id),
                "pack_uuid": uuid_by_id.get(wa.addon_id),
                "enabled": wa.enabled,
                "load_order": wa.load_order,
            }
            for wa in world_addons
            if worlds.get(wa.world_id) and uuid_by_id.get(wa.addon_id)
        ],
    }


def create_addon_library_backup_sync(
    session: Session,
    settings: Settings,
    *,
    created_by: int | None,
    note: str | None = None,
) -> AddonLibraryBackup:
    """Synchronously archive the pack library + assignment manifest.

    Raises:
        AppError: if packing or hashing fails.
    """

    packs = addon_service.packs_library_dir(settings)
    packs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = addon_backups_dir(settings) / f"addon-library-{stamp}.tar.zst"
    manifest = _build_manifest(session)

    with tempfile.TemporaryDirectory(prefix="mf-addon-bak-") as tmp:
        staging = Path(tmp) / "payload"
        staging.mkdir()
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        packs_dest = staging / "packs"
        if any(packs.iterdir()):
            copy_tree(packs, packs_dest)
        else:
            packs_dest.mkdir()
        create_tar_zst(staging, dest, arcname="addon-library")

    members = verify_tar_zst(dest)
    digest = sha256_file(dest)
    row = AddonLibraryBackup(
        path=str(dest),
        size_bytes=dest.stat().st_size,
        sha256=digest,
        verified=True,
        pack_count=len(manifest["addons"]),
        note=note,
        created_by=created_by,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info(
        "Add-on library backup #%s created (%s packs, %s members)",
        row.id,
        row.pack_count,
        len(members),
    )
    return row


def start_addon_library_backup(
    session: Session,
    settings: Settings,
    *,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> dict[str, Any]:
    """Queue a pack-library backup (admin)."""

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required to backup add-ons")
    op = ops.create_operation(
        session,
        op_type=OperationType.ADDON_BACKUP,
        params={"scope": "addon_library"},
        started_by=user_id,
    )
    record_audit(
        session,
        action="addon_backup.start",
        user_id=user_id,
        target="addon_library",
        details={"operation_id": op.id},
        ip=ip,
    )
    session.commit()
    operation_id = op.id
    assert operation_id is not None

    def work(worker_session: Session, oid: int) -> None:
        ops.append_log(worker_session, oid, "Archiving pack library")
        row = create_addon_library_backup_sync(
            worker_session, settings, created_by=user_id, note="manual"
        )
        ops.append_log(
            worker_session,
            oid,
            f"Created backup #{row.id} ({row.pack_count} packs, {row.size_bytes} bytes)",
        )

    ops.run_in_background(operation_id, work)
    return ops.operation_to_dict(ops.get_operation(session, operation_id))


def _restore_from_extracted(
    session: Session,
    settings: Settings,
    extracted: Path,
) -> int:
    """Apply extracted addon-library payload. Returns restored pack count."""

    manifest_path = extracted / "manifest.json"
    packs_src = extracted / "packs"
    if not manifest_path.is_file():
        # Nested top-level folder from tar
        children = [p for p in extracted.iterdir() if p.is_dir()]
        if len(children) == 1:
            nested = children[0]
            manifest_path = nested / "manifest.json"
            packs_src = nested / "packs"
    if not manifest_path.is_file():
        raise AppError("Backup is missing manifest.json")
    if not packs_src.is_dir():
        raise AppError("Backup is missing packs/")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(f"Invalid addon backup manifest: {exc}") from exc
    if int(payload.get("version", 0)) != MANIFEST_VERSION:
        raise AppError("Unsupported addon backup manifest version")

    packs_root = addon_service.packs_library_dir(settings)
    rollback = packs_root.parent / f"{packs_root.name}.pre-restore"
    if rollback.exists():
        shutil.rmtree(rollback, ignore_errors=True)

    with tempfile.TemporaryDirectory(prefix="mf-addon-restore-") as tmp:
        new_packs = Path(tmp) / "packs"
        if any(packs_src.iterdir()):
            copy_tree(packs_src, new_packs)
        else:
            new_packs.mkdir()
        atomic_replace_dir(new_packs, packs_root, backup=rollback)

    # Rebuild DB rows from manifest (keep pack files as restored).
    for wa in list(session.exec(select(WorldAddon)).all()):
        session.delete(wa)
    session.flush()
    for addon in list(session.exec(select(Addon)).all()):
        session.delete(addon)
    session.flush()

    uuid_to_id: dict[str, int] = {}
    for entry in payload.get("addons", []):
        storage = str(entry.get("storage_path") or "")
        if not storage:
            raise AppError("Manifest entry missing storage_path")
        storage_path = packs_root / storage
        if not storage_path.exists():
            raise AppError(f"Restored pack missing on disk: {storage}")
        kind_raw = str(entry.get("kind") or "behavior")
        kind = (
            AddonKind.RESOURCE
            if kind_raw == AddonKind.RESOURCE.value
            else AddonKind.BEHAVIOR
        )
        row = Addon(
            name=str(entry.get("name") or storage),
            pack_uuid=str(entry["pack_uuid"]),
            version=str(entry.get("version") or "0.0.0"),
            kind=kind,
            source_filename=str(entry.get("source_filename") or storage),
            sha256=str(entry.get("sha256") or ""),
            size_bytes=int(entry.get("size_bytes") or 0),
            missing_pair=bool(entry.get("missing_pair")),
            encrypted=bool(entry.get("encrypted")),
            needs_beta_apis=bool(entry.get("needs_beta_apis")),
            notes=entry.get("notes"),
            storage_path=storage,
        )
        session.add(row)
        session.flush()
        assert row.id is not None
        uuid_to_id[row.pack_uuid] = row.id

    # Re-link pairs by UUID
    for entry in payload.get("addons", []):
        pair_uuid = entry.get("pair_pack_uuid")
        pack_uuid = str(entry.get("pack_uuid") or "")
        if not pair_uuid or pack_uuid not in uuid_to_id:
            continue
        pair_id = uuid_to_id.get(str(pair_uuid))
        if pair_id is None:
            continue
        addon = session.get(Addon, uuid_to_id[pack_uuid])
        if addon is not None:
            addon.pair_addon_id = pair_id
            session.add(addon)

    worlds_by_folder = {
        w.folder_name: w.id
        for w in session.exec(select(World)).all()
        if w.id is not None
    }
    for wa in payload.get("world_addons", []):
        folder = wa.get("world_folder")
        pack_uuid = wa.get("pack_uuid")
        world_id = worlds_by_folder.get(str(folder)) if folder else None
        addon_id = uuid_to_id.get(str(pack_uuid)) if pack_uuid else None
        if world_id is None or addon_id is None:
            continue
        session.add(
            WorldAddon(
                world_id=world_id,
                addon_id=addon_id,
                enabled=bool(wa.get("enabled", True)),
                load_order=int(wa.get("load_order") or 0),
            )
        )

    session.commit()
    if rollback.exists():
        shutil.rmtree(rollback, ignore_errors=True)
    return len(uuid_to_id)


def restore_addon_library_sync(
    session: Session,
    settings: Settings,
    *,
    backup_id: int,
) -> int:
    """Restore pack library from a backup. Returns pack count.

    Raises:
        NotFoundError / AppError on missing or corrupt archives.
    """

    backup = get_addon_backup(session, backup_id)
    archive = Path(backup.path)
    if not archive.is_file():
        raise NotFoundError("Add-on backup archive file is missing")
    verify_tar_zst(archive)

    with tempfile.TemporaryDirectory(prefix="mf-addon-extract-") as tmp:
        dest = Path(tmp) / "out"
        extracted = extract_tar_zst(archive, dest)
        return _restore_from_extracted(session, settings, extracted)


def start_addon_library_restore(
    session: Session,
    settings: Settings,
    *,
    backup_id: int,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> dict[str, Any]:
    """Queue a pack-library restore (admin). Takes a safety backup first."""

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required to restore add-ons")
    backup = get_addon_backup(session, backup_id)
    if not Path(backup.path).is_file():
        raise NotFoundError("Add-on backup archive file is missing")

    op = ops.create_operation(
        session,
        op_type=OperationType.ADDON_RESTORE,
        params={"backup_id": backup.id},
        started_by=user_id,
    )
    record_audit(
        session,
        action="addon_backup.restore_start",
        user_id=user_id,
        target=str(backup.id),
        details={"operation_id": op.id},
        ip=ip,
    )
    session.commit()
    operation_id = op.id
    assert operation_id is not None
    bid = backup.id
    assert bid is not None

    def work(worker_session: Session, oid: int) -> None:
        ops.append_log(worker_session, oid, "Taking safety backup of current library")
        create_addon_library_backup_sync(
            worker_session,
            settings,
            created_by=user_id,
            note=f"pre_restore_of_{bid}",
        )
        ops.append_log(worker_session, oid, f"Restoring add-on library from #{bid}")
        count = restore_addon_library_sync(worker_session, settings, backup_id=bid)
        ops.append_log(worker_session, oid, f"Restored {count} pack(s)")

    ops.run_in_background(operation_id, work)
    return ops.operation_to_dict(ops.get_operation(session, operation_id))


def delete_addon_backup(
    session: Session,
    settings: Settings,
    *,
    backup_id: int,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> None:
    """Delete an add-on library backup archive and row (admin)."""

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    backup = get_addon_backup(session, backup_id)
    path = Path(backup.path)
    root = addon_backups_dir(settings).resolve()
    try:
        resolved = path.resolve()
    except FileNotFoundError:
        resolved = None
    if resolved is not None and resolved.is_file() and resolved.is_relative_to(root):
        resolved.unlink(missing_ok=True)
    session.delete(backup)
    record_audit(
        session,
        action="addon_backup.delete",
        user_id=user_id,
        target=str(backup_id),
        details=None,
        ip=ip,
    )
    session.commit()


def resolve_backup_file(session: Session, settings: Settings, backup_id: int) -> Path:
    """Return a verified path to a downloadable addon backup archive."""

    backup = get_addon_backup(session, backup_id)
    path = Path(backup.path)
    root = addon_backups_dir(settings).resolve()
    try:
        resolved = path.resolve()
    except FileNotFoundError as exc:
        raise NotFoundError("Backup file missing") from exc
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise NotFoundError("Backup file missing")
    return resolved
