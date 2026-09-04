"""Вход через Telegram Mini App.

Telegram открывает панель прямо внутри мессенджера и передаёт странице
подписанную строку initData. Подпись проверяется здесь, ключом служит токен
бота — подделать её, не зная токена, нельзя.

Порядок проверки описан в документации Telegram: строку разбираем на пары,
вынимаем hash, остальные пары сортируем по имени и склеиваем через перевод
строки; ключ — HMAC(токен, "WebAppData"), затем HMAC этой строки.
"""

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

log = logging.getLogger('burger.webapp')

MAX_AGE = 24 * 3600          # старую подпись не принимаем


def check(init_data, token, max_age=MAX_AGE, now=None):
    """Возвращает данные пользователя или None, если подпись не сходится."""
    if not init_data or not token:
        return None

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    got = pairs.pop('hash', '')
    if not got:
        return None

    checked = '\n'.join(f'{k}={pairs[k]}' for k in sorted(pairs))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    mine = hmac.new(secret, checked.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(mine, got):
        return None

    # свежесть: перехваченную вчера ссылку сегодня уже не пустим
    try:
        issued = int(pairs.get('auth_date', 0))
    except ValueError:
        return None
    if max_age and (now or time.time()) - issued > max_age:
        return None

    try:
        user = json.loads(pairs.get('user', '{}'))
    except json.JSONDecodeError:
        return None

    return user if user.get('id') else None


def sign(data, token):
    """Собрать подписанную строку — нужно только тестам."""
    pairs = {k: str(v) for k, v in data.items()}
    checked = '\n'.join(f'{k}={pairs[k]}' for k in sorted(pairs))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    pairs['hash'] = hmac.new(secret, checked.encode(), hashlib.sha256).hexdigest()
    from urllib.parse import urlencode
    return urlencode(pairs)
