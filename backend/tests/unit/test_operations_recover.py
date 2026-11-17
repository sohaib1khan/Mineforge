"""Orphaned operation recovery after process restart."""

from __future__ import annotations

from app.models.operation import Operation, OperationStatus, OperationType
from app.services import operations as ops
from sqlmodel import Session


def test_recover_orphaned_operations(db_session: Session) -> None:
    running = Operation(
        type=OperationType.ADDON_BACKUP,
        status=OperationStatus.RUNNING,
        log="[started]",
    )
    queued = Operation(
        type=OperationType.SWITCH,
        status=OperationStatus.QUEUED,
        log="",
    )
    done = Operation(
        type=OperationType.BACKUP,
        status=OperationStatus.SUCCEEDED,
        log="ok",
    )
    db_session.add(running)
    db_session.add(queued)
    db_session.add(done)
    db_session.commit()
    db_session.refresh(running)
    db_session.refresh(queued)
    db_session.refresh(done)

    count = ops.recover_orphaned_operations(db_session)
    assert count == 2
    db_session.refresh(running)
    db_session.refresh(queued)
    db_session.refresh(done)
    assert running.status == OperationStatus.FAILED
    assert queued.status == OperationStatus.FAILED
    assert done.status == OperationStatus.SUCCEEDED
    assert "Recovered after process restart" in (running.log or "")
    assert ops.get_running_operation(db_session) is None
