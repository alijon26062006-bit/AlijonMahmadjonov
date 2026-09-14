"""Кто пускается в админ-панель.

Прав два уровня, и разделение здесь не формальность.

  Владелец — тот, чей ID стоит в .env на сервере. Его нельзя снять из
  панели: иначе достаточно один раз ошибиться человеком, и бота уводят
  вместе с кассой, а вернуть его будет неоткуда.

  Админ — тот, кого владелец добавил из панели. Может всё то же, кроме
  одного: раздавать и отнимать доступ. Это остаётся за владельцем.
"""
from __future__ import annotations

from app import runtime
from app.config import settings

#: Настройка со списком добавленных админов: «111,222».
KEY = "extra_admins"


def owners() -> list[int]:
    """Владельцы из .env. Снять их можно только на сервере."""
    return list(settings.admin_ids)


def extra() -> list[int]:
    """Админы, добавленные из панели."""
    raw = (runtime.get(KEY) or "").replace(";", ",")
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            value = int(part)
            if value not in out:
                out.append(value)
    return out


def is_owner(user_id: int) -> bool:
    return user_id in owners()


def is_admin(user_id: int) -> bool:
    """Пускать ли в панель. Владелец — всегда."""
    return is_owner(user_id) or user_id in extra()


def admins() -> list[int]:
    """Все, у кого есть доступ: сначала владельцы."""
    return owners() + [uid for uid in extra() if uid not in owners()]


async def grant(conn, user_id: int) -> bool:
    """Выдать доступ. False — он уже есть."""
    if is_admin(user_id):
        return False
    current = extra() + [user_id]
    await runtime.set_value(conn, KEY, ",".join(str(uid) for uid in current))
    return True


async def revoke(conn, user_id: int) -> bool:
    """Забрать доступ. False — забирать нечего или это владелец.

    Владельца из панели не снять: его право записано на сервере, и
    отнимать его отсюда нельзя — иначе бота можно потерять целиком.
    """
    if is_owner(user_id) or user_id not in extra():
        return False
    left = [uid for uid in extra() if uid != user_id]
    await runtime.set_value(conn, KEY, ",".join(str(uid) for uid in left))
    return True
