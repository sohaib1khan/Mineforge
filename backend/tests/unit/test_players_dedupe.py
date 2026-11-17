"""Online player dedupe and duplicate session cleanup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.player_session import PlayerSession
from app.services import players as players_service
from app.services.logwatch import apply_log_event, close_duplicate_open_sessions
from sqlmodel import Session, select


def test_list_online_players_dedupes_same_xuid(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        PlayerSession(
            gamertag="player_one",
            xuid="2535400000000001",
            joined_at=now - timedelta(minutes=10),
        )
    )
    db_session.add(
        PlayerSession(
            gamertag="player_one",
            xuid="2535400000000001",
            joined_at=now - timedelta(minutes=1),
        )
    )
    db_session.add(
        PlayerSession(
            gamertag="player_two",
            xuid="2535400000000002",
            joined_at=now - timedelta(minutes=5),
        )
    )
    db_session.commit()

    online = players_service.list_online_players(db_session)
    assert len(online) == 2
    assert {p.gamertag for p in online} == {"player_one", "player_two"}


def test_join_does_not_duplicate_open_session(db_session: Session) -> None:
    apply_log_event(
        db_session,
        "join",
        {"gamertag": "player_one", "xuid": "2535400000000001"},
    )
    apply_log_event(
        db_session,
        "join",
        {"gamertag": "player_one", "xuid": "2535400000000001"},
    )
    open_rows = list(
        db_session.exec(
            select(PlayerSession).where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
        ).all()
    )
    assert len(open_rows) == 1


def test_leave_closes_all_open_sessions_for_player(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        PlayerSession(
            gamertag="player_one",
            xuid="2535400000000001",
            joined_at=now - timedelta(minutes=5),
        )
    )
    db_session.add(
        PlayerSession(
            gamertag="player_one",
            xuid="2535400000000001",
            joined_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()

    apply_log_event(
        db_session,
        "leave",
        {"gamertag": "player_one", "xuid": "2535400000000001"},
    )
    open_rows = list(
        db_session.exec(
            select(PlayerSession).where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
        ).all()
    )
    assert open_rows == []


def test_close_duplicate_open_sessions(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        PlayerSession(
            gamertag="player_one",
            xuid="2535400000000001",
            joined_at=now - timedelta(minutes=5),
        )
    )
    db_session.add(
        PlayerSession(
            gamertag="player_one",
            xuid="2535400000000001",
            joined_at=now - timedelta(minutes=1),
        )
    )
    db_session.commit()

    closed = close_duplicate_open_sessions(db_session)
    assert closed == 1
    online = players_service.list_online_players(db_session)
    assert len(online) == 1
