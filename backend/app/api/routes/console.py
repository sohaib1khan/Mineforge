"""Live console: send commands and stream output via SSE."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import AdminCsrfDep, AdminDep, SessionDep, SettingsDep, get_client_ip
from app.schemas.server import (
    ConsoleCommandRequest,
    ConsoleLinesResponse,
    MessageResponse,
)
from app.services import console as console_service
from app.services import players as players_service
from app.services.audit import record_audit

router = APIRouter(prefix="/api/console", tags=["console"])


@router.get("/history", response_model=ConsoleLinesResponse)
def console_history(_admin: AdminDep, limit: int = 200) -> ConsoleLinesResponse:
    """Return recent console buffer lines (admin)."""

    return ConsoleLinesResponse(lines=console_service.snapshot_output(limit=limit))


@router.post("/command", response_model=MessageResponse)
def console_command(
    body: ConsoleCommandRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    admin: AdminCsrfDep,
) -> MessageResponse:
    """Send a console command via Docker attach (admin)."""

    console_service.send_command(settings, body.command, actor=admin.user.username)
    if body.command.strip().lower() == "list":
        online = players_service.list_online_players(session)
        names = ", ".join(p.gamertag for p in online) or "(none)"
        console_service.append_output(
            f"There are {len(online)}/?? players online: {names}",
            stream="stdout",
        )
    record_audit(
        session,
        action="console.command",
        user_id=admin.user.id,
        details={"command": body.command.strip().split(" ", 1)[0]},
        ip=get_client_ip(request),
    )
    session.commit()
    return MessageResponse(detail="sent")


@router.get("/stream")
async def console_stream(_admin: AdminDep) -> StreamingResponse:
    """SSE stream of console output (admin)."""

    async def event_generator() -> AsyncIterator[str]:
        event, getter = console_service.subscribe_console()
        try:
            for line in console_service.snapshot_output(limit=100):
                yield f"data: {json.dumps(line)}\n\n"
            while True:
                got = await asyncio.to_thread(event.wait, 15.0)
                if got:
                    for line in getter():
                        yield f"data: {json.dumps(line)}\n\n"
                else:
                    yield ": keepalive\n\n"
        finally:
            console_service.unsubscribe_console(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
