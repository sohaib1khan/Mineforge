"""Add-on library: upload, parse, pair, per-world profiles, apply, test/revert.

Pack files live under `/app-data/packs/<sha256>/`. Applied copies are synced into
`/data/behavior_packs` or `/data/resource_packs`. World pack JSON files merge
enabled library packs with world-embedded packs so imports are never wiped.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.db.session import get_engine
from app.models.addon import Addon, AddonKind, WorldAddon
from app.models.backup import BackupKind
from app.models.operation import OperationType
from app.models.user import UserRole
from app.models.world import World
from app.services import console as console_service
from app.services import operations as ops
from app.services import server_props
from app.services import worlds as worlds_service
from app.services.archive_safety import (
    dir_size,
    extract_zip_safe,
    sha256_file,
)
from app.services.audit import record_audit
from app.services.docker_client import get_docker_client
from app.services.paths import resolve_under

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_pending_tests: dict[int, PendingTest] = {}
_pending_lock = threading.Lock()
_apply_fail_hook: Callable[[], None] | None = None


@dataclass
class PendingTest:
    operation_id: int
    world_id: int
    world_folder: str
    snapshot_bp: str
    snapshot_rp: str
    expires_at: datetime
    timer: threading.Timer


@dataclass
class ParsedPack:
    name: str
    pack_uuid: str
    version: str
    version_list: list[int]
    kind: AddonKind
    encrypted: bool
    needs_beta_apis: bool
    dependencies: list[str]
    root: Path
    min_engine_version: list[int] | None = None


PROFILE_MANAGED_MARKER = ".mineforge-addon-profile"


def set_apply_fail_hook(hook: Callable[[], None] | None) -> None:
    """Inject failure after pack JSON write during apply (tests)."""

    global _apply_fail_hook
    _apply_fail_hook = hook


def reset_pending_tests_for_tests() -> None:
    with _pending_lock:
        for pending in list(_pending_tests.values()):
            pending.timer.cancel()
        _pending_tests.clear()


def packs_library_dir(settings: Settings) -> Path:
    path = resolve_under(settings.app_data_dir, "packs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def behavior_packs_dir(settings: Settings) -> Path:
    path = resolve_under(settings.data_dir, "behavior_packs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_packs_dir(settings: Settings) -> Path:
    path = resolve_under(settings.data_dir, "resource_packs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_addons(session: Session) -> list[Addon]:
    return list(
        session.exec(select(Addon).order_by(col(Addon.created_at).desc())).all()
    )


def _is_stock_pack(folder_name: str, pack_name: str) -> bool:
    """Skip Mojang stock packs when importing from a live /data tree."""

    lowered = f"{folder_name} {pack_name}".lower()
    stock_markers = (
        "vanilla",
        "chemistry",
        "editor",
        "experimental",
        "education",
        "castomatic",
    )
    return any(marker in lowered for marker in stock_markers)


def import_packs_from_server_data(session: Session, settings: Settings) -> int:
    """Register custom packs already under `/data` into the MineForge library.

    Scans behavior/resource (+ development) pack folders, copies non-stock packs
    into `/app-data/packs`, and links world_*_packs.json entries to WorldAddon rows.

    Returns:
        Number of newly imported library rows.
    """

    created = 0
    for root in _server_pack_roots(settings):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or not (child / "manifest.json").is_file():
                continue
            try:
                parsed = parse_manifest(child)
            except AppError:
                continue
            if _is_stock_pack(child.name, parsed.name):
                continue
            existing = session.exec(
                select(Addon).where(
                    Addon.pack_uuid == parsed.pack_uuid,
                    Addon.version == parsed.version,
                    Addon.kind == parsed.kind,
                )
            ).first()
            if existing:
                if _looks_like_lang_key(existing.name) and parsed.name != existing.name:
                    existing.name = parsed.name
                    session.add(existing)
                continue
            digest = hashlib.sha256(
                f"server:{parsed.pack_uuid}:{parsed.version}:{parsed.kind.value}".encode()
            ).hexdigest()
            storage_rel = f"{digest}/{parsed.pack_uuid}"
            storage = packs_library_dir(settings) / storage_rel
            if storage.exists():
                shutil.rmtree(storage)
            storage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(child, storage, symlinks=False)
            addon = Addon(
                name=parsed.name,
                pack_uuid=parsed.pack_uuid,
                version=parsed.version,
                kind=parsed.kind,
                source_filename=child.name,
                sha256=digest,
                size_bytes=dir_size(storage),
                missing_pair=False,
                encrypted=parsed.encrypted,
                needs_beta_apis=parsed.needs_beta_apis,
                uploaded_by=None,
                storage_path=storage_rel,
                notes=f"Imported from server data ({root.name}/{child.name})",
            )
            session.add(addon)
            session.flush()
            created += 1

    _repair_localized_names(session, settings)
    _refresh_pairing(session, settings)
    _sync_world_pack_links(session, settings)
    session.commit()
    if created:
        logger.info("Imported %s pack(s) from server /data into the library", created)
    return created


def _looks_like_lang_key(name: str) -> bool:
    cleaned = (name or "").strip()
    return (
        (not cleaned)
        or cleaned.startswith("pack.")
        or cleaned in {"name", "description"}
    )


def _repair_localized_names(session: Session, settings: Settings) -> None:
    """Fix library rows that still store localization keys as the display name."""

    for addon in session.exec(select(Addon)).all():
        if not _looks_like_lang_key(addon.name):
            continue
        root = packs_library_dir(settings) / addon.storage_path
        if not root.is_dir():
            continue
        try:
            parsed = parse_manifest(root)
        except AppError:
            continue
        if parsed.name and parsed.name != addon.name:
            addon.name = parsed.name
            session.add(addon)


def _sync_world_pack_links(session: Session, settings: Settings) -> None:
    """Bootstrap WorldAddon rows from pack JSON for worlds without a saved profile.

    Once MineForge has written ``.mineforge-addon-profile`` for a world, the DB
    profile is authoritative — do not recreate enabled rows from stale JSON
    (that undoes Save / deselect across page refresh).
    """

    worlds = list(session.exec(select(World)).all())
    for world in worlds:
        folder = worlds_service.world_path(settings, world.folder_name)
        if not folder.is_dir() or world.id is None:
            continue
        if (folder / PROFILE_MANAGED_MARKER).is_file():
            continue
        order = 0
        for json_name in ("world_behavior_packs.json", "world_resource_packs.json"):
            path = folder / json_name
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, list):
                continue
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                pack_id = str(entry.get("pack_id") or entry.get("uuid") or "").lower()
                if not pack_id:
                    continue
                version_raw = entry.get("version") or [1, 0, 0]
                if isinstance(version_raw, list):
                    version = ".".join(str(int(x)) for x in version_raw[:3])
                else:
                    version = str(version_raw)
                addon = session.exec(
                    select(Addon).where(
                        Addon.pack_uuid == pack_id,
                        Addon.version == version,
                    )
                ).first()
                if addon is None:
                    addon = session.exec(
                        select(Addon).where(Addon.pack_uuid == pack_id)
                    ).first()
                if addon is None or addon.id is None:
                    continue
                link = session.exec(
                    select(WorldAddon).where(
                        WorldAddon.world_id == world.id,
                        WorldAddon.addon_id == addon.id,
                    )
                ).first()
                if link is None:
                    session.add(
                        WorldAddon(
                            world_id=world.id,
                            addon_id=addon.id,
                            enabled=True,
                            load_order=order,
                        )
                    )
                order += 1


def _mark_world_profile_managed(settings: Settings, folder_name: str) -> None:
    """Record that MineForge owns this world's add-on profile (skip JSON re-import)."""

    folder = worlds_service.world_path(settings, folder_name)
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / PROFILE_MANAGED_MARKER
    marker.write_text("managed-by-mineforge\n", encoding="utf-8")
    try:
        os.chown(marker, settings.bedrock_uid, settings.bedrock_gid)
    except PermissionError:
        logger.warning("Could not chown addon profile marker %s", marker)


