"""Safe path resolution inside allowed roots."""

from __future__ import annotations

from pathlib import Path

from app.core.errors import ForbiddenError


def resolve_under(root: Path, *parts: str) -> Path:
    """Resolve a path and ensure it stays inside root.

    Raises:
        ForbiddenError: if the resolved path escapes the root.
    """

    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise ForbiddenError("Path escapes allowed root")
    return candidate
