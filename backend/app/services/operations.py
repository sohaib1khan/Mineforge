"""Global operation lock, job state machine, and SSE progress fan-out.

Risky actions (backup, restore, switch, add-on apply) run as Operation rows
with streamed logs. Only one operation runs at a time (process lock + DB).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.session import get_engine
from app.models.operation import Operation, OperationStatus, OperationType

logger = logging.getLogger(__name__)

_process_lock = threading.Lock()
_subscribers_lock = threading.Lock()
_subscribers: dict[int, list[threading.Event]] = {}
_active_operation_id: int | None = None


class OperationBusyError(ConflictError):
    def __init__(
        self, message: str = "Another operation is already in progress"
    ) -> None:
        super().__init__(message)


def get_active_operation_id() -> int | None:
    return _active_operation_id


def create_operation(
    session: Session,
    *,
    op_type: OperationType,
    params: dict[str, Any] | None,
    started_by: int | None,
) -> Operation:
    """Create a queued Operation row. Does not acquire the lock or commit."""

    op = Operation(
        type=op_type,
        status=OperationStatus.QUEUED,
        params=params,
        started_by=started_by,
        log="",
        rollback_performed=False,
    )
    session.add(op)
    session.flush()
    return op


def get_operation(session: Session, operation_id: int) -> Operation:
    """Load an operation by id.

    Raises:
        NotFoundError: if missing.
    """

    op = session.get(Operation, operation_id)
    if op is None:
        raise NotFoundError("Operation not found")
    return op


def list_operations(
    session: Session, *, limit: int = 50, offset: int = 0
) -> list[Operation]:
    """Return recent operations, newest first."""

    if limit < 1 or limit > 200:
        raise AppError("limit must be between 1 and 200")
    statement = (
        select(Operation)
        .order_by(col(Operation.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def get_running_operation(session: Session) -> Operation | None:
    """Return the currently running operation, if any."""

    return session.exec(
        select(Operation).where(Operation.status == OperationStatus.RUNNING)
    ).first()


def recover_orphaned_operations(session: Session) -> int:
    """Mark RUNNING/QUEUED ops failed after process restart (no worker left).

    Container restarts leave DB rows as ``running`` while the thread is gone,
    which blocks switch/backup until cleared. Safe on every startup because
    operations only run in-process.

    Returns:
        Number of operations recovered.
    """

    orphans = list(
        session.exec(
            select(Operation).where(
                col(Operation.status).in_(
                    [OperationStatus.RUNNING, OperationStatus.QUEUED]
                )
            )
        ).all()
    )
    if not orphans:
        return 0
    now = datetime.now(UTC)
    stamp = now.strftime("%H:%M:%S")
    for op in orphans:
        op.status = OperationStatus.FAILED
        if op.started_at is None:
            op.started_at = now
        op.finished_at = now
        note = (
            f"[{stamp}] FAILED: Recovered after process restart "
            f"(orphaned {op.type.value if isinstance(op.type, OperationType) else op.type})"
        )
        op.log = (op.log + "\n" if op.log else "") + note
        session.add(op)
    session.commit()
    release_lock()
    logger.warning("Recovered %s orphaned operation(s) on startup", len(orphans))
    return len(orphans)


def append_log(session: Session, operation_id: int, line: str) -> Operation:
    """Append a timestamped line to the operation log and notify SSE subscribers.

    Commits so SSE clients see progress promptly.
    """

    op = get_operation(session, operation_id)
    stamp = datetime.now(UTC).strftime("%H:%M:%S")
    entry = f"[{stamp}] {line}"
    op.log = (op.log + "\n" if op.log else "") + entry
    session.add(op)
    session.commit()
    session.refresh(op)
    _notify(operation_id)
    return op


def set_status(
    session: Session,
    operation_id: int,
    status: OperationStatus,
    *,
    rollback_performed: bool | None = None,
) -> Operation:
    """Update operation status; set started/finished timestamps as needed."""

    op = get_operation(session, operation_id)
    op.status = status
    now = datetime.now(UTC)
    if status == OperationStatus.RUNNING and op.started_at is None:
        op.started_at = now
    if status in {
        OperationStatus.SUCCEEDED,
        OperationStatus.FAILED,
        OperationStatus.ROLLED_BACK,
    }:
        op.finished_at = now
    if rollback_performed is not None:
        op.rollback_performed = rollback_performed
    session.add(op)
    session.commit()
    session.refresh(op)
    _notify(operation_id)
    return op


def acquire_lock(session: Session, operation_id: int) -> None:
    """Acquire the global operation lock for this job.

    Raises:
        OperationBusyError: if another job holds the lock.
    """

    global _active_operation_id
    if not _process_lock.acquire(blocking=False):
        raise OperationBusyError()
    try:
        running = get_running_operation(session)
        if running is not None and running.id != operation_id:
            raise OperationBusyError(
                f"Operation {running.id} ({running.type}) is already running"
            )
        _active_operation_id = operation_id
    except Exception:
        _process_lock.release()
        raise


def release_lock(operation_id: int | None = None) -> None:
    """Release the global lock if held by this operation (or any if None)."""

    global _active_operation_id
    if operation_id is not None and _active_operation_id not in {None, operation_id}:
        return
    _active_operation_id = None
    if _process_lock.locked():
        try:
            _process_lock.release()
        except RuntimeError:
            pass


def subscribe(operation_id: int) -> threading.Event:
    """Subscribe to log/status updates for an operation."""

    event = threading.Event()
    with _subscribers_lock:
        _subscribers.setdefault(operation_id, []).append(event)
    return event


def unsubscribe(operation_id: int, event: threading.Event) -> None:
    with _subscribers_lock:
        events = _subscribers.get(operation_id)
        if not events:
            return
        if event in events:
            events.remove(event)
        if not events:
            _subscribers.pop(operation_id, None)


def _notify(operation_id: int) -> None:
    with _subscribers_lock:
        for event in _subscribers.get(operation_id, []):
            event.set()


def run_in_background(
    operation_id: int,
    work: Callable[[Session, int], None],
) -> None:
    """Run work(session, operation_id) on a daemon thread with lock + status.

    On success → SUCCEEDED. On AppError/Exception → FAILED (or ROLLED_BACK if
    the worker set rollback_performed). Always releases the lock.
    """

    def _runner() -> None:
        with Session(get_engine()) as session:
            try:
                acquire_lock(session, operation_id)
                set_status(session, operation_id, OperationStatus.RUNNING)
                append_log(session, operation_id, "Operation started")
                work(session, operation_id)
                op = get_operation(session, operation_id)
                if op.status == OperationStatus.RUNNING:
                    set_status(session, operation_id, OperationStatus.SUCCEEDED)
                    append_log(session, operation_id, "Operation succeeded")
            except Exception as exc:
                logger.exception("Operation %s failed", operation_id)
                try:
                    op = get_operation(session, operation_id)
                    status = (
                        OperationStatus.ROLLED_BACK
                        if op.rollback_performed
                        else OperationStatus.FAILED
                    )
                    set_status(
                        session,
                        operation_id,
                        status,
                        rollback_performed=op.rollback_performed,
                    )
                    append_log(session, operation_id, f"FAILED: {exc}")
                except Exception:
                    logger.exception(
                        "Could not record failure for operation %s", operation_id
                    )
            finally:
                release_lock(operation_id)

    thread = threading.Thread(target=_runner, name=f"mf-op-{operation_id}", daemon=True)
    thread.start()


def operation_to_dict(op: Operation) -> dict[str, Any]:
    """Serialize an Operation for API/SSE payloads."""

    return {
        "id": op.id,
        "type": op.type.value if isinstance(op.type, OperationType) else op.type,
        "status": (
            op.status.value if isinstance(op.status, OperationStatus) else op.status
        ),
        "params": op.params,
        "started_by": op.started_by,
        "started_at": op.started_at.isoformat() if op.started_at else None,
        "finished_at": op.finished_at.isoformat() if op.finished_at else None,
        "log": op.log,
        "rollback_performed": op.rollback_performed,
        "created_at": op.created_at.isoformat() if op.created_at else None,
    }


def reset_locks_for_tests() -> None:
    """Clear process lock state (tests only)."""

    global _active_operation_id
    _active_operation_id = None
    with _subscribers_lock:
        _subscribers.clear()
    if _process_lock.locked():
        try:
            _process_lock.release()
        except RuntimeError:
            pass