def get_addon(session: Session, addon_id: int) -> Addon:
    addon = session.get(Addon, addon_id)
    if addon is None:
        raise NotFoundError("Add-on not found")
    return addon


def addon_to_dict(session: Session, addon: Addon) -> dict[str, Any]:
    used_by = list(
        session.exec(select(WorldAddon).where(WorldAddon.addon_id == addon.id)).all()
    )
    pair_name = None
    if addon.pair_addon_id:
        pair = session.get(Addon, addon.pair_addon_id)
        if pair:
            pair_name = pair.name
    flags: list[str] = []
    if addon.missing_pair:
        flags.append("missing_pair")
    if addon.encrypted:
        flags.append("encrypted")
    if addon.needs_beta_apis:
        flags.append("needs_beta_apis")
    return {
        "id": addon.id,
        "name": addon.name,
        "pack_uuid": addon.pack_uuid,
        "version": addon.version,
        "kind": addon.kind.value if isinstance(addon.kind, AddonKind) else addon.kind,
        "pair_addon_id": addon.pair_addon_id,
        "pair_name": pair_name,
        "source_filename": addon.source_filename,
        "sha256": addon.sha256,
        "size_bytes": addon.size_bytes,
        "missing_pair": addon.missing_pair,
        "encrypted": addon.encrypted,
        "needs_beta_apis": addon.needs_beta_apis,
        "flags": flags,
        "uploaded_by": addon.uploaded_by,
        "created_at": addon.created_at.isoformat() if addon.created_at else None,
        "notes": addon.notes,
        "used_by_world_ids": [wa.world_id for wa in used_by],
    }


