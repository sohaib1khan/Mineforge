"""Admin user management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import AdminCsrfDep, AdminDep, SessionDep, get_client_ip
from app.schemas.auth import MessageResponse, UserPublic
from app.schemas.users import (
    ResetPasswordRequest,
    UserCreateRequest,
    UserListResponse,
    UserUpdateRequest,
)
from app.services import users as users_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserListResponse)
def list_users(session: SessionDep, _admin: AdminDep) -> UserListResponse:
    """List all users (admin)."""

    users = users_service.list_users(session)
    return UserListResponse(users=[UserPublic.model_validate(u) for u in users])


@router.post("", response_model=UserPublic)
def create_user(
    body: UserCreateRequest,
    request: Request,
    session: SessionDep,
    admin: AdminCsrfDep,
) -> UserPublic:
    """Create a user (admin)."""

    user = users_service.create_user(
        session,
        username=body.username,
        password=body.password,
        role=body.role,
        actor=admin.user,
        ip=get_client_ip(request),
    )
    return UserPublic.model_validate(user)


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: int,
    body: UserUpdateRequest,
    request: Request,
    session: SessionDep,
    admin: AdminCsrfDep,
) -> UserPublic:
    """Update role or active flag (admin)."""

    user = users_service.update_user(
        session,
        user_id,
        actor=admin.user,
        role=body.role,
        is_active=body.is_active,
        ip=get_client_ip(request),
    )
    return UserPublic.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    request: Request,
    session: SessionDep,
    admin: AdminCsrfDep,
) -> MessageResponse:
    """Reset a user's password and force change on next login (admin)."""

    users_service.reset_password(
        session,
        user_id,
        new_password=body.new_password,
        actor=admin.user,
        ip=get_client_ip(request),
    )
    return MessageResponse(detail="Password reset")


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminCsrfDep,
) -> MessageResponse:
    """Delete a user (admin)."""

    users_service.delete_user(
        session,
        user_id,
        actor=admin.user,
        ip=get_client_ip(request),
    )
    return MessageResponse(detail="User deleted")
