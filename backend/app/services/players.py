"""Online player queries from PlayerSession rows."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.player_session import PlayerSession


def _player_identity_key(row: PlayerSession) -> str:
    """Stable identity for dedupe: prefer xuid, else gamertag."""

    xuid = (row.xuid or "").strip()
    if xuid:
        return f"xuid:{xuid}"
    return f"name:{(row.gamertag or '').strip().lower()}"


def list_online_players(session: Session) -> list[PlayerSession]:
    """Return unique players with an open session (left_at is null).

    Dedupes by xuid/gamertag so reconnect ghosts do not inflate consent counts.
    """

    statement = (
        select(PlayerSession)
        .where(PlayerSession.left_at.is_(None))  # type: ignore[union-attr]
        .order_by(PlayerSession.joined_at)
    )
    rows = list(session.exec(statement).all())
    best: dict[str, PlayerSession] = {}
    for row in rows:
        key = _player_identity_key(row)
        prev = best.get(key)
        if prev is None or row.joined_at >= prev.joined_at:
            best[key] = row
    return sorted(best.values(), key=lambda r: r.joined_at)
