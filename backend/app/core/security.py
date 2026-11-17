"""Password hashing, token generation, and cookie helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Hash a password with argon2id.

    Raises:
        ValueError: if the password is empty.
    """

    if not password:
        raise ValueError("password must not be empty")
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return True when the password matches the argon2id hash."""

    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_token(nbytes: int = 32) -> str:
    """Return a URL-safe random token."""

    return secrets.token_urlsafe(nbytes)


def hash_token(token: str, *, secret: str | None = None) -> str:
    """Hash a session token for storage (HMAC-SHA256 when secret is set)."""

    raw = token.encode("utf-8")
    if secret:
        return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hashlib.sha256(raw).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    """Compare two strings in constant time."""

    return hmac.compare_digest(left, right)
