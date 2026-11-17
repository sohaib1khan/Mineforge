"""Shared API error types and handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error with an HTTP status code."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach AppError → JSON response handling."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
