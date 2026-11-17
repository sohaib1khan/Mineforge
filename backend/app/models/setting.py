"""Key/value settings store."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True, max_length=128)
    value: str
