"""Auth and setup request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole

MIN_PASSWORD_LENGTH = 12
# Letters, digits, underscore, dot, hyphen (e.g. sohaib.khan).
USERNAME_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$"


def _validate_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    return value


class SetupStatusResponse(BaseModel):
    needs_setup: bool
    app_name: str


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    password: str
    # Optional for older clients; ignored when present.
    setup_code: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _validate_password(value)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class UserPublic(BaseModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserPublic
    csrf_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _validate_password(value)


class MessageResponse(BaseModel):
    detail: str
