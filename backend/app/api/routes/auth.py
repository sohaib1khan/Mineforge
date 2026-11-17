"""Login, logout, and current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import (
    SESSION_COOKIE,
    AuthDep,
    CsrfAuthDep,
    SessionDep,
    SettingsDep,
    get_client_ip,
)
from app.core.rate_limit import limiter
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    UserPublic,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, settings, raw_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        httponly=True,
        secure=settings.resolved_cookie_secure(),
        samesite="strict",
        max_age=settings.session_days * 24 * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response, settings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=settings.resolved_cookie_secure(),
        httponly=True,
        samesite="strict",
    )


@router.post("/login", response_model=MeResponse)
@limiter.limit("10/minute")
def login(
    body: LoginRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> JSONResponse:
    """Authenticate and set the session cookie."""

    user, auth_session, raw_token = auth_service.authenticate(
        session,
        settings,
        username=body.username,
        password=body.password,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    payload = MeResponse(
        user=UserPublic.model_validate(user),
        csrf_token=auth_session.csrf_token,
    )
    response = JSONResponse(content=payload.model_dump(mode="json"))
    _set_session_cookie(response, settings, raw_token)
    return response


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    auth: CsrfAuthDep,
) -> MessageResponse:
    """Invalidate the current session and clear the cookie (CSRF required)."""

    auth_service.logout(
        session,
        raw_token=auth.raw_token,
        user_id=auth.user.id,
        ip=get_client_ip(request),
    )
    _clear_session_cookie(response, settings)
    return MessageResponse(detail="Logged out")


@router.get("/me", response_model=MeResponse)
def me(auth: AuthDep) -> MeResponse:
    """Return the current user and CSRF token."""

    return MeResponse(
        user=UserPublic.model_validate(auth.user),
        csrf_token=auth.auth_session.csrf_token,
    )


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    session: SessionDep,
    auth: CsrfAuthDep,
) -> MessageResponse:
    """Change the authenticated user's password."""

    auth_service.change_own_password(
        session,
        auth.user,
        current_password=body.current_password,
        new_password=body.new_password,
        raw_token=auth.raw_token,
        ip=get_client_ip(request),
    )
    return MessageResponse(detail="Password updated")
