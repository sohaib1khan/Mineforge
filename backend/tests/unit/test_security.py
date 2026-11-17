"""Unit tests for password hashing helpers."""

from app.core.security import hash_password, verify_password


def test_argon2_round_trip() -> None:
    hashed = hash_password("example-password-12")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "example-password-12")
    assert not verify_password(hashed, "wrong-password-12")
