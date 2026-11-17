"""Allowlist and operator (permissions.json) management."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.services.paths import resolve_under

logger = logging.getLogger(__name__)


def allowlist_path(settings: Settings) -> Path:
    return resolve_under(settings.data_dir, "allowlist.json")


def permissions_path(settings: Settings) -> Path:
    return resolve_under(settings.data_dir, "permissions.json")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppError(f"Invalid JSON in {path.name}", status_code=500) from exc
    if not isinstance(data, list):
        raise AppError(f"{path.name} must be a JSON array", status_code=500)
    return [item for item in data if isinstance(item, dict)]


def _atomic_write_json(
    path: Path, payload: list[dict[str, Any]], *, uid: int, gid: int
) -> None:
    """Atomically rewrite a JSON list file under /data.

    Raises:
        AppError: if the data directory is not writable (common when the app
            UID does not match the Bedrock data owner).
    """

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2) + "\n"
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
        tmp_path = Path(tmp_name)
    except OSError as exc:
        raise AppError(
            f"Cannot write {path.name}: {exc}. "
            "MineForge must run as the same UID/GID that owns the Bedrock data "
            "directory (set BEDROCK_UID/BEDROCK_GID or MINEFORGE_RUNTIME_UID/GID).",
            status_code=500,
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chown(tmp_path, uid, gid)
        except PermissionError:
            logger.warning("Could not chown %s", tmp_path)
        tmp_path.replace(path)
        try:
            os.chown(path, uid, gid)
        except PermissionError:
            logger.warning("Could not chown %s", path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise AppError(
            f"Failed to update {path.name}: {exc}. "
            "Check that /data is writable by the MineForge runtime user.",
            status_code=500,
        ) from exc
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def list_allowlist(settings: Settings) -> list[dict[str, Any]]:
    """Return allowlist entries."""

    return _read_json_list(allowlist_path(settings))


def add_allowlist_entry(
    settings: Settings, *, name: str, xuid: str | None = None
) -> list[dict[str, Any]]:
    """Add a gamertag to the allowlist.

    Raises:
        ConflictError: if the name already exists.
    """

    name = name.strip()
    if not name:
        raise AppError("Gamertag is required")
    entries = list_allowlist(settings)
    if any(str(e.get("name", "")).lower() == name.lower() for e in entries):
        raise ConflictError("Gamertag already on allowlist")
    entry: dict[str, Any] = {"name": name, "ignoresPlayerLimit": False}
    if xuid:
        entry["xuid"] = xuid.strip()
    entries.append(entry)
    _atomic_write_json(
        allowlist_path(settings),
        entries,
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )
    return entries


def remove_allowlist_entry(settings: Settings, name: str) -> list[dict[str, Any]]:
    """Remove a gamertag from the allowlist.

    Raises:
        NotFoundError: if missing.
    """

    name = name.strip()
    entries = list_allowlist(settings)
    next_entries = [
        e for e in entries if str(e.get("name", "")).lower() != name.lower()
    ]
    if len(next_entries) == len(entries):
        raise NotFoundError("Gamertag not on allowlist")
    _atomic_write_json(
        allowlist_path(settings),
        next_entries,
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )
    return next_entries


def list_ops(settings: Settings) -> list[dict[str, Any]]:
    """Return permissions.json operator/member entries."""

    return _read_json_list(permissions_path(settings))


def set_permission(
    settings: Settings,
    *,
    xuid: str,
    permission: str,
    name: str | None = None,
) -> list[dict[str, Any]]:
    """Upsert a permissions.json entry by XUID.

    Raises:
        AppError: invalid permission level.
    """

    permission = permission.strip().lower()
    if permission not in {"visitor", "member", "operator"}:
        raise AppError("permission must be visitor, member, or operator")
    xuid = xuid.strip()
    if not xuid:
        raise AppError("xuid is required")

    entries = list_ops(settings)
    found = False
    for entry in entries:
        if str(entry.get("xuid", "")) == xuid:
            entry["permission"] = permission
            if name:
                entry["name"] = name
            found = True
            break
    if not found:
        item: dict[str, Any] = {"xuid": xuid, "permission": permission}
        if name:
            item["name"] = name
        entries.append(item)

    _atomic_write_json(
        permissions_path(settings),
        entries,
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )
    return entries


def remove_permission(settings: Settings, xuid: str) -> list[dict[str, Any]]:
    """Remove a permissions entry by XUID."""

    xuid = xuid.strip()
    entries = list_ops(settings)
    next_entries = [e for e in entries if str(e.get("xuid", "")) != xuid]
    if len(next_entries) == len(entries):
        raise NotFoundError("Permission entry not found")
    _atomic_write_json(
        permissions_path(settings),
        next_entries,
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )
    return next_entries
