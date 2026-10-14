"""Пароли: только хеш argon2id, сам пароль нигде не хранится."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class WeakPasswordError(ValueError):
    pass


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(f"Пароль должен быть не длиннее {MAX_PASSWORD_LENGTH} символов")


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, UnicodeEncodeError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True, если параметры argon2 устарели — пересчитать хеш при следующем входе."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, UnicodeEncodeError):
        return True
