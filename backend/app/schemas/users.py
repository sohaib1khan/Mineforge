"""Admin user management schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole
from app.schemas.auth import USERNAME_PATTERN, UserPublic, _validate_password


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    password: str
    role: UserRole = UserRole.PLAYER

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _validate_password(value)


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _validate_password(value)


class UserListResponse(BaseModel):
    users: list[UserPublic]
