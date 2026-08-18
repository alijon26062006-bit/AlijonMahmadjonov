"""Заведение и опознание покупателя.

Один человек — один аккаунт. Он может прийти с номером, с Google или из
бота; если совпало хоть одно из трёх, это тот же человек, и недостающее
мы просто дописываем ему в профиль. Отдельная регистрация с паролем не
нужна: и Telegram, и Google уже подтвердили, кто это.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User


def _should_be_admin(tg_id: int | None) -> bool:
    return bool(tg_id and tg_id in get_settings().admin_id_list)


async def sync_rights(session: AsyncSession, user: User) -> User:
    """ADMIN_IDS — единственный источник правды о правах.

    Сверяем при каждом входе: список правят в .env, и человек не должен
    ждать пересоздания аккаунта, чтобы права применились.
    """
    should = _should_be_admin(user.tg_id)
    if user.is_admin != should:
        user.is_admin = should
        await session.commit()
    return user


async def find(session: AsyncSession, *, phone: str | None = None,
               google_sub: str | None = None,
               tg_id: int | None = None,
               email: str | None = None) -> User | None:
    """Ищет по любому из опознавательных полей, в порядке надёжности."""
    for column, value in ((User.google_sub, google_sub), (User.tg_id, tg_id),
                          (User.phone, phone), (User.email, email)):
        if value:
            found = await session.scalar(select(User).where(column == value))
            if found:
                return found
    return None


async def attach(session: AsyncSession, user: User, column, field: str,
                  value) -> None:
    """Дописывает поле, если оно свободно и не занято кем-то другим.

    Занято другим — молча пропускаем: сливать два живых аккаунта с их
    заказами автоматически нельзя, это должен решать человек.
    """
    if not value or getattr(user, field):
        return
    taken = await session.scalar(select(User.id).where(column == value))
    if taken is None:
        setattr(user, field, value)


async def login_with_phone(session: AsyncSession, phone: str, *,
                           tg_id: int | None = None,
                           name: str | None = None,
                           username: str | None = None) -> User:
    user = await find(session, phone=phone, tg_id=tg_id)
    if user is None:
        user = User(phone=phone, phone_verified=True, first_name=name or "",
                    tg_id=tg_id, username=username,
                    is_admin=_should_be_admin(tg_id))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    await attach(session, user, User.phone, "phone", phone)
    await attach(session, user, User.tg_id, "tg_id", tg_id)
    user.phone_verified = True
    if name and not user.first_name:
        user.first_name = name
    if username and not user.username:
        user.username = username
    await session.commit()
    return await sync_rights(session, user)


async def login_with_google(session: AsyncSession, claims: dict) -> User:
    sub = claims.get("sub")
    email = (claims.get("email") or "").strip().lower() or None
    name = (claims.get("name") or "").strip()
    picture = claims.get("picture")

    user = await find(session, google_sub=sub, email=email)
    if user is None:
        user = User(google_sub=sub, email=email, first_name=name,
                    avatar_url=picture)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    await attach(session, user, User.google_sub, "google_sub", sub)
    await attach(session, user, User.email, "email", email)
    if name and not user.first_name:
        user.first_name = name
    if picture and not user.avatar_url:
        user.avatar_url = picture
    await session.commit()
    return await sync_rights(session, user)


async def link_telegram(session: AsyncSession, user: User, *, tg_id: int,
                        username: str | None, name: str | None) -> User:
    """Привязка бота к уже существующему аккаунту — ради уведомлений."""
    await attach(session, user, User.tg_id, "tg_id", tg_id)
    if username:
        user.username = username
    if name and not user.first_name:
        user.first_name = name
    await session.commit()
    return await sync_rights(session, user)


def public(user: User) -> dict:
    """Что о себе видит сам пользователь."""
    return {
        "id": user.id,
        "name": user.first_name,
        "avatar_url": user.avatar_url,
        "phone": user.phone,
        "email": user.email,
        "tg_linked": user.tg_id is not None,
        "city_id": user.city_id,
        "address": user.address,
        "notify_email": user.notify_email,
        "notify_telegram": user.notify_telegram,
        "onboarding_done": user.onboarding_done,
        "is_admin": user.is_admin,
    }
