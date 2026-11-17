"""Safe world switch (Section 8) with player rules, countdown, and rollback."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, ForbiddenError
from app.models.backup import BackupKind
from app.models.operation import OperationType
from app.models.setting import Setting
from app.models.user import UserRole
from app.services import backups as backup_service
from app.services import console as console_service
from app.services import operations as ops
from app.services import server_props
from app.services import worlds as worlds_service
from app.services.archive_safety import dir_size, free_disk_bytes
from app.services.audit import record_audit
from app.services.docker_client import get_docker_client
from app.services.players import list_online_players

logger = logging.getLogger(__name__)

LAST_SWITCH_KEY = "last_switch_at"
SWITCH_CONSENT_TTL = timedelta(minutes=2)

_consent_lock = threading.Lock()
_consents: dict[str, SwitchConsent] = {}

# Test hook: raise after level-name change, before health success.
_switch_fail_hook: Callable[[], None] | None = None


def set_switch_fail_hook(hook: Callable[[], None] | None) -> None:
    """Inject a failure after switching level-name (tests)."""

    global _switch_fail_hook
    _switch_fail_hook = hook


@dataclass
class SwitchConsent:
    id: str
    target_world_id: int
    target_folder: str
    requested_by: int
    required_count: int
    approvals: set[int] = field(default_factory=set)
    online_gamertags: list[str] = field(default_factory=list)
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self) -> bool:
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return datetime.now(UTC) >= exp

    def is_satisfied(self) -> bool:
        return len(self.approvals) >= self.required_count


def reset_consents_for_tests() -> None:
    with _consent_lock:
        _consents.clear()


def create_consent_request(
    session: Session,
    *,
    target_world_id: int,
    target_folder: str,
    user_id: int,
) -> dict[str, Any]:
    """Open a switch consent request when other players are online.

    Any authenticated user may approve. Requires one approval per online player.
    """

    online = list_online_players(session)
    if not online:
        raise AppError("No players online; switch without a consent request")
    req = SwitchConsent(
        id=uuid.uuid4().hex,
        target_world_id=target_world_id,
        target_folder=target_folder,
        requested_by=user_id,
        required_count=len(online),
        online_gamertags=[p.gamertag for p in online],
        expires_at=datetime.now(UTC) + SWITCH_CONSENT_TTL,
    )
    # Requester auto-counts as one approval
    req.approvals.add(user_id)
    with _consent_lock:
        # Drop expired
        expired = [k for k, v in _consents.items() if v.is_expired()]
        for k in expired:
            del _consents[k]
        _consents[req.id] = req
    return consent_to_dict(req)


def approve_consent(request_id: str, user_id: int) -> dict[str, Any]:
    """Approve an open switch consent request."""

    with _consent_lock:
        req = _consents.get(request_id)
        if req is None or req.is_expired():
            _consents.pop(request_id, None)
            raise AppError("Switch request not found or expired", status_code=404)
        req.approvals.add(user_id)
        return consent_to_dict(req)


def get_consent(request_id: str) -> dict[str, Any] | None:
    with _consent_lock:
        req = _consents.get(request_id)
        if req is None:
            return None
        if req.is_expired():
            del _consents[request_id]
            return None
        return consent_to_dict(req)


def consent_to_dict(req: SwitchConsent) -> dict[str, Any]:
    return {
        "id": req.id,
        "target_world_id": req.target_world_id,
        "target_folder": req.target_folder,
        "requested_by": req.requested_by,
        "required_count": req.required_count,
        "approval_count": len(req.approvals),
        "online_gamertags": list(req.online_gamertags),
        "expires_at": req.expires_at.isoformat(),
        "satisfied": req.is_satisfied(),
    }


def start_switch(
    session: Session,
    settings: Settings,
    *,
    target_world_id: int,
    user_id: int,
    role: UserRole,
    ip: str | None,
    force: bool = False,
    skip_countdown: bool = False,
    consent_id: str | None = None,
) -> dict[str, Any]:
    """Queue a world switch operation after permission checks."""

    target = worlds_service.get_world(session, target_world_id)
    if target.is_active:
        raise AppError("World is already active")

    path = worlds_service.world_path(settings, target.folder_name)
    # New empty worlds (create) may lack level.dat — Bedrock will generate.
    is_new = path.is_dir() and not (path / "level.dat").is_file()
    if not is_new:
        worlds_service.validate_world_folder(path)

    online = list_online_players(session)
    _check_permissions(
        session,
        settings,
        role=role,
        user_id=user_id,
        online_count=len(online),
        force=force,
        consent_id=consent_id,
        target_world_id=target_world_id,
    )

    size = dir_size(path) if path.is_dir() else 0
    free = free_disk_bytes(settings.app_data_dir)
    if size > 0 and free < 2 * size:
        raise AppError(
            f"Not enough free disk (need ≥ 2× world size: {2 * size} bytes, have {free})"
        )

    active = None
    try:
        active = worlds_service.ensure_active_world(session, settings)
    except Exception:
        active = None

    op = ops.create_operation(
        session,
        op_type=OperationType.SWITCH,
        params={
            "from_world_id": active.id if active else None,
            "from_folder": active.folder_name if active else None,
            "to_world_id": target.id,
            "to_folder": target.folder_name,
            "force": force,
            "skip_countdown": skip_countdown and role == UserRole.ADMIN,
            "is_new": is_new,
        },
        started_by=user_id,
    )
    record_audit(
        session,
        action="world.switch_start",
        user_id=user_id,
        target=target.folder_name,
        details={"operation_id": op.id, "force": force},
        ip=ip,
    )
    session.commit()
    operation_id = op.id
    assert operation_id is not None
    to_id = target.id
    assert to_id is not None
    to_folder = target.folder_name
    from_id = active.id if active else None
    from_folder = active.folder_name if active else None
    skip = bool(skip_countdown and role == UserRole.ADMIN)
    new_world = is_new

    def work(worker_session: Session, oid: int) -> None:
        _run_switch(
            worker_session,
            settings,
            operation_id=oid,
            from_world_id=from_id,
            from_folder=from_folder,
            to_world_id=to_id,
            to_folder=to_folder,
            skip_countdown=skip,
            is_new=new_world,
            started_by=user_id,
        )

    ops.run_in_background(operation_id, work)
    return ops.operation_to_dict(ops.get_operation(session, operation_id))


def _check_permissions(
    session: Session,
    settings: Settings,
    *,
    role: UserRole,
    user_id: int,
    online_count: int,
    force: bool,
    consent_id: str | None,
    target_world_id: int,
) -> None:
    # Cooldown
    last = session.get(Setting, LAST_SWITCH_KEY)
    if last and last.value:
        try:
            last_at = datetime.fromisoformat(last.value)
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=UTC)
            cooldown = timedelta(minutes=max(0, settings.switch_cooldown_minutes))
            if datetime.now(UTC) < last_at + cooldown and role != UserRole.ADMIN:
                remaining = int(
                    (last_at + cooldown - datetime.now(UTC)).total_seconds()
                )
                raise ConflictError(
                    f"Switch cooldown active; try again in {remaining}s "
                    "(admins can still switch)"
                )
        except ValueError:
            pass

    if online_count == 0:
        return

    if force:
        if role != UserRole.ADMIN:
            raise ForbiddenError(
                "Only admins can force a switch while players are online"
            )
        return

    if consent_id:
        with _consent_lock:
            req = _consents.get(consent_id)
            if req is None or req.is_expired():
                raise AppError("Switch consent request expired or missing")
            if req.target_world_id != target_world_id:
                raise AppError("Consent request is for a different world")
            if not req.is_satisfied():
                raise ConflictError(
                    f"Need {req.required_count} approvals, have {len(req.approvals)}"
                )
        return

    raise ConflictError(
        "Other players are online. Create a switch request and get approvals, "
        "or an admin can force the switch."
    )


def _run_switch(
    session: Session,
    settings: Settings,
    *,
    operation_id: int,
    from_world_id: int | None,
    from_folder: str | None,
    to_world_id: int,
    to_folder: str,
    skip_countdown: bool,
    is_new: bool,
    started_by: int | None,
) -> None:
    docker = get_docker_client(settings)
    was_running = docker.status().running
    props_snapshot = server_props.snapshot_properties_text(settings)
    switched = False

    try:
        # 2) Warn + countdown
        if was_running and not skip_countdown:
            seconds = max(0, settings.switch_countdown_seconds)
            ops.append_log(
                session,
                operation_id,
                f"Warning players: switching to {to_folder} in {seconds}s",
            )
            try:
                console_service.send_command(
                    settings,
                    f"say MineForge: switching world to {to_folder} in {seconds} seconds",
                    actor="switch",
                )
            except Exception as exc:
                ops.append_log(session, operation_id, f"Warn say failed: {exc}")
            for remaining in range(seconds, 0, -5):
                ops.append_log(session, operation_id, f"Countdown: {remaining}s")
                time.sleep(min(5, remaining))
        elif skip_countdown:
            ops.append_log(session, operation_id, "Countdown skipped by admin")

        # 3) Backup current world
        if from_folder and from_world_id is not None:
            from_path = worlds_service.world_path(settings, from_folder)
            if from_path.is_dir():
                try:
                    worlds_service.validate_world_folder(from_path)
                    ops.append_log(
                        session, operation_id, f"Pre-switch backup of {from_folder}"
                    )
                    backup_service.create_backup_sync(
                        session,
                        settings,
                        world_id=from_world_id,
                        world_folder=from_folder,
                        kind=BackupKind.PRE_SWITCH,
                        created_by=started_by,
                        operation_id=operation_id,
                    )
                except AppError as exc:
                    raise AppError(
                        f"Pre-switch backup failed; aborting: {exc}"
                    ) from exc

        # 4) Stop
        if was_running:
            ops.append_log(session, operation_id, "Stopping Bedrock")
            try:
                console_service.send_command(settings, "stop", actor="switch")
                time.sleep(2)
            except Exception:
                pass
            docker.stop(timeout=45)

        # 5) Switch level-name (+ optional gamemode/difficulty from target metadata)
        ops.append_log(session, operation_id, f"Setting level-name={to_folder}")
        target = worlds_service.get_world(session, to_world_id)
        updates: dict[str, str] = {"level-name": to_folder}
        if target.gamemode:
            updates["gamemode"] = target.gamemode
        if target.difficulty:
            updates["difficulty"] = target.difficulty
        server_props.write_managed(settings, updates)
        # Merge enabled library profile with world-embedded packs
        try:
            from app.services import addons as addons_service

            addons_service.write_merged_pack_jsons(
                session, settings, to_folder, to_world_id
            )
            ops.append_log(
                session, operation_id, "Merged pack profile for target world"
            )
        except Exception as pack_exc:
            ops.append_log(session, operation_id, f"Pack merge skipped: {pack_exc}")
        switched = True

        if _switch_fail_hook is not None:
            _switch_fail_hook()

        # 6) Start + health (always start so the new world loads)
        ops.append_log(session, operation_id, "Starting Bedrock")
        docker.start()
        backup_service_wait_healthy(settings, session, operation_id)
        if is_new:
            new_path = worlds_service.world_path(settings, to_folder)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if (new_path / "level.dat").is_file():
                    break
                time.sleep(1)

        # 7) Success
        worlds_service.ensure_world_for_folder(
            session, settings, to_folder, mark_active=True
        )
        _set_last_switch(session)
        session.commit()
        ops.append_log(session, operation_id, f"Switched to {to_folder}")
        record_audit(
            session,
            action="world.switch_success",
            user_id=started_by,
            target=to_folder,
            details={"operation_id": operation_id},
        )
        session.commit()
    except Exception as exc:
        ops.append_log(session, operation_id, f"Switch failed: {exc}")
        if switched and props_snapshot:
            ops.append_log(session, operation_id, "Rolling back server.properties")
            try:
                try:
                    docker.stop(timeout=30)
                except Exception:
                    pass
                server_props.restore_properties_text(settings, props_snapshot)
                docker.start()
                try:
                    backup_service_wait_healthy(settings, session, operation_id)
                except Exception as health_exc:
                    ops.append_log(
                        session, operation_id, f"Rollback health warning: {health_exc}"
                    )
                if from_folder:
                    worlds_service.ensure_world_for_folder(
                        session, settings, from_folder, mark_active=True
                    )
                    session.commit()
                op = ops.get_operation(session, operation_id)
                op.rollback_performed = True
                session.add(op)
                session.commit()
                ops.append_log(session, operation_id, "Rollback completed")
            except Exception as rb_exc:
                ops.append_log(session, operation_id, f"Rollback failed: {rb_exc}")
                raise
        raise


def backup_service_wait_healthy(
    settings: Settings, session: Session, operation_id: int
) -> None:
    """Wait for server health; log progress."""

    from app.services.backups import HEALTH_TIMEOUT, _wait_for_server_healthy

    ops.append_log(session, operation_id, "Waiting for server health")
    _wait_for_server_healthy(settings, timeout=HEALTH_TIMEOUT)


def _set_last_switch(session: Session) -> None:
    row = session.get(Setting, LAST_SWITCH_KEY)
    now = datetime.now(UTC).isoformat()
    if row is None:
        session.add(Setting(key=LAST_SWITCH_KEY, value=now))
    else:
        row.value = now
        session.add(row)


def switch_status(session: Session, settings: Settings) -> dict[str, Any]:
    """Return cooldown / online info for the switch UI."""

    online = list_online_players(session)
    last = session.get(Setting, LAST_SWITCH_KEY)
    cooldown_remaining = 0
    if last and last.value:
        try:
            last_at = datetime.fromisoformat(last.value)
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=UTC)
            end = last_at + timedelta(minutes=max(0, settings.switch_cooldown_minutes))
            cooldown_remaining = max(0, int((end - datetime.now(UTC)).total_seconds()))
        except ValueError:
            pass
    with _consent_lock:
        open_reqs = [
            consent_to_dict(r) for r in _consents.values() if not r.is_expired()
        ]
    return {
        "players_online": len(online),
        "online_gamertags": [p.gamertag for p in online],
        "cooldown_remaining_seconds": cooldown_remaining,
        "countdown_seconds": settings.switch_countdown_seconds,
        "open_consent_requests": open_reqs,
    }
