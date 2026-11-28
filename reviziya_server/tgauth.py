"""Проверка, что запрос пришёл из мини-аппа Telegram и от кого.

Telegram подписывает данные запуска токеном бота. Подделать подпись без токена
нельзя, поэтому серверу не нужны пароли: кто открыл мини-апп, тот и есть.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE = 3 * 24 * 3600  # ревизия идёт весь день, мини-апп могут не закрывать


class AuthError(Exception):
    pass


def check_init_data(init_data: str, bot_token: str, *, now: float | None = None, max_age: int = MAX_AGE) -> dict:
    """Возвращает пользователя Telegram ({id, first_name, ...}) или бросает AuthError."""
    if not init_data:
        raise AuthError("нет данных запуска")
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise AuthError("данные запуска повреждены") from exc

    their_hash = pairs.pop("hash", "")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    my_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(my_hash, their_hash):
        raise AuthError("подпись не сошлась")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise AuthError("нет даты запуска") from exc
    if (now if now is not None else time.time()) - auth_date > max_age:
        raise AuthError("запуск устарел, откройте мини-апп заново")

    try:
        user = json.loads(pairs["user"])
        user["id"] = int(user["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthError("нет пользователя") from exc
    return user


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Собирает подписанную строку запуска. Нужна только тестам."""
    from urllib.parse import urlencode

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})
