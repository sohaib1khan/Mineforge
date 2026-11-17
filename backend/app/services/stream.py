"""OBS → MediaMTX stream status, publish auth, key rotation, and HLS proxy.

Business logic for the Stream page. Routes validate input, call these
functions, and return responses. Stream keys are stored only as argon2 hashes.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.security import (
    constant_time_equals,
    generate_token,
    hash_password,
    verify_password,
)
from app.models.stream import StreamSession, StreamSettings
from app.models.user import User, UserRole
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

STREAM_PATH = "live"
STATUS_CACHE_SECONDS = 3.0
HLS_ALLOWED_SUFFIXES = (".m3u8", ".ts", ".mp4", ".m4s", ".cmfv", ".cmfa")
OBS_NOTES = [
    "OBS → Settings → Stream: Service must be Custom (not Twitch/YouTube).",
    "Server = the RTMP URL below (rtmp://…:1935/live) — not your https:// website URL.",
    "Stream Key = the OBS stream-key field below (?user=publish&pass=…). Paste that whole string.",
    "Cloudflare: do NOT use an orange-cloud hostname for RTMP. Create a DNS-only (grey cloud) "
    "A/AAAA record (e.g. rtmp.yourdomain) pointing at the server public IP, set "
    "MINEFORGE_STREAM_RTMP_HOST to that name, and forward TCP 1935 to the host.",
    "Forward TCP 1935 on the router/firewall. RTMP is not encrypted — use a strong key.",
    "Output: 1280×720 or 1920×1080, 30 fps, CBR 2500–4500 kbps, keyframe interval 2 s.",
    "Encoder: NVENC / VAAPI / QSV if available, else x264 veryfast. Audio: AAC 128–160 kbps, 48 kHz.",
    "Capture the game window only — avoid leaking other windows, chat, or credentials.",
]

_status_cache: dict[str, Any] = {"expires": 0.0, "payload": None}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def get_or_create_settings(session: Session, settings: Settings) -> StreamSettings:
    """Return the singleton StreamSettings row, creating defaults if needed."""

    row = session.get(StreamSettings, 1)
    if row is not None:
        return row
    row = StreamSettings(
        id=1,
        title="MineForge Live",
        description="",
        enabled=settings.stream_enabled,
        key_hash=None,
        key_rotated_at=None,
        updated_at=_utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def rtmp_server_url(settings: Settings) -> str:
    """OBS Custom server URL (no credentials)."""

    host = settings.resolved_stream_rtmp_host()
    return f"rtmp://{host}:{settings.stream_rtmp_port}/{STREAM_PATH}"


def obs_stream_key_field(stream_key: str) -> str:
    """Value for OBS Custom 'Stream Key' (MediaMTX query auth)."""

    return f"?user=publish&pass={stream_key}"


def rtmp_url_with_key(settings: Settings, stream_key: str) -> str:
    """Full RTMP publish URL with query credentials for MediaMTX."""

    return f"{rtmp_server_url(settings)}{obs_stream_key_field(stream_key)}"


def settings_to_dict(
    row: StreamSettings, settings: Settings, *, include_obs: bool = True
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": row.title,
        "description": row.description,
        "enabled": row.enabled,
        "key_configured": bool(row.key_hash),
        "key_rotated_at": (
            row.key_rotated_at.isoformat() if row.key_rotated_at else None
        ),
        "rtmp_server": rtmp_server_url(settings),
        "rtmp_host": settings.resolved_stream_rtmp_host(),
        "rtmp_port": settings.stream_rtmp_port,
        "rtmp_stream_key_hint": (
            "Regenerate the key to reveal copyable OBS values (shown once)."
            if row.key_hash
            else "No key yet — regenerate to create one."
        ),
    }
    if include_obs:
        payload["obs_notes"] = list(OBS_NOTES)
    return payload


def update_settings(
    session: Session,
    settings: Settings,
    *,
    user: User,
    title: str | None,
    description: str | None,
    enabled: bool | None,
    ip: str | None,
) -> StreamSettings:
    """Update stream page settings (admin).

    Raises:
        ForbiddenError: if the user is not an admin.
        AppError: on empty title after update.
    """

    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    row = get_or_create_settings(session, settings)
    if title is not None:
        cleaned = title.strip()
        if not cleaned:
            raise AppError("Title must not be empty")
        row.title = cleaned[:128]
    if description is not None:
        row.description = description.strip()[:512]
    if enabled is not None:
        row.enabled = enabled
    row.updated_at = _utcnow()
    session.add(row)
    record_audit(
        session,
        action="stream.settings.update",
        user_id=user.id,
        target="stream",
        details={"enabled": row.enabled, "title": row.title},
        ip=ip,
    )
    session.commit()
    session.refresh(row)
    return row


def rotate_key(
    session: Session,
    settings: Settings,
    *,
    user: User,
    ip: str | None,
) -> tuple[str, StreamSettings]:
    """Generate a new stream key, store only its hash, return plaintext once.

    Raises:
        ForbiddenError: if the user is not an admin.
    """

    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    plaintext = generate_token(32)
    row = get_or_create_settings(session, settings)
    row.key_hash = hash_password(plaintext)
    row.key_rotated_at = _utcnow()
    row.updated_at = row.key_rotated_at
    session.add(row)
    # End any open session — old key must stop working immediately.
    _end_open_sessions(session)
    record_audit(
        session,
        action="stream.key.rotate",
        user_id=user.id,
        target="stream",
        details={"key_rotated_at": row.key_rotated_at.isoformat()},
        ip=ip,
    )
    session.commit()
    session.refresh(row)
    _invalidate_status_cache()
    return plaintext, row


def _end_open_sessions(session: Session) -> None:
    open_rows = list(
        session.exec(
            select(StreamSession).where(col(StreamSession.ended_at).is_(None))
        ).all()
    )
    now = _utcnow()
    for row in open_rows:
        row.ended_at = now
        session.add(row)


def _is_private_ip(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(addr.is_private or addr.is_loopback)


def verify_internal_caller(
    settings: Settings, *, client_ip: str | None, token: str | None
) -> None:
    """Require Docker-internal caller + shared secret for /internal/stream/auth.

    Raises:
        ForbiddenError: when the secret is wrong or the source is not private.
    """

    expected = settings.internal_stream_secret
    if not expected or expected == "CHANGE_ME_INTERNAL_STREAM_SECRET":
        raise ForbiddenError("Internal stream auth is not configured")
    if not token or not constant_time_equals(token, expected):
        raise ForbiddenError("Invalid internal auth token")
    if not _is_private_ip(client_ip):
        raise ForbiddenError("Internal stream auth requires a private source IP")


def authorize_publish(
    session: Session,
    settings: Settings,
    *,
    action: str,
    path: str,
    password: str,
    token: str,
    publisher_ip: str | None,
    protocol: str,
) -> bool:
    """Validate a MediaMTX auth callback. Returns True when allowed.

    Publish requires the current stream key. Read is allowed for the live path
    so MineForge can proxy HLS from the internal network. Failures are
    audit-logged (never log the key).

    Raises:
        Nothing — returns False on denial; caller maps to HTTP 401/403.
    """

    action_l = (action or "").strip().lower()
    path_l = (path or "").strip().strip("/")
    stream_row = get_or_create_settings(session, settings)

    if action_l in {"read", "playback"}:
        if path_l == STREAM_PATH or path_l.startswith(f"{STREAM_PATH}/"):
            return True
        record_audit(
            session,
            action="stream.auth.denied",
            user_id=None,
            target=path_l or "unknown",
            details={"action": action_l, "reason": "path"},
            ip=publisher_ip,
        )
        session.commit()
        return False

    if action_l != "publish":
        record_audit(
            session,
            action="stream.auth.denied",
            user_id=None,
            target=path_l or "unknown",
            details={"action": action_l, "reason": "action"},
            ip=publisher_ip,
        )
        session.commit()
        return False

    if path_l != STREAM_PATH:
        record_audit(
            session,
            action="stream.auth.denied",
            user_id=None,
            target=path_l or "unknown",
            details={"action": "publish", "reason": "path"},
            ip=publisher_ip,
        )
        session.commit()
        return False

    if not stream_row.enabled:
        record_audit(
            session,
            action="stream.auth.denied",
            user_id=None,
            target=STREAM_PATH,
            details={"action": "publish", "reason": "disabled"},
            ip=publisher_ip,
        )
        session.commit()
        return False

    provided = password or token
    if not stream_row.key_hash or not provided:
        record_audit(
            session,
            action="stream.auth.denied",
            user_id=None,
            target=STREAM_PATH,
            details={"action": "publish", "reason": "no_key"},
            ip=publisher_ip,
        )
        session.commit()
        return False

    if not verify_password(stream_row.key_hash, provided):
        record_audit(
            session,
            action="stream.auth.denied",
            user_id=None,
            target=STREAM_PATH,
            details={"action": "publish", "reason": "bad_key", "protocol": protocol},
            ip=publisher_ip,
        )
        session.commit()
        return False

    _end_open_sessions(session)
    sess = StreamSession(
        started_at=_utcnow(),
        ended_at=None,
        peak_viewers=0,
        started_by=None,
        publisher_ip=publisher_ip,
    )
    session.add(sess)
    record_audit(
        session,
        action="stream.publish.start",
        user_id=None,
        target=STREAM_PATH,
        details={"protocol": protocol},
        ip=publisher_ip,
    )
    session.commit()
    _invalidate_status_cache()
    return True


def mark_stream_stopped(session: Session, *, ip: str | None = None) -> None:
    """Close open sessions when MediaMTX reports the path is idle (optional)."""

    open_rows = list(
        session.exec(
            select(StreamSession).where(col(StreamSession.ended_at).is_(None))
        ).all()
    )
    if not open_rows:
        return
    now = _utcnow()
    for row in open_rows:
        row.ended_at = now
        session.add(row)
    record_audit(
        session,
        action="stream.publish.stop",
        user_id=None,
        target=STREAM_PATH,
        details={"count": len(open_rows)},
        ip=ip,
    )
    session.commit()
    _invalidate_status_cache()


def _invalidate_status_cache() -> None:
    _status_cache["expires"] = 0.0
    _status_cache["payload"] = None


def _fetch_mediamtx_path(settings: Settings) -> dict[str, Any] | None:
    url = urljoin(
        settings.mediamtx_api_url.rstrip("/") + "/",
        f"v3/paths/get/{STREAM_PATH}",
    )
    try:
        with httpx.Client(timeout=2.5) as client:
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("MediaMTX path status unavailable: %s", exc)
        return None


def get_status(session: Session, settings: Settings) -> dict[str, Any]:
    """Return live status for the Stream page (cached ~3s).

    Raises:
        Nothing — degrades to offline when MediaMTX is unreachable.
    """

    now = time.monotonic()
    cached = _status_cache.get("payload")
    if cached is not None and float(_status_cache["expires"]) > now:
        return dict(cached)

    row = get_or_create_settings(session, settings)
    path_info = _fetch_mediamtx_path(settings)
    ready = False
    viewers = 0
    bitrate: float | None = None
    codec: str | None = None
    resolution: str | None = None
    started_at: str | None = None

    if path_info is not None:
        ready = bool(path_info.get("ready"))
        readers = path_info.get("readers")
        if isinstance(readers, list):
            viewers = len(readers)
        elif isinstance(path_info.get("readerCount"), int):
            viewers = int(path_info["readerCount"])
        tracks = path_info.get("tracks") or path_info.get("bytesReceived")
        # Best-effort fields across MediaMTX versions.
        _bytes_recv = path_info.get("bytesReceived")
        if isinstance(_bytes_recv, int | float):
            # Not a true bitrate; leave None unless we can derive.
            pass
        if isinstance(tracks, list) and tracks:
            # tracks may be strings like "H264" or dicts
            first = tracks[0]
            if isinstance(first, str):
                codec = first
            elif isinstance(first, dict):
                codec = str(first.get("codec") or first.get("type") or "") or None

    open_session = session.exec(
        select(StreamSession)
        .where(col(StreamSession.ended_at).is_(None))
        .order_by(col(StreamSession.started_at).desc())
    ).first()

    if ready and open_session is None:
        # Publisher may have been allowed before process restart — open a row.
        open_session = StreamSession(
            started_at=_utcnow(),
            peak_viewers=viewers,
            publisher_ip=None,
        )
        session.add(open_session)
        session.commit()
        session.refresh(open_session)

    if not ready and open_session is not None:
        open_session.ended_at = _utcnow()
        session.add(open_session)
        record_audit(
            session,
            action="stream.publish.stop",
            user_id=None,
            target=STREAM_PATH,
            details={"reason": "path_not_ready"},
            ip=None,
        )
        session.commit()
        open_session = None

    if open_session is not None:
        if viewers > open_session.peak_viewers:
            open_session.peak_viewers = viewers
            session.add(open_session)
            session.commit()
        started_at = open_session.started_at.isoformat()

    last = session.exec(
        select(StreamSession)
        .where(col(StreamSession.ended_at).is_not(None))
        .order_by(col(StreamSession.ended_at).desc())
    ).first()

    payload = {
        "live": bool(ready and row.enabled),
        "enabled": row.enabled,
        "title": row.title,
        "description": row.description,
        "started_at": started_at if ready else None,
        "viewers": viewers if ready else 0,
        "bitrate_kbps": bitrate,
        "video_codec": codec,
        "resolution": resolution,
        "last_ended_at": last.ended_at.isoformat() if last and last.ended_at else None,
    }
    _status_cache["payload"] = payload
    _status_cache["expires"] = now + STATUS_CACHE_SECONDS
    return dict(payload)


_TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)")


def validate_hls_rel_path(rel_path: str) -> str:
    """Normalize and validate an HLS subpath under ``live/``.

    Raises:
        ForbiddenError: on traversal or disallowed extensions.
        NotFoundError: on empty path.
    """

    cleaned = (rel_path or "").replace("\\", "/").lstrip("/")
    if not cleaned:
        raise NotFoundError("Missing HLS path")
    if _TRAVERSAL_RE.search(cleaned) or cleaned.startswith(".."):
        raise ForbiddenError("Invalid HLS path")
    if not (cleaned == STREAM_PATH or cleaned.startswith(f"{STREAM_PATH}/")):
        raise ForbiddenError("HLS path must be under live/")
    # Allow playlist root and segment files.
    name = cleaned.rsplit("/", 1)[-1]
    if "." in name:
        lower = name.lower()
        if not any(lower.endswith(suf) for suf in HLS_ALLOWED_SUFFIXES):
            raise ForbiddenError("Disallowed HLS file type")
    return cleaned


def proxy_hls(
    settings: Settings, rel_path: str
) -> tuple[Iterator[bytes], str, dict[str, str]]:
    """Stream an HLS playlist/segment from MediaMTX.

    Returns ``(body_iterator, media_type, headers)``.

    Raises:
        ForbiddenError / NotFoundError: from path validation.
        AppError: when MediaMTX is unreachable or returns an error.
    """

    cleaned = validate_hls_rel_path(rel_path)
    base = settings.mediamtx_hls_url.rstrip("/") + "/"
    url = urljoin(base, cleaned)
    if not url.startswith(base):
        raise ForbiddenError("Invalid HLS URL")

    try:
        client = httpx.Client(timeout=httpx.Timeout(15.0, connect=3.0))
        request = client.build_request("GET", url)
        response = client.send(request, stream=True)
    except httpx.HTTPError as exc:
        raise AppError("Stream media unavailable", status_code=502) from exc

    if response.status_code == 404:
        response.close()
        client.close()
        raise NotFoundError("Segment not found")
    if response.status_code >= 400:
        response.close()
        client.close()
        raise AppError("Stream media error", status_code=502)

    media_type = response.headers.get("content-type") or _guess_media_type(cleaned)
    is_playlist = cleaned.endswith(".m3u8")
    headers = {
        "Cache-Control": "no-cache" if is_playlist else "public, max-age=1",
        "X-Accel-Buffering": "no",
    }

    def body() -> Iterator[bytes]:
        try:
            for chunk in response.iter_bytes(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            response.close()
            client.close()

    return body(), media_type, headers


def _guess_media_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if lower.endswith(".ts"):
        return "video/mp2t"
    if lower.endswith(".mp4") or lower.endswith(".m4s"):
        return "video/mp4"
    return "application/octet-stream"


def reset_stream_cache_for_tests() -> None:
    """Clear status cache between tests."""

    _invalidate_status_cache()
