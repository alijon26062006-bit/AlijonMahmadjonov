"""Вход на сайт: по номеру телефона и через Google.

Паролей в магазине нет. Номер подтверждает Telegram, почту — Google;
хранить и восстанавливать пароли не нужно ни нам, ни покупателю.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, Db
from app.config import get_settings
from app.db.models import User
from app.security.google_auth import GoogleAuthError, verify as verify_google
from app.security.jwt_auth import issue_token
from app.services import accounts, auth_code

router = APIRouter(prefix="/api/auth", tags=["auth"])


class PhoneIn(BaseModel):
    phone: str = Field(max_length=32)


class CodeIn(BaseModel):
    key: str = Field(max_length=48)
    code: str = Field(max_length=12)


class GoogleIn(BaseModel):
    id_token: str = Field(max_length=4096)


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=160)
    city_id: int | None = None
    address: str | None = Field(default=None, max_length=255)
    notify_email: bool | None = None
    notify_telegram: bool | None = None
    onboarding_done: bool | None = None


def _session(user) -> dict:
    return {"access_token": issue_token(user.id, user.tg_id, user.is_admin),
            "user": accounts.public(user)}


@router.post("/phone/request")
async def phone_request(body: PhoneIn, session: Db):
    """Заводит заявку и отдаёт ссылку на бота.

    Кода здесь ещё нет: его выдаст бот, и только после того, как Telegram
    сам подтвердит, что номер принадлежит нажавшему.
    """
    try:
        entry = await auth_code.request(session, body.phone)
    except auth_code.AuthError as error:
        raise HTTPException(400, str(error)) from None
    s = get_settings()
    return {"key": entry.key,
            "phone": entry.phone,
            "link": f"{s.bot_link}?start=c_{entry.key}",
            "expires_in": s.code_ttl}


@router.get("/phone/status")
async def phone_status(key: str, session: Db):
    """Вкладка ждёт, пока человек нажмёт кнопку в боте.

    Как только бот сверил номер, впускаем сразу — вводить цифры уже незачем.
    Код остаётся нужен, если вкладку закрыли или входят с другого устройства.
    """
    entry = await auth_code.take_confirmed(session, key)
    if entry is None:
        return {"status": "waiting"}
    user = await accounts.login_with_phone(session, entry.phone,
                                           tg_id=entry.tg_id)
    if user.is_banned:
        raise HTTPException(403, "Доступ закрыт")
    return {"status": "confirmed", **_session(user)}


@router.post("/phone/verify")
async def phone_verify(body: CodeIn, session: Db):
    try:
        entry = await auth_code.check(session, body.key, body.code)
    except auth_code.AuthError as error:
        raise HTTPException(400, str(error)) from None
    user = await accounts.login_with_phone(session, entry.phone,
                                           tg_id=entry.tg_id)
    if user.is_banned:
        raise HTTPException(403, "Доступ закрыт")
    return _session(user)


@router.post("/google")
async def google_login(body: GoogleIn, session: Db):
    try:
        claims = await verify_google(body.id_token)
    except GoogleAuthError as error:
        raise HTTPException(401, str(error)) from None
    user = await accounts.login_with_google(session, claims)
    if user.is_banned:
        raise HTTPException(403, "Доступ закрыт")
    return _session(user)


@router.post("/telegram/link")
async def telegram_link(user: CurrentUser, session: Db):
    """Ссылка «привязать бота» для тех, кто вошёл через Google.

    Нужна ради уведомлений о заказе: письма доходят не всем и не сразу.
    Номер тут не спрашиваем и код не шлём — ссылка одноразовая и выдана
    уже вошедшему человеку, этого достаточно.
    """
    entry = await auth_code.request_link(session, user)
    return {"link": f"{get_settings().bot_link}?start=c_{entry.key}"}


@router.get("/me")
async def me(user: CurrentUser):
    return accounts.public(user)


@router.patch("/me")
async def update_me(body: ProfileIn, user: CurrentUser, session: Db):
    if body.name is not None:
        user.first_name = " ".join(body.name.split())[:128]
    if body.email is not None:
        email = body.email.strip().lower()[:160] or None
        if email != user.email:
            await accounts.attach(session, user, User.email, "email", email)
    if body.city_id is not None:
        user.city_id = body.city_id
    if body.address is not None:
        user.address = body.address.strip()[:255] or None
    if body.notify_email is not None:
        user.notify_email = body.notify_email
    if body.notify_telegram is not None:
        user.notify_telegram = body.notify_telegram
    if body.onboarding_done is not None:
        user.onboarding_done = body.onboarding_done
    await session.commit()
    return accounts.public(user)
