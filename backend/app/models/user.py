"""User account model."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class UserRole(StrEnum):
    ADMIN = "admin"
    PLAYER = "player"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=64)
    password_hash: str
    role: UserRole = Field(default=UserRole.PLAYER, index=True)
    is_active: bool = Field(default=True)
    must_change_password: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login_at: datetime | None = None
