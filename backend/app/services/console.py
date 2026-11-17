"""Send Bedrock console commands and maintain a ring buffer of output."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime

from app.core.config import Settings
from app.core.errors import AppError
from app.services.docker_client import get_docker_client

MAX_BUFFER = 1000

_buffer_lock = threading.Lock()
_output_buffer: deque[dict[str, str]] = deque(maxlen=MAX_BUFFER)
_subscribers: list[threading.Event] = []


def append_output(text: str, *, stream: str = "stdout") -> None:
    """Append a line to the shared console buffer and wake SSE subscribers."""

    line = {
        "ts": datetime.now(UTC).isoformat(),
        "stream": stream,
        "text": text,
    }
    with _buffer_lock:
        _output_buffer.append(line)
        for event in _subscribers:
            event.set()


def snapshot_output(limit: int = 200) -> list[dict[str, str]]:
    """Return the newest console lines."""

    with _buffer_lock:
        items = list(_output_buffer)
    return items[-limit:]


def subscribe_console() -> tuple[threading.Event, Callable[[], list[dict[str, str]]]]:
    """Subscribe to new console lines. Returns (event, getter)."""

    event = threading.Event()
    with _buffer_lock:
        _subscribers.append(event)
        cursor = len(_output_buffer)

    def getter() -> list[dict[str, str]]:
        nonlocal cursor
        with _buffer_lock:
            items = list(_output_buffer)[cursor:]
            cursor = len(_output_buffer)
            event.clear()
            return items

    return event, getter


def unsubscribe_console(event: threading.Event) -> None:
    """Remove an SSE subscriber event."""

    with _buffer_lock:
        if event in _subscribers:
            _subscribers.remove(event)


def send_command(settings: Settings, command: str, *, actor: str) -> None:
    """Send a console command via Docker attach and echo it to the buffer.

    Raises:
        AppError: validation or Docker failures.
    """

    cleaned = command.strip()
    if not cleaned:
        raise AppError("Command must not be empty")
    if "\n" in cleaned or "\r" in cleaned:
        raise AppError("Command must be a single line")

    append_output(f"> {cleaned}", stream="stdin")
    client = get_docker_client(settings)
    client.send_command(cleaned)
    append_output(f"(sent by {actor})", stream="system")
