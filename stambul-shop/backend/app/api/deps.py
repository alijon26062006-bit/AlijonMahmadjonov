"""Зависимости API: сессия БД, Redis, текущий пользователь."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import get_session
from app.db.models import User
from app.security.jwt_auth import decode_token

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url)
    return _redis


Db = Annotated[AsyncSession, Depends(get_session)]
Cache = Annotated[Redis, Depends(get_redis)]


async def get_current_user(session: Db,
                           authorization: str = Header(default="")) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "unauthorized")
    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    if not payload:
        raise HTTPException(401, "unauthorized")
    user = await session.get(User, int(payload["sub"]))
    if not user or user.is_banned:
        raise HTTPException(403, "forbidden")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(session: Db,
                            authorization: str = Header(default="")) -> User | None:
    if not authorization.startswith("Bearer "):
        return None
    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    if not payload:
        return None
    return await session.get(User, int(payload["sub"]))


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
