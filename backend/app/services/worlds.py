"""World library: scan, create, import, export, rename, clone, delete."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.models.user import UserRole
from app.models.world import World
from app.services import server_props
from app.services.archive_safety import (
    copy_tree,
    dir_size,
    extract_zip_safe,
)
from app.services.audit import record_audit
from app.services.paths import resolve_under

logger = logging.getLogger(__name__)

FOLDER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,126}$")
IMPORT_WARN_PLAYER_DATA = (
    "Player data from single-player may not transfer to a dedicated server."
)
IMPORT_WARN_EMBEDDED = "This world includes embedded behavior/resource packs."


def worlds_root(settings: Settings) -> Path:
    return resolve_under(settings.data_dir, "worlds")


def world_path(settings: Settings, folder_name: str) -> Path:
    """Resolve a world folder under /data/worlds.

    Raises:
        ForbiddenError: path escape.
        AppError: empty/invalid folder name.
    """

    cleaned = normalize_folder_name(folder_name)
    return resolve_under(worlds_root(settings), cleaned)


def normalize_folder_name(folder_name: str) -> str:
    cleaned = folder_name.strip()
    if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise AppError("Invalid world folder name")
    if not FOLDER_RE.match(cleaned):
        raise AppError(
            "World folder name must start with a letter/number and use "
            "only letters, numbers, spaces, dots, underscores, or hyphens"
        )
    return cleaned


def active_level_name(settings: Settings) -> str:
    """Return level-name from server.properties.

    Raises:
        AppError: if missing.
    """

    props = server_props.read_properties(settings)
    name = (props.get("level-name") or "").strip()
    if not name:
        raise AppError("level-name is not set in server.properties")
    return name


def ensure_world_for_folder(
    session: Session, settings: Settings, folder_name: str, *, mark_active: bool = False
) -> World:
    """Get or create a World row for a folder on disk."""

    folder = normalize_folder_name(folder_name)
    existing = session.exec(select(World).where(World.folder_name == folder)).first()
    path = world_path(settings, folder)
    size = dir_size(path) if path.is_dir() else 0
    if existing:
        existing.size_bytes = size
        if mark_active:
            _clear_active(session)
            existing.is_active = True
            existing.last_played_at = datetime.now(UTC)
        session.add(existing)
        session.flush()
        return existing

    if mark_active:
        _clear_active(session)
    world = World(
        display_name=folder,
        folder_name=folder,
        size_bytes=size,
        is_active=mark_active,
        last_played_at=datetime.now(UTC) if mark_active else None,
    )
    session.add(world)
    session.flush()
    return world


def ensure_active_world(session: Session, settings: Settings) -> World:
    """Ensure a World row exists for the current level-name and mark it active."""

    folder = active_level_name(settings)
    path = world_path(settings, folder)
    if not path.is_dir():
        raise NotFoundError(f"Active world folder not found: {folder}")
    return ensure_world_for_folder(session, settings, folder, mark_active=True)


def get_world(session: Session, world_id: int) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise NotFoundError("World not found")
    return world


def validate_world_folder(path: Path) -> None:
    """Check a world directory looks like Bedrock data.

    Raises:
        AppError: if level.dat or db/ is missing.
    """

    if not path.is_dir():
        raise AppError("World folder does not exist")
    if not (path / "level.dat").is_file():
        raise AppError("World is missing level.dat")
    if not (path / "db").is_dir():
        raise AppError("World is missing db/")


def world_warnings(path: Path) -> list[str]:
    """Return import/library warnings for a world folder."""

    warnings: list[str] = []
    if (path / "behavior_packs").is_dir() or (path / "resource_packs").is_dir():
        warnings.append(IMPORT_WARN_EMBEDDED)
    # Presence of local player data is common after single-player export
    if (path / "db").is_dir():
        warnings.append(IMPORT_WARN_PLAYER_DATA)
    return warnings


def sync_from_disk(session: Session, settings: Settings) -> list[World]:
    """Scan /data/worlds and upsert World rows. Marks active from level-name."""

    root = worlds_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    active: str | None = None
    try:
        active = active_level_name(settings)
    except AppError:
        active = None

    on_disk: set[str] = set()
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        try:
            folder = normalize_folder_name(child.name)
        except AppError:
            continue
        on_disk.add(folder)
        ensure_world_for_folder(
            session, settings, folder, mark_active=(folder == active)
        )

    # Deactivate rows whose folders vanished (keep row for history of backups)
    for world in session.exec(select(World)).all():
        if world.folder_name not in on_disk:
            world.is_active = False
            world.size_bytes = 0
            session.add(world)
        elif active and world.folder_name == active:
            world.is_active = True
            session.add(world)
        elif active:
            world.is_active = False
            session.add(world)

    session.commit()
    return list_worlds(session, settings)


def list_worlds(session: Session, settings: Settings) -> list[World]:
    """Return worlds sorted active-first then name. Refreshes sizes from disk."""

    worlds = list(session.exec(select(World).order_by(World.display_name)).all())
    for world in worlds:
        path = world_path(settings, world.folder_name)
        if path.is_dir():
            world.size_bytes = dir_size(path)
            session.add(world)
    session.commit()
    worlds.sort(key=lambda w: (not w.is_active, w.display_name.lower()))
    return worlds


def world_to_dict(settings: Settings, world: World) -> dict[str, Any]:
    path = world_path(settings, world.folder_name)
    warnings: list[str] = []
    valid = False
    if path.is_dir():
        try:
            validate_world_folder(path)
            valid = True
        except AppError:
            valid = False
        warnings = world_warnings(path)
    icon_present = (path / "world_icon.jpeg").is_file() or (
        path / "world_icon.jpg"
    ).is_file()
    return {
        "id": world.id,
        "display_name": world.display_name,
        "folder_name": world.folder_name,
        "description": world.description,
        "gamemode": world.gamemode,
        "difficulty": world.difficulty,
        "seed": world.seed,
        "size_bytes": world.size_bytes,
        "is_active": world.is_active,
        "created_at": world.created_at.isoformat() if world.created_at else None,
        "last_played_at": (
            world.last_played_at.isoformat() if world.last_played_at else None
        ),
        "needs_experiments": world.needs_experiments,
        "valid": valid,
        "on_disk": path.is_dir(),
        "icon_present": icon_present,
        "warnings": warnings,
    }


def create_world(
    session: Session,
    settings: Settings,
    *,
    display_name: str,
    folder_name: str | None,
    description: str | None,
    gamemode: str | None,
    difficulty: str | None,
    seed: str | None,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> World:
    """Create a new empty world folder and DB row (admin).

    Bedrock generates level data the first time this world is switched to
    if level.dat is still missing — create leaves a placeholder folder.
    """

    _require_admin(role)
    name = display_name.strip()
    if not name:
        raise AppError("Display name is required")
    folder = normalize_folder_name(folder_name or name)
    path = world_path(settings, folder)
    if path.exists():
        raise AppError(f"World folder already exists: {folder}")
    existing = session.exec(select(World).where(World.folder_name == folder)).first()
    if existing:
        raise AppError(f"World already registered: {folder}")

    path.mkdir(parents=True, exist_ok=False)
    (path / "db").mkdir()
    # Placeholder so the folder is recognizable; real level.dat comes from
    # Bedrock on first start, or from import/clone.
    (path / ".mineforge-new").write_text(
        f"seed={seed or ''}\ngamemode={gamemode or ''}\ndifficulty={difficulty or ''}\n",
        encoding="utf-8",
    )
    _chown_tree(path, settings.bedrock_uid, settings.bedrock_gid)

    world = World(
        display_name=name,
        folder_name=folder,
        description=description,
        gamemode=gamemode,
        difficulty=difficulty,
        seed=seed,
        size_bytes=dir_size(path),
        is_active=False,
    )
    session.add(world)
    record_audit(
        session,
        action="world.create",
        user_id=user_id,
        target=folder,
        ip=ip,
    )
    session.commit()
    session.refresh(world)
    return world


def import_mcworld(
    session: Session,
    settings: Settings,
    *,
    upload_path: Path,
    display_name: str | None,
    folder_name: str | None,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> tuple[World, list[str]]:
    """Import a `.mcworld` zip into /data/worlds (admin).

    Raises:
        AppError: invalid archive, collisions, or missing level.dat.
    """

    _require_admin(role)
    if not upload_path.is_file():
        raise AppError("Upload file missing")
    if upload_path.suffix.lower() not in {".mcworld", ".zip"}:
        raise AppError("Only .mcworld or .zip uploads are supported")

    staging = Path(
        tempfile.mkdtemp(prefix="mf-mcworld-", dir=str(settings.app_data_dir))
    )
    try:
        extract_zip_safe(upload_path, staging)
        source = _find_world_root(staging)
        validate_world_folder(source)
        warnings = world_warnings(source)

        folder = normalize_folder_name(
            folder_name or display_name or source.name or "ImportedWorld"
        )
        dest = world_path(settings, folder)
        if dest.exists():
            raise AppError(f"World folder already exists: {folder}")

        copy_tree(source, dest)
        _chown_tree(dest, settings.bedrock_uid, settings.bedrock_gid)

        world = World(
            display_name=(display_name or folder).strip() or folder,
            folder_name=folder,
            size_bytes=dir_size(dest),
            is_active=False,
            needs_experiments=False,
        )
        session.add(world)
        record_audit(
            session,
            action="world.import",
            user_id=user_id,
            target=folder,
            details={"warnings": warnings},
            ip=ip,
        )
        session.commit()
        session.refresh(world)
        return world, warnings
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def export_world(settings: Settings, world: World) -> Path:
    """Zip a world folder to a temp `.mcworld` and return the path.

    Caller must delete the temp file after sending.
    """

    path = world_path(settings, world.folder_name)
    validate_world_folder(path)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"mf-export-{world.folder_name}-",
        suffix=".mcworld",
        dir=str(settings.app_data_dir),
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(path):
                for name in files:
                    full = Path(root) / name
                    arc = full.relative_to(path).as_posix()
                    zf.write(full, arcname=arc)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise AppError(f"Export failed: {exc}") from exc
    return tmp_path


def rename_world(
    session: Session,
    settings: Settings,
    *,
    world_id: int,
    display_name: str | None,
    folder_name: str | None,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> World:
    """Rename display name and/or folder (admin). Active world folder rename
    also updates level-name when the server is stopped or via properties.
    """

    _require_admin(role)
    world = get_world(session, world_id)
    old_folder = world.folder_name
    if display_name is not None:
        name = display_name.strip()
        if not name:
            raise AppError("Display name cannot be empty")
        world.display_name = name

    if folder_name is not None:
        new_folder = normalize_folder_name(folder_name)
        if new_folder != old_folder:
            if world.is_active:
                raise AppError(
                    "Stop and switch away before renaming the active world folder"
                )
            src = world_path(settings, old_folder)
            dest = world_path(settings, new_folder)
            if dest.exists():
                raise AppError(f"Target folder already exists: {new_folder}")
            if src.exists():
                src.rename(dest)
            world.folder_name = new_folder

    session.add(world)
    record_audit(
        session,
        action="world.rename",
        user_id=user_id,
        target=world.folder_name,
        details={"from": old_folder},
        ip=ip,
    )
    session.commit()
    session.refresh(world)
    return world


def clone_world(
    session: Session,
    settings: Settings,
    *,
    world_id: int,
    new_folder_name: str,
    display_name: str | None,
    user_id: int,
    role: UserRole,
    ip: str | None,
) -> World:
    """Deep-copy a world folder to a new name (admin)."""

    _require_admin(role)
    source = get_world(session, world_id)
    src_path = world_path(settings, source.folder_name)
    validate_world_folder(src_path)
    folder = normalize_folder_name(new_folder_name)
    dest = world_path(settings, folder)
    if dest.exists():
        raise AppError(f"World folder already exists: {folder}")
    copy_tree(src_path, dest)
    _chown_tree(dest, settings.bedrock_uid, settings.bedrock_gid)

    world = World(
        display_name=(display_name or folder).strip() or folder,
        folder_name=folder,
        description=source.description,
        gamemode=source.gamemode,
        difficulty=source.difficulty,
        seed=source.seed,
        size_bytes=dir_size(dest),
        is_active=False,
        needs_experiments=source.needs_experiments,
    )
    session.add(world)
    record_audit(
        session,
        action="world.clone",
        user_id=user_id,
        target=folder,
        details={"from": source.folder_name},
        ip=ip,
    )
    session.commit()
    session.refresh(world)
    return world


def delete_world(
    session: Session,
    settings: Settings,
    *,
    world_id: int,
    user_id: int,
    role: UserRole,
    ip: str | None,
    take_backup: bool = True,
) -> None:
    """Delete a world folder and DB row (admin). Refuses to delete the active world."""

    _require_admin(role)
    world = get_world(session, world_id)
    if world.is_active:
        raise AppError("Cannot delete the active world; switch away first")
    folder = world.folder_name
    path = world_path(settings, folder)

    if take_backup and path.is_dir():
        try:
            validate_world_folder(path)
            from app.models.backup import BackupKind
            from app.services import backups as backup_service

            backup_service.create_backup_sync(
                session,
                settings,
                world_id=world.id,  # type: ignore[arg-type]
                world_folder=folder,
                kind=BackupKind.MANUAL,
                created_by=user_id,
            )
        except AppError as exc:
            logger.warning("Pre-delete backup skipped: %s", exc)

    session.delete(world)
    record_audit(
        session,
        action="world.delete",
        user_id=user_id,
        target=folder,
        ip=ip,
    )
    session.commit()
    if path.is_dir():
        shutil.rmtree(path)


def _find_world_root(extracted: Path) -> Path:
    if (extracted / "level.dat").is_file():
        return extracted
    candidates = [p for p in extracted.rglob("level.dat") if p.is_file()]
    if not candidates:
        raise AppError("Imported archive has no level.dat")
    # Prefer shallowest
    candidates.sort(key=lambda p: len(p.parts))
    return candidates[0].parent


def _require_admin(role: UserRole) -> None:
    if role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")


def _clear_active(session: Session) -> None:
    for world in session.exec(select(World).where(World.is_active.is_(True))).all():  # type: ignore[union-attr]
        world.is_active = False
        session.add(world)


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
