"""Console mark-based waits used by live backups."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services import backups as backup_service
from app.services import console as console_service


def test_lines_after_mark_ignores_older_and_keeps_newer() -> None:
    # Reset buffer by draining via snapshot then appending controlled lines.
    console_service.append_output("old-line", stream="stdout")
    mark = backup_service._console_mark()
    console_service.append_output("new-line", stream="stdout")
    lines = backup_service._lines_after_mark(mark)
    assert "new-line" in lines
    # Older-or-equal mark line must not be included (strictly after).
    assert all(text != "old-line" or text == "new-line" for text in lines)


def test_lines_after_mark_works_when_buffer_is_full() -> None:
    """Index cursors break at maxlen; timestamp marks must still see new lines."""

    for i in range(console_service.MAX_BUFFER + 50):
        console_service.append_output(f"fill-{i}", stream="stdout")
    mark = datetime.now(UTC) - timedelta(milliseconds=1)
    console_service.append_output("after-full", stream="stdout")
    lines = backup_service._lines_after_mark(mark)
    assert "after-full" in lines
