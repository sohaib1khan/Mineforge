"""In-process login failure tracking and temporary lockout."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import ForbiddenError


@dataclass
class _AttemptState:
    failures: int = 0
    locked_until: float = 0.0


_lock = threading.Lock()
_attempts: dict[str, _AttemptState] = {}


def _key(username: str, ip: str | None) -> str:
    return f"{username.strip().lower()}|{ip or '-'}"


def assert_not_locked(username: str, ip: str | None, settings: Settings) -> None:
    """Raise ForbiddenError when the identity is temporarily locked out."""

    with _lock:
        state = _attempts.get(_key(username, ip))
        if state and state.locked_until > time.monotonic():
            raise ForbiddenError("Too many failed login attempts. Try again later.")


def record_failure(username: str, ip: str | None, settings: Settings) -> None:
    """Record a failed login and lock out after too many failures."""

    with _lock:
        key = _key(username, ip)
        state = _attempts.setdefault(key, _AttemptState())
        state.failures += 1
        if state.failures >= settings.login_max_attempts:
            state.locked_until = time.monotonic() + (
                settings.login_lockout_minutes * 60
            )
            state.failures = 0


def clear_failures(username: str, ip: str | None) -> None:
    """Clear failure state after a successful login."""

    with _lock:
        _attempts.pop(_key(username, ip), None)


def reset_lockouts() -> None:
    """Clear all lockout state (tests)."""

    with _lock:
        _attempts.clear()
