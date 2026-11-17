"""Operation status and SSE progress."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import AuthDep, SessionDep
from app.db.session import get_engine
from app.schemas.operations import OperationListResponse, OperationResponse
from app.services import operations as ops

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("", response_model=OperationListResponse)
def list_operations(
    session: SessionDep, _auth: AuthDep, limit: int = 50
) -> OperationListResponse:
    items = ops.list_operations(session, limit=limit)
    return OperationListResponse(
        operations=[
            OperationResponse.model_validate(ops.operation_to_dict(o)) for o in items
        ],
        active_id=ops.get_active_operation_id(),
    )


@router.get("/active", response_model=OperationResponse | None)
def active_operation(session: SessionDep, _auth: AuthDep) -> OperationResponse | None:
    running = ops.get_running_operation(session)
    if running is None:
        active_id = ops.get_active_operation_id()
        if active_id is None:
            return None
        try:
            running = ops.get_operation(session, active_id)
        except Exception:
            return None
    return OperationResponse.model_validate(ops.operation_to_dict(running))


@router.get("/{operation_id}", response_model=OperationResponse)
def get_operation(
    operation_id: int, session: SessionDep, _auth: AuthDep
) -> OperationResponse:
    op = ops.get_operation(session, operation_id)
    return OperationResponse.model_validate(ops.operation_to_dict(op))


@router.get("/{operation_id}/stream")
async def stream_operation(
    operation_id: int, session: SessionDep, _auth: AuthDep
) -> StreamingResponse:
    """SSE stream of operation log/status updates."""

    ops.get_operation(session, operation_id)  # 404 if missing

    async def event_generator() -> AsyncIterator[str]:
        event = ops.subscribe(operation_id)
        try:
            with Session(get_engine()) as live:
                op = ops.get_operation(live, operation_id)
                yield f"data: {json.dumps(ops.operation_to_dict(op))}\n\n"
            while True:
                got = await asyncio.to_thread(event.wait, 15.0)
                with Session(get_engine()) as live:
                    op = ops.get_operation(live, operation_id)
                    payload = ops.operation_to_dict(op)
                if got:
                    event.clear()
                    yield f"data: {json.dumps(payload)}\n\n"
                    if payload["status"] in {"succeeded", "failed", "rolled_back"}:
                        break
                else:
                    yield ": keepalive\n\n"
                    if payload["status"] in {"succeeded", "failed", "rolled_back"}:
                        yield f"data: {json.dumps(payload)}\n\n"
                        break
        finally:
            ops.unsubscribe(operation_id, event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
