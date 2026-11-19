from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import get_settings

_ph = PasswordHasher()
COOKIE_NAME = "session"
ALGO = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def make_token(user_id: int) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(days=s.session_days)
    return jwt.encode({"sub": str(user_id), "exp": exp}, s.secret_key, algorithm=ALGO)


def read_token(token: str) -> int | None:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=[ALGO])
        return int(data["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
