#!/usr/bin/env python3
"""Включить или выключить вебхук Telegram. Запускать один раз после установки.

    python3 hook.py on     — сказать Telegram, куда слать нажатия курьеров
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


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'info'
    cfg = env()
    token = cfg.get('TG_TOKEN', '')
    if not token:
        sys.exit('В .env не задан TG_TOKEN')

    api = f'https://api.telegram.org/bot{token}'

    if what == 'on':
        base = cfg.get('PUBLIC_URL', '').rstrip('/')
        secret = cfg.get('TG_HOOK_SECRET', '')
        if not base or not secret:
            sys.exit('В .env нужны PUBLIC_URL и TG_HOOK_SECRET')
        url = f'{base}/tg/{secret}'
        r = httpx.post(f'{api}/setWebhook',
                       json={'url': url, 'allowed_updates': ['message', 'callback_query'],
                             'drop_pending_updates': True}, timeout=15)
        print(r.json().get('description', r.text))
        print('Адрес вебхука:', url)
    elif what == 'off':
        print(httpx.post(f'{api}/deleteWebhook', timeout=15).json().get('description'))
    else:
        info = httpx.get(f'{api}/getWebhookInfo', timeout=15).json().get('result', {})
        print('Адрес:', info.get('url') or 'не задан')
        if info.get('last_error_message'):
            print('Последняя ошибка:', info['last_error_message'])


if __name__ == '__main__':
    main()