def upload_addon(
    session: Session,
    settings: Settings,
    *,
    upload_path: Path,
    original_filename: str,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> list[Addon]:
    """Parse and store packs from a `.mcaddon` / `.mcpack` / `.zip` upload.

    Raises:
        ForbiddenError: non-admin.
        AppError: bad archive or missing manifests.
    """

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    suffix = upload_path.suffix.lower()
    if suffix not in {".mcaddon", ".mcpack", ".zip"}:
        raise AppError("Only .mcaddon, .mcpack, or .zip uploads are supported")

    digest = sha256_file(upload_path)
    staging = Path(tempfile.mkdtemp(prefix="mf-addon-", dir=str(settings.app_data_dir)))
    created: list[Addon] = []
    try:
        extract_zip_safe(upload_path, staging)
        pack_roots = _discover_pack_roots(staging)
        if not pack_roots:
            # Single .mcpack often extracts with manifest at top level
            if (staging / "manifest.json").is_file():
                pack_roots = [staging]
            else:
                raise AppError("No pack manifests found in upload")

        for root in pack_roots:
            parsed = parse_manifest(root)
            storage_rel = f"{digest}/{parsed.pack_uuid}"
            storage = packs_library_dir(settings) / storage_rel
            if storage.exists():
                shutil.rmtree(storage)
            storage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(root, storage, symlinks=False)

            # Deduplicate by uuid+version+kind
            existing = session.exec(
                select(Addon).where(
                    Addon.pack_uuid == parsed.pack_uuid,
                    Addon.version == parsed.version,
                    Addon.kind == parsed.kind,
                )
            ).first()
            if existing:
                existing.storage_path = storage_rel
                existing.size_bytes = dir_size(storage)
                existing.encrypted = parsed.encrypted
                existing.needs_beta_apis = parsed.needs_beta_apis
                existing.source_filename = original_filename
                session.add(existing)
                created.append(existing)
                continue

            addon = Addon(
                name=parsed.name,
                pack_uuid=parsed.pack_uuid,
                version=parsed.version,
                kind=parsed.kind,
                source_filename=original_filename,
                sha256=digest,
                size_bytes=dir_size(storage),
                missing_pair=False,
                encrypted=parsed.encrypted,
                needs_beta_apis=parsed.needs_beta_apis,
                uploaded_by=user_id,
                storage_path=storage_rel,
            )
            session.add(addon)
            session.flush()
            created.append(addon)

        session.commit()
        for addon in created:
            session.refresh(addon)
        _refresh_pairing(session, settings)
        session.commit()
        for addon in created:
            session.refresh(addon)

        record_audit(
            session,
            action="addon.upload",
            user_id=user_id,
            target=original_filename,
            details={"addon_ids": [a.id for a in created]},
            ip=ip,
        )
        session.commit()
        return created
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def delete_addon(
    session: Session,
    settings: Settings,
    *,
    addon_id: int,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> None:
    """Remove a pack from the library and from Bedrock ``/data`` pack folders.

    Also strips the pack UUID from every world's pack JSON so Apply/list does not
    keep re-importing the same pack from server data.
    """

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    addon = get_addon(session, addon_id)
    pack_uuid = addon.pack_uuid
    kind = addon.kind
    links = list(
        session.exec(select(WorldAddon).where(WorldAddon.addon_id == addon_id)).all()
    )
    for link in links:
        session.delete(link)
    # Clear reverse pairs
    for other in session.exec(
        select(Addon).where(Addon.pair_addon_id == addon_id)
    ).all():
        other.pair_addon_id = None
        other.missing_pair = True
        session.add(other)
    storage = packs_library_dir(settings) / addon.storage_path
    session.delete(addon)
    record_audit(
        session, action="addon.delete", user_id=user_id, target=str(addon_id), ip=ip
    )
    session.commit()
    if storage.is_dir():
        shutil.rmtree(storage, ignore_errors=True)
    removed = _remove_server_pack_copies(settings, pack_uuid=pack_uuid, kind=kind)
    stripped = _strip_pack_uuid_from_world_jsons(settings, pack_uuid=pack_uuid)
    logger.info(
        "Deleted addon %s (%s): removed %s server folder(s), stripped %s world JSON file(s)",
        addon_id,
        pack_uuid,
        removed,
        stripped,
    )
    _refresh_pairing(session, settings)
    session.commit()


def _server_pack_roots(settings: Settings) -> list[Path]:
    return [
        settings.data_dir / "behavior_packs",
        settings.data_dir / "resource_packs",
        settings.data_dir / "development_behavior_packs",
        settings.data_dir / "development_resource_packs",
    ]


def _remove_server_pack_copies(
    settings: Settings, *, pack_uuid: str, kind: AddonKind
) -> int:
    """Delete matching pack folders under Bedrock ``/data`` pack roots."""

    target = pack_uuid.lower()
    removed = 0
    for root in _server_pack_roots(settings):
        if not root.is_dir():
            continue
        for child in list(root.iterdir()):
            if not child.is_dir() or not (child / "manifest.json").is_file():
                continue
            try:
                parsed = parse_manifest(child)
            except AppError:
                continue
            if parsed.kind != kind:
                continue
            if parsed.pack_uuid.lower() != target:
                continue
            if _is_stock_pack(child.name, parsed.name):
                continue
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def _strip_pack_uuid_from_world_jsons(settings: Settings, *, pack_uuid: str) -> int:
    """Remove a pack UUID from every world's behavior/resource pack JSON lists."""

    target = pack_uuid.lower()
    worlds_root = settings.data_dir / "worlds"
    if not worlds_root.is_dir():
        return 0
    changed = 0
    for world_dir in worlds_root.iterdir():
        if not world_dir.is_dir():
            continue
        for json_name in ("world_behavior_packs.json", "world_resource_packs.json"):
            path = world_dir / json_name
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, list):
                continue
            kept: list[Any] = []
            removed_any = False
            for entry in payload:
                if not isinstance(entry, dict):
                    kept.append(entry)
                    continue
                entry_id = str(entry.get("pack_id") or entry.get("uuid") or "").lower()
                if entry_id == target:
                    removed_any = True
                    continue
                kept.append(entry)
            if not removed_any:
                continue
            path.write_text(
                json.dumps(kept, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            changed += 1
    return changed


def get_world_profile(session: Session, world_id: int) -> list[dict[str, Any]]:
    world = session.get(World, world_id)
    if world is None:
        raise NotFoundError("World not found")
    rows = list(
        session.exec(
            select(WorldAddon)
            .where(WorldAddon.world_id == world_id)
            .order_by(WorldAddon.load_order, WorldAddon.id)
        ).all()
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        addon = get_addon(session, row.addon_id)
        result.append(
            {
                "world_addon_id": row.id,
                "addon_id": addon.id,
                "enabled": row.enabled,
                "load_order": row.load_order,
                "addon": addon_to_dict(session, addon),
            }
        )
    return result


def set_world_profile(
    session: Session,
    settings: Settings,
    *,
    world_id: int,
    entries: list[dict[str, Any]],
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> list[dict[str, Any]]:
    """Replace a world's add-on profile and write pack JSON so refresh cannot revive packs.

    Does not restart Bedrock — use Apply for a full pack sync + restart. Writing
    ``world_*_packs.json`` here keeps list/import from re-enabling unchecked packs.
    """

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    world = session.get(World, world_id)
    if world is None:
        raise NotFoundError("World not found")

    existing = list(
        session.exec(select(WorldAddon).where(WorldAddon.world_id == world_id)).all()
    )
    for row in existing:
        session.delete(row)
    session.flush()

    for idx, entry in enumerate(entries):
        addon_id = int(entry["addon_id"])
        get_addon(session, addon_id)
        session.add(
            WorldAddon(
                world_id=world_id,
                addon_id=addon_id,
                enabled=bool(entry.get("enabled", True)),
                load_order=int(entry.get("load_order", idx)),
            )
        )
    session.flush()
    write_merged_pack_jsons(session, settings, world.folder_name, world_id)
    _mark_world_profile_managed(settings, world.folder_name)
    record_audit(
        session,
        action="addon.profile_set",
        user_id=user_id,
        target=str(world_id),
        details={"count": len(entries)},
        ip=ip,
    )
    session.commit()
    return get_world_profile(session, world_id)


def world_download_size(
    session: Session, settings: Settings, world_id: int
) -> dict[str, int]:
    """Sum sizes of enabled profile packs (+ rough embedded pack dirs)."""

    world = session.get(World, world_id)
    if world is None:
        raise NotFoundError("World not found")
    total = 0
    count = 0
    for row in session.exec(
        select(WorldAddon).where(
            WorldAddon.world_id == world_id, WorldAddon.enabled.is_(True)  # type: ignore[union-attr]
        )
    ).all():
        addon = get_addon(session, row.addon_id)
        total += addon.size_bytes
        count += 1
    path = worlds_service.world_path(settings, world.folder_name)
    for sub in ("behavior_packs", "resource_packs"):
        embedded = path / sub
        if embedded.is_dir():
            total += dir_size(embedded)
    return {"enabled_pack_bytes": total, "enabled_pack_count": count}


def start_apply(
    session: Session,
    settings: Settings,
    *,
    world_id: int,
    user_id: int,
    role: UserRole,
    ip: str | None,
    test_mode: bool = False,
) -> dict[str, Any]:
    """Apply the world's enabled profile (or test with auto-revert)."""

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    world = session.get(World, world_id)
    if world is None:
        raise NotFoundError("World not found")

    op_type = OperationType.ADDON_TEST if test_mode else OperationType.ADDON_APPLY
    op = ops.create_operation(
        session,
        op_type=op_type,
        params={
            "world_id": world_id,
            "world_folder": world.folder_name,
            "test_mode": test_mode,
        },
        started_by=user_id,
    )
    record_audit(
        session,
        action="addon.apply_start" if not test_mode else "addon.test_start",
        user_id=user_id,
        target=world.folder_name,
        details={"operation_id": op.id, "test_mode": test_mode},
        ip=ip,
    )
    session.commit()
    operation_id = op.id
    assert operation_id is not None
    folder = world.folder_name
    wid = world_id

    def work(worker_session: Session, oid: int) -> None:
        _run_apply(
            worker_session,
            settings,
            operation_id=oid,
            world_id=wid,
            world_folder=folder,
            test_mode=test_mode,
            started_by=user_id,
        )

    ops.run_in_background(operation_id, work)
    return ops.operation_to_dict(ops.get_operation(session, operation_id))


def keep_test(
    session: Session, settings: Settings, *, world_id: int, user_id: int
) -> None:
    """Confirm a test apply — cancel auto-revert."""

    with _pending_lock:
        pending = _pending_tests.pop(world_id, None)
    if pending is None:
        raise AppError("No pending add-on test for this world")
    pending.timer.cancel()
    record_audit(
        session,
        action="addon.test_keep",
        user_id=user_id,
        target=str(world_id),
        details={"operation_id": pending.operation_id},
    )
    session.commit()
    ops.append_log(
        session, pending.operation_id, "Test keep confirmed — auto-revert cancelled"
    )


def revert_test_now(
    session: Session, settings: Settings, *, world_id: int, user_id: int | None
) -> None:
    """Immediately revert a pending test (or call from timer).

    Refuses to stop/start Bedrock while another operation holds the global lock
    (e.g. world switch) — callers should reschedule instead of racing.
    """

    if ops.is_busy():
        raise AppError("Another operation is running; deferring add-on test revert")

    with _pending_lock:
        pending = _pending_tests.pop(world_id, None)
    if pending is None:
        raise AppError("No pending add-on test for this world")
    pending.timer.cancel()
    _restore_pack_jsons(
        settings, pending.world_folder, pending.snapshot_bp, pending.snapshot_rp
    )
    docker = get_docker_client(settings)
    was_running = docker.status().running
    if was_running:
        try:
            console_service.send_command(settings, "stop", actor="addon-revert")
            time.sleep(1)
        except Exception:
            pass
        docker.stop(timeout=30)
        docker.start()
    record_audit(
        session,
        action="addon.test_revert",
        user_id=user_id,
        target=str(world_id),
        details={"operation_id": pending.operation_id},
    )
    session.commit()
    with Session(get_engine()) as live:
        ops.append_log(live, pending.operation_id, "Test auto-reverted pack JSONs")


def list_pending_tests() -> list[dict[str, Any]]:
    with _pending_lock:
        return [
            {
                "world_id": wid,
                "operation_id": p.operation_id,
                "world_folder": p.world_folder,
                "expires_at": p.expires_at.isoformat(),
            }
            for wid, p in _pending_tests.items()
        ]


def cancel_all_pending_tests(*, reason: str) -> int:
    """Cancel timers for all pending test reverts without restoring files.

    Used when a world switch starts so auto-revert cannot restart Bedrock mid-switch.
    Returns the number of cancelled pending tests.
    """

    with _pending_lock:
        pending_items = list(_pending_tests.items())
        _pending_tests.clear()
    for world_id, pending in pending_items:
        pending.timer.cancel()
        logger.info(
            "Cancelled pending add-on test revert for world %s (%s)", world_id, reason
        )
        try:
            with Session(get_engine()) as live:
                ops.append_log(
                    live,
                    pending.operation_id,
                    f"Test auto-revert cancelled ({reason})",
                )
        except Exception:
            logger.exception(
                "Failed to log cancelled test revert for world %s", world_id
            )
    return len(pending_items)


def write_merged_pack_jsons(
    session: Session, settings: Settings, world_folder: str, world_id: int
) -> None:
    """Write world_*_packs.json merging embedded packs + enabled profile.

    Used by apply and by world switch so embedded packs are preserved.
    """

    world_dir = worlds_service.world_path(settings, world_folder)
    world_dir.mkdir(parents=True, exist_ok=True)

    enabled = list(
        session.exec(
            select(WorldAddon)
            .where(
                WorldAddon.world_id == world_id,
                WorldAddon.enabled.is_(True),  # type: ignore[union-attr]
            )
            .order_by(WorldAddon.load_order, WorldAddon.id)
        ).all()
    )

    bp_entries: list[dict[str, Any]] = []
    rp_entries: list[dict[str, Any]] = []

    # Embedded first
    bp_entries.extend(_read_embedded_pack_refs(world_dir / "behavior_packs"))
    rp_entries.extend(_read_embedded_pack_refs(world_dir / "resource_packs"))

    seen_bp = {e["pack_id"] for e in bp_entries}
    seen_rp = {e["pack_id"] for e in rp_entries}

    for row in enabled:
        addon = get_addon(session, row.addon_id)
        if addon.encrypted:
            continue
        _sync_pack_into_data(settings, addon)
        entry = {
            "pack_id": addon.pack_uuid,
            "version": _version_list(addon.version),
        }
        if addon.kind == AddonKind.BEHAVIOR:
            if addon.pack_uuid not in seen_bp:
                bp_entries.append(entry)
                seen_bp.add(addon.pack_uuid)
        else:
            if addon.pack_uuid not in seen_rp:
                rp_entries.append(entry)
                seen_rp.add(addon.pack_uuid)

    _write_json(
        world_dir / "world_behavior_packs.json",
        bp_entries,
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )
    _write_json(
        world_dir / "world_resource_packs.json",
        rp_entries,
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )


def parse_manifest(pack_root: Path) -> ParsedPack:
    """Parse a Bedrock pack manifest.json.

    Raises:
        AppError: missing/invalid manifest.
    """

    manifest_path = pack_root / "manifest.json"
    if not manifest_path.is_file():
        raise AppError(f"manifest.json missing in {pack_root.name}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppError(f"Invalid manifest.json: {exc}") from exc

    header = data.get("header") or {}
    raw_name = str(header.get("name") or "").strip()
    name = _resolve_pack_display_name(pack_root, raw_name)
    pack_uuid = str(header.get("uuid") or "").strip()
    if not UUID_RE.match(pack_uuid):
        raise AppError("manifest header.uuid is missing or invalid")
    version_raw = header.get("version") or [1, 0, 0]
    if isinstance(version_raw, list):
        version_list = [int(x) for x in version_raw[:3]]
        while len(version_list) < 3:
            version_list.append(0)
        version = ".".join(str(x) for x in version_list)
    else:
        version = str(version_raw)
        version_list = _version_list(version)

    modules = data.get("modules") or []
    kind = _detect_kind(modules)
    encrypted = _detect_encrypted(pack_root, data)
    needs_beta = _detect_beta_apis(data, modules)
    deps: list[str] = []
    for dep in data.get("dependencies") or []:
        if isinstance(dep, dict) and dep.get("uuid"):
            deps.append(str(dep["uuid"]).lower())

    min_engine_raw = header.get("min_engine_version")
    min_engine: list[int] | None = None
    if isinstance(min_engine_raw, list) and min_engine_raw:
        min_engine = [int(x) for x in min_engine_raw[:3]]
        while len(min_engine) < 3:
            min_engine.append(0)

    return ParsedPack(
        name=name,
        pack_uuid=pack_uuid.lower(),
        version=version,
        version_list=version_list,
        kind=kind,
        encrypted=encrypted,
        needs_beta_apis=needs_beta,
        dependencies=deps,
        root=pack_root,
        min_engine_version=min_engine,
    )


def _parse_bedrock_version(raw: str | None) -> list[int] | None:
    """Parse VERSION env like ``1.26.61.1`` into ``[1, 26, 61]`` for comparisons."""

    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned or cleaned.upper() in {"LATEST", "PREVIEW"}:
        return None
    parts: list[int] = []
    for piece in cleaned.split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
        if len(parts) == 3:
            break
    if len(parts) < 2:
        return None
    while len(parts) < 3:
        parts.append(0)
    return parts


def _version_tuple_at_least(current: list[int], required: list[int]) -> bool:
    return tuple(current[:3]) >= tuple(required[:3])


def world_addon_compatibility(
    session: Session, settings: Settings, world_id: int
) -> list[dict[str, Any]]:
    """Heuristic compatibility notes for packs vs this world / Bedrock build.

    Checks encrypted Marketplace packs, Beta APIs, missing BP/RP pairs, unmet
    dependency UUIDs, and ``min_engine_version`` vs the container VERSION env.
    This is not a Mojang Marketplace cert — it flags likely breakage only.
    """

    world = session.get(World, world_id)
    if world is None:
        raise NotFoundError("World not found")

    server_version: list[int] | None = None
    try:
        info = get_docker_client(settings).version_info()
        server_version = _parse_bedrock_version(info.version_env)
    except Exception:
        server_version = None

    library_uuids = {
        a.pack_uuid.lower() for a in session.exec(select(Addon)).all() if a.pack_uuid
    }
    rows = list(
        session.exec(
            select(WorldAddon)
            .where(
                WorldAddon.world_id == world_id,
                WorldAddon.enabled.is_(True),  # type: ignore[union-attr]
            )
            .order_by(WorldAddon.load_order, WorldAddon.id)
        ).all()
    )
    warnings: list[dict[str, Any]] = []
    for row in rows:
        addon = get_addon(session, row.addon_id)
        display = addon.name
        if addon.encrypted:
            warnings.append(
                {
                    "addon_id": addon.id,
                    "addon_name": display,
                    "level": "error",
                    "code": "encrypted",
                    "message": "Encrypted / Marketplace pack — Bedrock dedicated servers cannot load it.",
                }
            )
        if addon.missing_pair:
            warnings.append(
                {
                    "addon_id": addon.id,
                    "addon_name": display,
                    "level": "warning",
                    "code": "missing_pair",
                    "message": "Missing paired behavior/resource pack in the library.",
                }
            )
        if addon.needs_beta_apis:
            warnings.append(
                {
                    "addon_id": addon.id,
                    "addon_name": display,
                    "level": "warning",
                    "code": "needs_beta_apis",
                    "message": "Requires Beta APIs / experiments — enable matching experiments in the world.",
                }
            )
        root = packs_library_dir(settings) / addon.storage_path
        if root.is_dir():
            try:
                parsed = parse_manifest(root)
            except AppError:
                parsed = None
            if parsed is not None:
                for dep in parsed.dependencies:
                    if (
                        dep.lower() not in library_uuids
                        and dep.lower() != addon.pack_uuid
                    ):
                        warnings.append(
                            {
                                "addon_id": addon.id,
                                "addon_name": display,
                                "level": "warning",
                                "code": "missing_dependency",
                                "message": f"Depends on pack UUID {dep} which is not in the library.",
                            }
                        )
                if (
                    parsed.min_engine_version
                    and server_version
                    and not _version_tuple_at_least(
                        server_version, parsed.min_engine_version
                    )
                ):
                    need = ".".join(str(x) for x in parsed.min_engine_version)
                    have = ".".join(str(x) for x in server_version)
                    warnings.append(
                        {
                            "addon_id": addon.id,
                            "addon_name": display,
                            "level": "error",
                            "code": "min_engine_version",
                            "message": (
                                f"Pack wants Bedrock ≥ {need}; server VERSION is {have}."
                            ),
                        }
                    )
    return warnings


def _resolve_pack_display_name(pack_root: Path, raw_name: str) -> str:
    """Resolve localization keys like ``pack.name`` via texts/*.lang."""

    key = raw_name.strip() if raw_name else "pack.name"
    looks_like_key = (
        (not key) or key.startswith("pack.") or key in {"name", "description"}
    )
    if not looks_like_key:
        return key

    texts_dir = pack_root / "texts"
    candidates: list[Path] = []
    if texts_dir.is_dir():
        for preferred in ("en_US.lang", "en_GB.lang", "en_US.lang.json"):
            path = texts_dir / preferred
            if path.is_file():
                candidates.append(path)
        candidates.extend(sorted(texts_dir.glob("*.lang")))

    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            lang_key, _, value = line.partition("=")
            if lang_key.strip() == key and value.strip():
                return value.strip()

    # Fall back to folder name rather than showing "pack.name" in the UI.
    folder = pack_root.name.replace("_", " ").strip()
    return folder or key or "Unnamed pack"


def _run_apply(
    session: Session,
    settings: Settings,
    *,
    operation_id: int,
    world_id: int,
    world_folder: str,
    test_mode: bool,
    started_by: int | None,
) -> None:
    from app.services import backups as backup_service
    from app.services.backups import HEALTH_TIMEOUT, _wait_for_server_healthy

    world_dir = worlds_service.world_path(settings, world_folder)
    bp_path = world_dir / "world_behavior_packs.json"
    rp_path = world_dir / "world_resource_packs.json"
    snapshot_bp = bp_path.read_text(encoding="utf-8") if bp_path.is_file() else "[]\n"
    snapshot_rp = rp_path.read_text(encoding="utf-8") if rp_path.is_file() else "[]\n"

    # Pre-addon backup of current world if valid
    try:
        worlds_service.validate_world_folder(world_dir)
        ops.append_log(session, operation_id, "Taking pre-addon backup")
        backup_service.create_backup_sync(
            session,
            settings,
            world_id=world_id,
            world_folder=world_folder,
            kind=BackupKind.PRE_ADDON,
            created_by=started_by,
            operation_id=operation_id,
        )
    except AppError as exc:
        ops.append_log(session, operation_id, f"Pre-addon backup skipped: {exc}")

    docker = get_docker_client(settings)
    was_running = docker.status().running
    applied = False
    try:
        if was_running:
            ops.append_log(session, operation_id, "Stopping Bedrock")
            try:
                console_service.send_command(settings, "stop", actor="addon")
                time.sleep(1)
            except Exception:
                pass
            docker.stop(timeout=45)

        ops.append_log(session, operation_id, "Writing merged pack JSON profiles")
        write_merged_pack_jsons(session, settings, world_folder, world_id)
        _mark_world_profile_managed(settings, world_folder)
        applied = True

        if _apply_fail_hook is not None:
            _apply_fail_hook()

        ops.append_log(session, operation_id, "Starting Bedrock")
        docker.start()
        ops.append_log(session, operation_id, "Waiting for health")
        _wait_for_server_healthy(settings, timeout=HEALTH_TIMEOUT)

        if test_mode:
            minutes = max(1, settings.addon_test_minutes)
            expires = datetime.now(UTC) + timedelta(minutes=minutes)
            ops.append_log(
                session,
                operation_id,
                f"Test mode: auto-revert in {minutes} min unless kept",
            )
            _schedule_test_revert(
                settings,
                operation_id=operation_id,
                world_id=world_id,
                world_folder=world_folder,
                snapshot_bp=snapshot_bp,
                snapshot_rp=snapshot_rp,
                expires_at=expires,
            )
        ops.append_log(session, operation_id, "Add-on apply complete")
    except Exception as exc:
        ops.append_log(session, operation_id, f"Apply failed: {exc}")
        if applied:
            ops.append_log(session, operation_id, "Rolling back pack JSON files")
            try:
                _restore_pack_jsons(settings, world_folder, snapshot_bp, snapshot_rp)
                try:
                    docker.stop(timeout=30)
                except Exception:
                    pass
                docker.start()
                try:
                    _wait_for_server_healthy(settings, timeout=HEALTH_TIMEOUT)
                except Exception as health_exc:
                    ops.append_log(
                        session, operation_id, f"Rollback health warning: {health_exc}"
                    )
                op = ops.get_operation(session, operation_id)
                op.rollback_performed = True
                session.add(op)
                session.commit()
                ops.append_log(session, operation_id, "Rollback completed")
            except Exception as rb_exc:
                ops.append_log(session, operation_id, f"Rollback failed: {rb_exc}")
                raise
        raise


def _schedule_test_revert(
    settings: Settings,
    *,
    operation_id: int,
    world_id: int,
    world_folder: str,
    snapshot_bp: str,
    snapshot_rp: str,
    expires_at: datetime,
) -> None:
    delay = max(1.0, (expires_at - datetime.now(UTC)).total_seconds())

    def _fire() -> None:
        try:
            with Session(get_engine()) as session:
                revert_test_now(session, settings, world_id=world_id, user_id=None)
        except AppError as exc:
            # Switch/backup holds the lock — retry soon instead of fighting Docker.
            if (
                "deferring" in str(exc).lower()
                or "another operation" in str(exc).lower()
            ):
                logger.info(
                    "Deferring add-on test revert for world %s: %s", world_id, exc
                )
                _schedule_test_revert(
                    settings,
                    operation_id=operation_id,
                    world_id=world_id,
                    world_folder=world_folder,
                    snapshot_bp=snapshot_bp,
                    snapshot_rp=snapshot_rp,
                    expires_at=datetime.now(UTC) + timedelta(seconds=30),
                )
            else:
                logger.info(
                    "Add-on test revert skipped for world %s: %s", world_id, exc
                )
        except Exception:
            logger.exception("Auto-revert failed for world %s", world_id)

    timer = threading.Timer(delay, _fire)
    timer.daemon = True
    pending = PendingTest(
        operation_id=operation_id,
        world_id=world_id,
        world_folder=world_folder,
        snapshot_bp=snapshot_bp,
        snapshot_rp=snapshot_rp,
        expires_at=expires_at,
        timer=timer,
    )
    with _pending_lock:
        old = _pending_tests.pop(world_id, None)
        if old:
            old.timer.cancel()
        _pending_tests[world_id] = pending
    timer.start()


def _restore_pack_jsons(
    settings: Settings, world_folder: str, snapshot_bp: str, snapshot_rp: str
) -> None:
    world_dir = worlds_service.world_path(settings, world_folder)
    _write_text(
        world_dir / "world_behavior_packs.json",
        snapshot_bp if snapshot_bp.endswith("\n") else snapshot_bp + "\n",
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )
    _write_text(
        world_dir / "world_resource_packs.json",
        snapshot_rp if snapshot_rp.endswith("\n") else snapshot_rp + "\n",
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )


def _sync_pack_into_data(settings: Settings, addon: Addon) -> None:
    src = packs_library_dir(settings) / addon.storage_path
    if not src.is_dir():
        raise AppError(f"Pack storage missing for {addon.name}")
    dest_root = (
        behavior_packs_dir(settings)
        if addon.kind == AddonKind.BEHAVIOR
        else resource_packs_dir(settings)
    )
    safe_name = f"{addon.name}-{addon.pack_uuid[:8]}".replace("/", "_")[:80]
    dest = dest_root / safe_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, symlinks=False)
    _chown_tree(dest, settings.bedrock_uid, settings.bedrock_gid)


def _read_embedded_pack_refs(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for child in sorted(folder.iterdir()):
        if not child.is_dir():
            continue
        manifest = child / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            parsed = parse_manifest(child)
        except AppError:
            continue
        entries.append({"pack_id": parsed.pack_uuid, "version": parsed.version_list})
    return entries


def _discover_pack_roots(extracted: Path) -> list[Path]:
    roots: list[Path] = []
    for manifest in extracted.rglob("manifest.json"):
        roots.append(manifest.parent)
    # Prefer shallowest unique roots (avoid nested duplicates)
    roots.sort(key=lambda p: len(p.parts))
    filtered: list[Path] = []
    for root in roots:
        if any(root.is_relative_to(prev) and root != prev for prev in filtered):
            continue
        filtered.append(root)
    return filtered


def _detect_kind(modules: list[Any]) -> AddonKind:
    types = {str(m.get("type", "")).lower() for m in modules if isinstance(m, dict)}
    if "resources" in types:
        return AddonKind.RESOURCE
    if "data" in types or "script" in types:
        return AddonKind.BEHAVIOR
    # Default: behavior if script-like else resource
    return AddonKind.BEHAVIOR


def _detect_encrypted(pack_root: Path, manifest: dict[str, Any]) -> bool:
    if manifest.get("content_key") or (manifest.get("header") or {}).get("content_key"):
        return True
    contents = pack_root / "contents.json"
    if contents.is_file():
        try:
            data = json.loads(contents.read_text(encoding="utf-8"))
            if data.get("content_key"):
                return True
            for entry in data.get("content") or []:
                if isinstance(entry, dict) and entry.get("key"):
                    return True
        except json.JSONDecodeError:
            pass
    # Marketplace packs often ship only signatures without readable assets
    if (pack_root / "signatures.json").is_file() and not any(pack_root.rglob("*.json")):
        return True
    return False


def _detect_beta_apis(manifest: dict[str, Any], modules: list[Any]) -> bool:
    for mod in modules:
        if not isinstance(mod, dict):
            continue
        if str(mod.get("type", "")).lower() == "script":
            lang = str(mod.get("language", "")).lower()
            if lang in {"javascript", "js"}:
                # Script modules on BDS typically need Beta APIs experiment
                return True
    for dep in manifest.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        module_name = str(dep.get("module_name") or "")
        if (
            module_name.startswith("@minecraft/")
            and "beta" in str(dep.get("version", "")).lower()
        ):
            return True
    return False


def _refresh_pairing(session: Session, settings: Settings | None = None) -> None:
    """Pair BP/RP halves and flag only *unmet* behavior-pack dependencies.

    Standalone resource packs (furniture, cars, textures) are normal and must
    not show "Missing behavior pack" unless their manifest depends on a BP
    UUID that is not in the library.
    """

    addons = list(session.exec(select(Addon)).all())
    by_uuid: dict[str, list[Addon]] = {}
    for addon in addons:
        by_uuid.setdefault(addon.pack_uuid.lower(), []).append(addon)

    paired_ids: set[int] = set()

    # 1) Pair opposite kinds that share source sha256 (same .mcaddon upload).
    by_sha: dict[str, list[Addon]] = {}
    for addon in addons:
        by_sha.setdefault(addon.sha256, []).append(addon)
    for group in by_sha.values():
        bps = [a for a in group if a.kind == AddonKind.BEHAVIOR]
        rps = [a for a in group if a.kind == AddonKind.RESOURCE]
        if len(bps) == 1 and len(rps) == 1 and bps[0].id and rps[0].id:
            bps[0].pair_addon_id = rps[0].id
            rps[0].pair_addon_id = bps[0].id
            bps[0].missing_pair = False
            rps[0].missing_pair = False
            session.add(bps[0])
            session.add(rps[0])
            paired_ids.add(bps[0].id)
            paired_ids.add(rps[0].id)

    # 2) Pair via manifest dependency UUIDs when settings are available.
    if settings is not None:
        for addon in addons:
            if addon.id in paired_ids or addon.kind != AddonKind.RESOURCE:
                continue
            for dep in _addon_dependency_uuids(settings, addon):
                candidates = [
                    a
                    for a in by_uuid.get(dep, [])
                    if a.kind == AddonKind.BEHAVIOR and a.id is not None
                ]
                if len(candidates) != 1:
                    continue
                bp = candidates[0]
                addon.pair_addon_id = bp.id
                bp.pair_addon_id = addon.id
                addon.missing_pair = False
                bp.missing_pair = False
                session.add(addon)
                session.add(bp)
                if addon.id is not None:
                    paired_ids.add(addon.id)
                paired_ids.add(bp.id)
                break

    for addon in addons:
        if addon.id in paired_ids:
            continue
        if addon.pair_addon_id:
            pair = session.get(Addon, addon.pair_addon_id)
            if pair and pair.kind != addon.kind:
                addon.missing_pair = False
                session.add(addon)
                continue
            addon.pair_addon_id = None

        # Only warn when a resource pack *declares* a BP dependency we lack.
        if addon.kind == AddonKind.RESOURCE and settings is not None:
            deps = _addon_dependency_uuids(settings, addon)
            bp_uuids = {
                a.pack_uuid.lower() for a in addons if a.kind == AddonKind.BEHAVIOR
            }
            addon.missing_pair = bool(deps) and any(d not in bp_uuids for d in deps)
        else:
            addon.missing_pair = False
        session.add(addon)


def _addon_dependency_uuids(settings: Settings, addon: Addon) -> list[str]:
    root = packs_library_dir(settings) / addon.storage_path
    if not root.is_dir():
        return []
    try:
        return list(parse_manifest(root).dependencies)
    except AppError:
        return []


def _version_list(version: str) -> list[int]:
    parts = []
    for piece in version.split(".")[:3]:
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts


def _write_json(path: Path, data: Any, *, uid: int, gid: int) -> None:
    text = json.dumps(data, indent=2) + "\n"
    _write_text(path, text, uid=uid, gid=gid)


def _write_text(path: Path, text: str, *, uid: int, gid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".mf-packjson.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chown(tmp_path, uid, gid)
        except PermissionError:
            pass
        tmp_path.replace(path)
        try:
            os.chown(path, uid, gid)
        except PermissionError:
            pass
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    for root, dirs, files in os.walk(path):
        try:
            os.chown(root, uid, gid)
        except PermissionError:
            pass
        for name in dirs + files:
            try:
                os.chown(os.path.join(root, name), uid, gid)
            except PermissionError:
                pass


def set_texturepack_required(
    session: Session,
    settings: Settings,
    *,
    required: bool,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> dict[str, str]:
    """Toggle texturepack-required in server.properties (admin)."""

    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    values = server_props.write_properties(
        settings, {"texturepack-required": "true" if required else "false"}
    )
    record_audit(
        session,
        action="addon.texturepack_required",
        user_id=user_id,
        details={"required": required},
        ip=ip,
    )
    session.commit()
    return values
