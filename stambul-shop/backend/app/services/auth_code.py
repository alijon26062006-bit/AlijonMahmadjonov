"""Вход по номеру телефона с подтверждением через Telegram.

Почему так, а не SMS: сообщения оператора стоят денег и требуют договора,
а бот присылает код бесплатно и мгновенно.

Почему бот сначала просит контакт, а не сразу шлёт код: иначе любой мог бы
ввести чужой номер и получить код себе. Кнопка «Отправить мой номер» —
штатная возможность Telegram, и номер в ней подставляет сам мессенджер,
руками его не подделать. Совпал с введённым на сайте — выдаём код.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AuthCode, User


class AuthError(Exception):
    """Ошибка входа, которую нужно показать человеку словами."""


def normalize_phone(raw: str | None) -> str | None:
    """Приводит номер к виду +7XXXXXXXXXX.

    Люди пишут номер как придётся: с восьмёркой, с пробелами, в скобках.
    Сравнивать и хранить нужно одну форму, иначе один и тот же человек
    заведёт себе два аккаунта.
    """
    if not raw:
        return None
    digits = "".join(c for c in str(raw) if c.isdigit())
    if len(digits) == 10 and digits[0] == "7":      # 7XX без кода страны
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":    # 8XXX — привычная форма
        digits = "7" + digits[1:]
    if len(digits) != 11 or digits[0] != "7":
        return None
    return "+" + digits


def _hash(code: str, key: str) -> str:
    s = get_settings()
    return hmac.new(s.jwt_secret.encode(), f"{key}:{code}".encode(),
                    hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def request(session: AsyncSession, raw_phone: str) -> AuthCode:
    """Создаёт заявку на вход. Кода в ней пока нет — его выдаст бот."""
    phone = normalize_phone(raw_phone)
    if phone is None:
        raise AuthError("Введите номер в формате +7 (7XX) XXX-XX-XX")

    s = get_settings()
    since = _now() - timedelta(hours=1)
    recent = await session.scalar(
        select(func.count()).select_from(AuthCode)
        .where(AuthCode.phone == phone, AuthCode.created_at >= since)) or 0
    if recent >= s.code_per_hour:
        raise AuthError("Слишком много попыток. Повторите через час")

    entry = AuthCode(key=secrets.token_urlsafe(24)[:32], phone=phone,
                     purpose="login",
                     expires_at=_now() + timedelta(seconds=s.code_ttl))
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def request_link(session: AsyncSession, user: User) -> AuthCode:
    """Заявка на привязку бота к уже открытому аккаунту.

    Здесь ни номера, ни кода: ссылку получил человек, который уже вошёл,
    и она одноразовая. Просить его после этого что-то подтверждать — лишний
    шаг ради того же результата.
    """
    entry = AuthCode(
        key=secrets.token_urlsafe(24)[:32], purpose="link", user_id=user.id,
        phone=user.phone or "",
        expires_at=_now() + timedelta(seconds=get_settings().code_ttl))
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def by_key(session: AsyncSession, key: str) -> AuthCode | None:
    return await session.scalar(select(AuthCode).where(AuthCode.key == key[:48]))


def alive(entry: AuthCode | None) -> bool:
    return bool(entry and entry.used_at is None
                and entry.expires_at > _now())


async def confirm(session: AsyncSession, entry: AuthCode, *,
                  contact_phone: str, tg_id: int) -> str:
    """Бот сверил номер — записываем подтверждение и возвращаем код.

    Повторное нажатие на ту же ссылку выдаёт тот же код: человек мог
    закрыть чат и вернуться, и новый код только запутал бы его.
    """
    if not alive(entry):
        raise AuthError("Срок заявки истёк. Начните вход заново")
    if normalize_phone(contact_phone) != entry.phone:
        raise AuthError("Этот номер не совпадает с тем, что ввели на сайте")

    code = "".join(secrets.choice("0123456789")
                   for _ in range(get_settings().code_len))
    entry.code_hash = _hash(code, entry.key)
    entry.tg_id = tg_id
    entry.confirmed_at = _now()
    entry.attempts = 0
    await session.commit()
    return code


async def check(session: AsyncSession, key: str, code: str) -> AuthCode:
    """Сверяет введённые цифры. Возвращает заявку, помечая её использованной."""
    entry = await by_key(session, key)
    if not alive(entry) or entry.code_hash is None:
        raise AuthError("Срок кода истёк. Запросите новый")
    if entry.attempts >= get_settings().code_max_attempts:
        raise AuthError("Слишком много неверных попыток. Запросите новый код")

    digits = "".join(c for c in code if c.isdigit())
    if not hmac.compare_digest(_hash(digits, entry.key), entry.code_hash):
        entry.attempts += 1
        await session.commit()
        left = get_settings().code_max_attempts - entry.attempts
        raise AuthError(f"Неверный код. Осталось попыток: {max(left, 0)}")

    entry.used_at = _now()
    await session.commit()
    return entry


async def mark_used(session: AsyncSession, entry: AuthCode) -> None:
    entry.used_at = _now()
    await session.commit()


async def take_confirmed(session: AsyncSession, key: str) -> AuthCode | None:
    """Для вкладки, которая ждёт: бот подтвердил — можно впускать без цифр."""
    entry = await by_key(session, key)
    if not alive(entry) or entry.confirmed_at is None:
        return None
    entry.used_at = _now()
    await session.commit()
    return entry
