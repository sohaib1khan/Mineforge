"""Safe read/write of Bedrock server.properties (whitelisted keys only)."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError
from app.services.paths import resolve_under

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PropertySpec:
    key: str
    description: str
    value_type: str  # string | int | bool | enum
    allowed_values: tuple[str, ...] | None = None


# Keys MineForge may edit. level-name is owned by world switching (Phase 4)
# but readable here; treat as read-only in the editor API.
EDITABLE_PROPERTIES: dict[str, PropertySpec] = {
    "server-name": PropertySpec(
        "server-name", "Display name shown in the server list.", "string"
    ),
    "gamemode": PropertySpec(
        "gamemode",
        "Default game mode. Also written into the active world's level.dat. "
        "Turn on force-gamemode so joining players use it.",
        "enum",
        ("survival", "creative", "adventure"),
    ),
    "difficulty": PropertySpec(
        "difficulty",
        "World difficulty. Written to server.properties and the active world's "
        "level.dat (server restarts briefly when either changes).",
        "enum",
        ("peaceful", "easy", "normal", "hard"),
    ),
    "force-gamemode": PropertySpec(
        "force-gamemode",
        "Force joining players onto the gamemode above (needed for existing players).",
        "bool",
    ),
    "allow-cheats": PropertySpec(
        "allow-cheats", "Allow cheats / commands for operators.", "bool"
    ),
    "max-players": PropertySpec("max-players", "Maximum concurrent players.", "int"),
    "online-mode": PropertySpec(
        "online-mode", "Require Xbox Live authentication.", "bool"
    ),
    "allow-list": PropertySpec(
        "allow-list", "Only allowlisted players may join.", "bool"
    ),
    "view-distance": PropertySpec(
        "view-distance", "Client view distance (chunks).", "int"
    ),
    "tick-distance": PropertySpec(
        "tick-distance", "Simulation distance (chunks).", "int"
    ),
    "player-idle-timeout": PropertySpec(
        "player-idle-timeout", "Minutes before idle kick (0 disables).", "int"
    ),
    "max-threads": PropertySpec(
        "max-threads", "Worker thread limit (0 = auto).", "int"
    ),
    "texturepack-required": PropertySpec(
        "texturepack-required", "Force clients to download the resource pack.", "bool"
    ),
    "default-player-permission-level": PropertySpec(
        "default-player-permission-level",
        "Default permission for new players.",
        "enum",
        ("visitor", "member", "operator"),
    ),
    "server-port": PropertySpec(
        "server-port", "TCP signaling port (NetherNet).", "int"
    ),
}

READONLY_PROPERTIES: dict[str, PropertySpec] = {
    "level-name": PropertySpec(
        "level-name",
        "Active world folder (changed via Worlds / switch).",
        "string",
    ),
    "server-udp-ports": PropertySpec(
        "server-udp-ports",
        "UDP game traffic advertisement (Network panel).",
        "string",
    ),
}


def properties_path(settings: Settings) -> Path:
    return resolve_under(settings.data_dir, "server.properties")


def parse_properties(text: str) -> dict[str, str]:
    """Parse server.properties text into a key/value map."""

    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def read_properties(settings: Settings) -> dict[str, str]:
    """Read server.properties from the Bedrock data dir.

    Raises:
        AppError: if the file is missing or unreadable.
    """

    path = properties_path(settings)
    if not path.is_file():
        raise AppError("server.properties not found", status_code=404)
    return parse_properties(path.read_text(encoding="utf-8"))


def validate_updates(updates: dict[str, str]) -> dict[str, str]:
    """Validate and normalize whitelisted property updates.

    Raises:
        ForbiddenError: unknown keys.
        AppError: invalid values.
    """

    cleaned: dict[str, str] = {}
    for key, value in updates.items():
        if key in READONLY_PROPERTIES:
            raise ForbiddenError(f"Property '{key}' is read-only")
        spec = EDITABLE_PROPERTIES.get(key)
        if spec is None:
            raise ForbiddenError(f"Property '{key}' is not editable")
        val = value.strip()
        if spec.value_type == "bool":
            if val.lower() not in {"true", "false"}:
                raise AppError(f"{key} must be true or false")
            val = val.lower()
        elif spec.value_type == "int":
            try:
                int(val)
            except ValueError as exc:
                raise AppError(f"{key} must be an integer") from exc
        elif spec.value_type == "enum":
            assert spec.allowed_values is not None
            if val not in spec.allowed_values:
                raise AppError(
                    f"{key} must be one of: {', '.join(spec.allowed_values)}"
                )
        cleaned[key] = val
    return cleaned


def write_properties(
    settings: Settings,
    updates: dict[str, str],
    *,
    preserve_unknown: bool = True,
) -> dict[str, str]:
    """Merge validated updates into server.properties atomically.

    Preserves comments and unknown keys when possible by rewriting the file
    from the existing key set.

    Raises:
        AppError / ForbiddenError from validation or I/O failures.
    """

    validated = validate_updates(updates)
    return _write_raw(settings, validated, preserve_unknown=preserve_unknown)


def write_managed(
    settings: Settings,
    updates: dict[str, str],
    *,
    preserve_unknown: bool = True,
) -> dict[str, str]:
    """Write keys MineForge owns internally (e.g. level-name during switch).

    Not exposed via the public properties API. Still rejects unknown keys
    outside EDITABLE + READONLY catalogs.

    Raises:
        AppError / ForbiddenError on invalid keys/values.
    """

    cleaned: dict[str, str] = {}
    for key, value in updates.items():
        spec = EDITABLE_PROPERTIES.get(key) or READONLY_PROPERTIES.get(key)
        if spec is None:
            raise ForbiddenError(f"Property '{key}' is not managed by MineForge")
        val = value.strip()
        if spec.value_type == "bool":
            if val.lower() not in {"true", "false"}:
                raise AppError(f"{key} must be true or false")
            val = val.lower()
        elif spec.value_type == "int":
            try:
                int(val)
            except ValueError as exc:
                raise AppError(f"{key} must be an integer") from exc
        elif spec.value_type == "enum":
            assert spec.allowed_values is not None
            if val not in spec.allowed_values:
                raise AppError(
                    f"{key} must be one of: {', '.join(spec.allowed_values)}"
                )
        cleaned[key] = val
    return _write_raw(settings, cleaned, preserve_unknown=preserve_unknown)


def snapshot_properties_text(settings: Settings) -> str:
    """Return raw server.properties text for rollback."""

    path = properties_path(settings)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def restore_properties_text(settings: Settings, text: str) -> None:
    """Overwrite server.properties from a snapshot string."""

    path = properties_path(settings)
    _atomic_write(
        path,
        text if text.endswith("\n") else text + "\n",
        uid=settings.bedrock_uid,
        gid=settings.bedrock_gid,
    )


def _write_raw(
    settings: Settings,
    validated: dict[str, str],
    *,
    preserve_unknown: bool = True,
) -> dict[str, str]:
    path = properties_path(settings)
    if path.is_file():
        current = parse_properties(path.read_text(encoding="utf-8"))
        original_text = path.read_text(encoding="utf-8")
    else:
        current = {}
        original_text = ""

    current.update(validated)

    seen: set[str] = set()
    lines: list[str] = []
    for raw in original_text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(raw)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in validated:
            lines.append(f"{key}={validated[key]}")
            seen.add(key)
        elif preserve_unknown:
            lines.append(raw)
            seen.add(key)
        else:
            lines.append(raw)
            seen.add(key)

    for key, value in validated.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    content = "\n".join(lines) + "\n"
    _atomic_write(path, content, uid=settings.bedrock_uid, gid=settings.bedrock_gid)
    return current


def _atomic_write(path: Path, content: str, *, uid: int, gid: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".server.props.")
        tmp_path = Path(tmp_name)
    except OSError as exc:
        raise AppError(
            f"Cannot write server.properties: {exc}. "
            "MineForge must run as the same UID/GID that owns the Bedrock data "
            "directory (set BEDROCK_UID/BEDROCK_GID).",
            status_code=500,
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chown(tmp_path, uid, gid)
        except PermissionError:
            logger.warning("Could not chown %s to %s:%s", tmp_path, uid, gid)
        tmp_path.replace(path)
        try:
            os.chown(path, uid, gid)
        except PermissionError:
            logger.warning("Could not chown %s to %s:%s", path, uid, gid)
    except OSError as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise AppError(
            f"Failed to update server.properties: {exc}",
            status_code=500,
        ) from exc
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def property_catalog() -> list[dict[str, object]]:
    """Return editable + readonly property metadata for the UI."""

    items: list[dict[str, object]] = []
    for spec in EDITABLE_PROPERTIES.values():
        items.append(
            {
                "key": spec.key,
                "description": spec.description,
                "value_type": spec.value_type,
                "allowed_values": (
                    list(spec.allowed_values) if spec.allowed_values else None
                ),
                "editable": True,
            }
        )
    for spec in READONLY_PROPERTIES.values():
        items.append(
            {
                "key": spec.key,
                "description": spec.description,
                "value_type": spec.value_type,
                "allowed_values": None,
                "editable": False,
            }
        )
    return items
