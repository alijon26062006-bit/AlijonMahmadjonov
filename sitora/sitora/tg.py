"""Telegram Bot API — тонкая обёртка на httpx. Проверка подписи мини-приложения (initData)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import parse_qsl

import httpx

log = logging.getLogger(__name__)


class TgError(Exception):
    def __init__(self, desc: str, code: int = 0):
        super().__init__(desc)
        self.code = code


class Bot:
    def __init__(self, token: str, transport: httpx.BaseTransport | None = None):
        self.token = token
        self._c = httpx.Client(base_url=f"https://api.telegram.org/bot{token}/", timeout=40, transport=transport)

    def call(self, method: str, files: dict | None = None, **params: Any) -> Any:
        data = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                for k, v in params.items() if v is not None}
        try:
            r = self._c.post(method, data=data, files=files) if files else self._c.post(method, data=data)
        except httpx.HTTPError as exc:
            raise TgError(f"{method}: {exc}") from exc
        try:
            body = r.json()
        except ValueError:
            raise TgError(f"{method}: HTTP {r.status_code}", r.status_code) from None
        if not body.get("ok"):
            raise TgError(f"{method}: {body.get('description')}", int(body.get("error_code") or r.status_code))
        return body.get("result")

    def send(self, chat_id: int, text: str, buttons: list | None = None, **kw: Any) -> Any:
        markup = {"inline_keyboard": buttons} if buttons else None
        return self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                         reply_markup=markup, disable_web_page_preview=True, **kw)

    def safe(self, method: str, **kw: Any) -> Any:
        try:
            return self.call(method, **kw)
        except TgError as exc:
            log.warning("telegram %s: %s", method, exc)
            return None


def check_init_data(init_data: str, token: str, max_age: int = 86400) -> dict[str, Any] | None:
    """Подпись мини-приложения: HMAC-SHA256 c ключом HMAC("WebAppData", token). Вернёт user или None."""
    if not init_data or not token:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    got = pairs.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    want = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, got):
        return None
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            return None
        user = json.loads(pairs.get("user", "{}"))
    except (ValueError, TypeError):
        return None
    return user if isinstance(user, dict) and user.get("id") else None


def sign_init_data(user: dict[str, Any], token: str, auth_date: int | None = None) -> str:
    """Для тестов: собрать подписанный initData."""
    from urllib.parse import urlencode
    pairs = {"auth_date": str(auth_date or int(time.time())), "user": json.dumps(user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)
