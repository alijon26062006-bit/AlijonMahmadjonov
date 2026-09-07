"""Проверка initData из Telegram Mini App.

Telegram передаёт в Mini App подписанную строку initData. Подпись считается
секретом, выведенным из токена бота, поэтому подделать её нельзя, не зная
токен. Без этой проверки любой человек прислал бы серверу чужой user_id.
Документация: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

# Сутки: столько живёт подпись. Дольше — считаем, что вкладку открыли давно.
MAX_AGE_SECONDS = 24 * 60 * 60


class AuthError(Exception):
    """initData не прошла проверку."""


@dataclass(frozen=True)
class WebAppUser:
    """Тот, кто открыл Mini App. Данные взяты из подписанной строки."""

    id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    language_code: str = ""
    photo_url: str = ""
    start_param: str = ""

    @property
    def name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username or f"Игрок {self.id}"


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def check_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age: int = MAX_AGE_SECONDS,
    now: float | None = None,
) -> dict[str, str]:
    """Возвращает разобранные поля initData или бросает AuthError."""

    if not init_data:
        raise AuthError("пустая initData")

    try:
        pairs = parse_qsl(init_data, strict_parsing=True, keep_blank_values=True)
    except ValueError as exc:
        raise AuthError("initData не разбирается") from exc

    fields = dict(pairs)
    given_hash = fields.pop("hash", "")
    if not given_hash:
        raise AuthError("в initData нет подписи")

    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    expected = hmac.new(
        _secret_key(bot_token), check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, given_hash):
        raise AuthError("подпись не совпала")

    auth_date = fields.get("auth_date", "")
    if auth_date:
        try:
            issued = int(auth_date)
        except ValueError as exc:
            raise AuthError("auth_date не число") from exc
        age = (now if now is not None else time.time()) - issued
        if age > max_age:
            raise AuthError("подпись просрочена, открой приложение заново")

    return fields


def parse_user(fields: dict[str, str]) -> WebAppUser:
    """Достаёт игрока из уже проверенных полей."""

    raw = fields.get("user", "")
    if not raw:
        raise AuthError("в initData нет пользователя")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthError("поле user не читается") from exc

    try:
        user_id = int(data["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("у пользователя нет id") from exc

    return WebAppUser(
        id=user_id,
        first_name=str(data.get("first_name", "") or ""),
        last_name=str(data.get("last_name", "") or ""),
        username=str(data.get("username", "") or ""),
        language_code=str(data.get("language_code", "") or ""),
        photo_url=str(data.get("photo_url", "") or ""),
        start_param=fields.get("start_param", ""),
    )


def authenticate(
    init_data: str,
    bot_token: str,
    *,
    dev_mode: bool = False,
    dev_fallback: WebAppUser | None = None,
    max_age: int = MAX_AGE_SECONDS,
    now: float | None = None,
) -> WebAppUser:
    """Проверяет подпись и возвращает игрока.

    В dev_mode (локальная отладка без Telegram) подпись не проверяется — тогда
    берётся dev_fallback. На боевом сервере dev_mode обязан быть выключен.
    """

    if dev_mode and not init_data:
        if dev_fallback is None:
            raise AuthError("dev_mode без запасного пользователя")
        return dev_fallback

    fields = check_init_data(init_data, bot_token, max_age=max_age, now=now)
    return parse_user(fields)
