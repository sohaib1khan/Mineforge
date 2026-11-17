"""Parse Bedrock server logs for started / join / leave events."""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.models.player_session import PlayerSession
from app.services.docker_client import (
    DockerUnavailableError,
    get_docker_client,
)

logger = logging.getLogger(__name__)

# Example lines (itzg / BDS vary slightly):
# Player connected: Steve, xuid: 2535400000000000
# Player disconnected: Steve, xuid: 2535400000000000
# Server started.
JOIN_RE = re.compile(
    r"Player connected:\s*(?P<name>.+?)(?:,\s*xuid:\s*(?P<xuid>\d+))?\s*$",
    re.IGNORECASE,
)
LEAVE_RE = re.compile(
    r"Player disconnected:\s*(?P<name>.+?)(?:,\s*xuid:\s*(?P<xuid>\d+))?\s*$",
    re.IGNORECASE,
)
STARTED_RE = re.compile(r"Server started\.?\s*$", re.IGNORECASE)

_state_lock = threading.Lock()
_server_started_at: datetime | None = None
_watcher_thread: threading.Thread | None = None
_stop_event = threading.Event()


def get_server_started_at() -> datetime | None:
    with _state_lock:
        return _server_started_at


def mark_server_started(when: datetime | None = None) -> None:
    global _server_started_at
    with _state_lock:
        _server_started_at = when or datetime.now(UTC)


def parse_log_line(line: str) -> tuple[str, dict[str, str]] | None:
    """Parse a single log line into (event, fields) or None."""

    text = line.strip()
    # Strip common timestamp / level prefixes: [2024-..] [INFO] ...
    if "] " in text:
        text = text.rsplit("] ", 1)[-1].strip()

    if STARTED_RE.search(text):
        return ("started", {})

    join = JOIN_RE.search(text)
    if join:
        fields = {"gamertag": join.group("name").strip()}
        if join.group("xuid"):
            fields["xuid"] = join.group("xuid")
        return ("join", fields)

    leave = LEAVE_RE.search(text)
    if leave:
        fields = {"gamertag": leave.group("name").strip()}
        if leave.group("xuid"):
            fields["xuid"] = leave.group("xuid")
        return ("leave", fields)

    return None


def _open_sessions_for_player(
    session: Session, *, gamertag: str, xuid: str | None
) -> list[PlayerSession]:
    """Open sessions matching xuid when present, else gamertag."""

    if xuid:
        return list(
            session.exec(
                select(PlayerSession).where(
                    PlayerSession.xuid == xuid,
                    PlayerSession.left_at.is_(None),  # type: ignore[union-attr]
                )
            ).all()
        )
    return list(
        session.exec(
            select(PlayerSession).where(
                PlayerSession.gamertag == gamertag,
                PlayerSession.left_at.is_(None),  # type: ignore[union-attr]
            )
        ).all()
    )


def close_duplicate_open_sessions(session: Session) -> int:
    """Close extra open sessions for the same player identity.

    Log replay / missed disconnects can leave multiple left_at=NULL rows for
    one xuid, which blocks world switch consent (N approvals for 1 person).

    Returns:
        Number of duplicate sessions closed.
    """

    open_rows = list(
        session.exec(
            select(PlayerSession)
            .where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
            .order_by(PlayerSession.joined_at)
        ).all()
    )
    kept: dict[str, PlayerSession] = {}
    closed = 0
    now = datetime.now(UTC)
    for row in open_rows:
        xuid = (row.xuid or "").strip()
        key = f"xuid:{xuid}" if xuid else f"name:{(row.gamertag or '').strip().lower()}"
        if key in kept:
            row.left_at = now
            session.add(row)
            closed += 1
        else:
            kept[key] = row
    if closed:
        session.commit()
        logger.warning("Closed %s duplicate open player session(s)", closed)
    return closed


def apply_log_event(session: Session, event: str, fields: dict[str, str]) -> None:
    """Persist join/leave/started side effects.

    Does commit — logwatch owns short transactions.
    """

    if event == "started":
        mark_server_started()
        # Close any open sessions on server restart.
        open_rows = session.exec(
            select(PlayerSession).where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
        ).all()
        now = datetime.now(UTC)
        for row in open_rows:
            row.left_at = now
            session.add(row)
        session.commit()
        return

    if event == "join":
        open_same = _open_sessions_for_player(
            session, gamertag=fields["gamertag"], xuid=fields.get("xuid")
        )
        if open_same:
            # Already online (reconnect / log replay) — keep one open session.
            return
        row = PlayerSession(
            gamertag=fields["gamertag"],
            xuid=fields.get("xuid"),
            joined_at=datetime.now(UTC),
        )
        session.add(row)
        session.commit()
        return

    if event == "leave":
        open_same = _open_sessions_for_player(
            session, gamertag=fields["gamertag"], xuid=fields.get("xuid")
        )
        if not open_same:
            return
        now = datetime.now(UTC)
        for row in open_same:
            row.left_at = now
            if fields.get("xuid") and not row.xuid:
                row.xuid = fields["xuid"]
            session.add(row)
        session.commit()


def handle_line(
    line: str, session_factory: Callable[[], Session] | None = None
) -> None:
    """Parse and apply one log line; always echo to the console buffer."""

    from app.services.console import append_output

    append_output(line, stream="stdout")
    parsed = parse_log_line(line)
    if parsed is None:
        return
    event, fields = parsed
    factory = session_factory or (lambda: Session(get_engine()))
    with factory() as session:
        apply_log_event(session, event, fields)


def _watch_loop(settings: Settings) -> None:
    logger.info("Log watcher starting for container %s", settings.bedrock_container)
    while not _stop_event.is_set():
        try:
            client = get_docker_client(settings)
            status = client.status()
            if not status.running:
                _stop_event.wait(5)
                continue
            for line in client.follow_logs():
                if _stop_event.is_set():
                    break
                try:
                    handle_line(line)
                except Exception:
                    logger.exception("Failed handling log line")
        except (DockerUnavailableError, Exception) as exc:
            logger.warning("Log watcher idle: %s", exc)
            _stop_event.wait(5)
    logger.info("Log watcher stopped")


def start_log_watcher(settings: Settings | None = None) -> None:
    """Start the background log watcher thread (idempotent)."""

    global _watcher_thread
    cfg = settings or get_settings()
    if not cfg.logwatch_enabled:
        return
    if _watcher_thread and _watcher_thread.is_alive():
        return
    _stop_event.clear()
    _watcher_thread = threading.Thread(
        target=_watch_loop,
        args=(cfg,),
        name="mineforge-logwatch",
        daemon=True,
    )
    _watcher_thread.start()


def stop_log_watcher() -> None:
    """Signal the log watcher to stop (tests / shutdown)."""

    _stop_event.set()
