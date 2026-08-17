"""Валидация Telegram initData.

Критичные детали (проверены по актуальному поведению Bot API):
- secret_key = HMAC_SHA256(key=b"WebAppData", msg=BOT_TOKEN) — именно в таком порядке;
- из строки проверки исключается ТОЛЬКО hash; поле signature остаётся;
- parse_qsl декодирует значения ровно один раз — второй раз декодировать нельзя;
- auth_date Telegram не проверяет — TTL добавляем сами.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from app.config import get_settings


class InitDataError(Exception):
    pass


def validate_init_data(init_data: str) -> dict:
    """Проверяет подпись и срок; возвращает распарсенное поле user."""
    s = get_settings()
    if not init_data or len(init_data) > 4096:
        raise InitDataError("bad_init_data")

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise InitDataError("bad_init_data") from None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise InitDataError("no_hash")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", s.bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise InitDataError("bad_signature")

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        raise InitDataError("bad_auth_date") from None
    now = time.time()
    if now - auth_date > s.init_data_ttl or auth_date - now > 60:
        raise InitDataError("expired")

    try:
        user = json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        raise InitDataError("bad_user") from None
    if not user.get("id"):
        raise InitDataError("no_user")

    return {"user": user, "start_param": parsed.get("start_param")}
