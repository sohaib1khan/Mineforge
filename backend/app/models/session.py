"""Server-side auth session model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class AuthSession(SQLModel, table=True):
    __tablename__ = "sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    token_hash: str = Field(index=True, unique=True)
    csrf_token: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    ip: str | None = None
    user_agent: str | None = Field(default=None, max_length=512)
