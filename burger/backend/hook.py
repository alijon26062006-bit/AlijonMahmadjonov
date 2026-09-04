#!/usr/bin/env python3
"""Включить или выключить вебхуки Telegram. Запускать один раз после установки.

Ботов два: курьерский и админский. Команда работает с обоими сразу.

    python3 hook.py on     — сказать Telegram, куда слать нажатия
    python3 hook.py off    — отключить
    python3 hook.py info   — что сейчас настроено
"""

import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).parent


def env():
    """Читаем .env рядом со скриптом — тот же файл, что и у службы."""
    values = dict(os.environ)
    path = HERE / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                values.setdefault(key.strip(), value.strip())
    return values


def one(title, token, url, what):
    api = f'https://api.telegram.org/bot{token}'

    if what == 'on':
        r = httpx.post(f'{api}/setWebhook',
                       json={'url': url, 'allowed_updates': ['message', 'callback_query'],
                             'drop_pending_updates': True}, timeout=15)
        print(f"{title}: {r.json().get('description', r.text)}")
        print(f'  адрес: {url}')
    elif what == 'off':
        print(f"{title}: {httpx.post(f'{api}/deleteWebhook', timeout=15).json().get('description')}")
    else:
        info = httpx.get(f'{api}/getWebhookInfo', timeout=15).json().get('result', {})
        print(f"{title}: {info.get('url') or 'вебхук не задан'}")
        if info.get('last_error_message'):
            print('  последняя ошибка:', info['last_error_message'])


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'info'
    cfg = env()
    base = cfg.get('PUBLIC_URL', '').rstrip('/')

    bots = [('Бот курьеров', cfg.get('TG_TOKEN', ''),
             f"{base}/tg/{cfg.get('TG_HOOK_SECRET', '')}"),
            ('Бот админки', cfg.get('TG_ADMIN_TOKEN', ''),
             f"{base}/tg/admin/{cfg.get('TG_ADMIN_HOOK_SECRET', '')}")]

    if not any(token for _, token, _ in bots):
        sys.exit('В .env не задан ни TG_TOKEN, ни TG_ADMIN_TOKEN')

    if what == 'on' and not base:
        sys.exit('В .env нужен PUBLIC_URL — иначе Telegram некуда стучаться')

    for title, token, url in bots:
        if not token:
            print(f'{title}: токен не задан, пропускаю')
            continue
        one(title, token, url, what)


if __name__ == '__main__':
    main()
