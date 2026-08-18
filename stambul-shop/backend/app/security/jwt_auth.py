"""Сессионные токены (HS256). Секрет отдельный, не токен бота."""
import time
import uuid

import jwt

from app.config import get_settings


def issue_token(user_id: int, tg_id: int | None, is_admin: bool) -> str:
    s = get_settings()
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "tg": tg_id, "adm": is_admin,
         "iat": now, "exp": now + s.jwt_ttl, "jti": uuid.uuid4().hex},
        s.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
