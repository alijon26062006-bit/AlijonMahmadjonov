"""Авторизация: Mini App (initData) и браузер (подтверждение в боте)."""
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Cache, CurrentUser, Db
from app.config import get_settings
from app.db.models import User
from app.security.init_data import InitDataError, validate_init_data
from app.security.jwt_auth import issue_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class InitDataIn(BaseModel):
    init_data: str


def _user_out(user: User) -> dict:
    return {"id": user.id, "tg_id": user.tg_id, "username": user.username,
            "first_name": user.first_name, "is_admin": user.is_admin}


async def _get_or_create(session, tg_user: dict) -> User:
    """Первый вход из Mini App = регистрация. Отдельного шага нет и не нужно:
    Telegram уже подтвердил, кто это."""
    user = await session.scalar(select(User).where(User.tg_id == tg_user["id"]))
    if user is None:
        user = User(tg_id=tg_user["id"], username=tg_user.get("username"),
                    first_name=tg_user.get("first_name", ""),
                    is_admin=tg_user["id"] in get_settings().admin_id_list)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    # Человек мог сменить имя или @username — подтягиваем при каждом входе,
    # иначе в профиле и в контактах останется то, что было при регистрации.
    changed = False
    if tg_user.get("username") != user.username:
        user.username, changed = tg_user.get("username"), True
    if tg_user.get("first_name") and tg_user["first_name"] != user.first_name:
        user.first_name, changed = tg_user["first_name"], True
    if changed:
        await session.commit()
    return user


@router.post("/telegram")
async def auth_telegram(body: InitDataIn, session: Db):
    try:
        data = validate_init_data(body.init_data)
    except InitDataError:
        raise HTTPException(401, "unauthorized") from None
    user = await _get_or_create(session, data["user"])
    if user.is_banned:
        raise HTTPException(403, "forbidden")
    return {"access_token": issue_token(user.id, user.tg_id, user.is_admin),
            "user": _user_out(user),
            "start_param": data.get("start_param")}


@router.post("/login-code")
async def create_login_code(redis: Cache):
    """Браузер: одноразовый код → ссылка на бота → подтверждение."""
    s = get_settings()
    code = secrets.token_urlsafe(24)[:32]
    await redis.set(f"login:{code}", "pending", ex=300)
    return {"code": code,
            "link": f"https://t.me/{s.bot_username}?start=login_{code}"}


@router.get("/login-code/{code}")
async def poll_login_code(code: str, redis: Cache, session: Db):
    value = await redis.get(f"login:{code[:64]}")
    if value is None:
        raise HTTPException(410, "expired")
    value = value.decode() if isinstance(value, bytes) else value
    if value == "pending":
        return {"status": "pending"}
    await redis.delete(f"login:{code[:64]}")          # код одноразовый
    user = await session.get(User, int(value))
    if not user or user.is_banned:
        raise HTTPException(403, "forbidden")
    return {"status": "confirmed",
            "access_token": issue_token(user.id, user.tg_id, user.is_admin),
            "user": _user_out(user)}


@router.get("/me")
async def me(user: CurrentUser):
    return _user_out(user)
