"""Online player queries from PlayerSession rows."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.player_session import PlayerSession


def list_online_players(session: Session) -> list[PlayerSession]:
    """Return players with an open session (left_at is null)."""

    statement = (
        select(PlayerSession)
        .where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
        .order_by(PlayerSession.joined_at)
    )
    return list(session.exec(statement).all())
