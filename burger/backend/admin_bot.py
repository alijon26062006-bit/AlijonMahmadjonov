"""Бот админки. Отдельный от курьерского: у хозяина свой вход, у курьеров свой.

Ничего лишнего он не делает — открывает панель прямо в Telegram (Mini App)
и показывает короткую сводку за сегодня, чтобы не лезть в панель ради двух цифр.
"""

import datetime
import logging
import os

try:
    from . import db, notify
except ImportError:
    import db, notify

log = logging.getLogger('burger.admin_bot')

TOKEN = os.getenv('TG_ADMIN_TOKEN', '')
PUBLIC_URL = os.getenv('PUBLIC_URL', '').rstrip('/')
TZ_HOURS = int(os.getenv('TZ_HOURS', '5'))


def allowed(user_id):
    ids = {i.strip() for i in os.getenv('ADMIN_TG_IDS', '').split(',') if i.strip()}
    if not ids and os.getenv('TG_ADMIN_CHAT'):
        ids = {os.getenv('TG_ADMIN_CHAT').strip()}
    return not ids or str(user_id) in ids


def keys():
    """Кнопка открывает панель внутри Telegram, а не в постороннем браузере."""
    if not PUBLIC_URL:
        return None
    return [[{'text': '📊 Открыть админку', 'web_app': {'url': f'{PUBLIC_URL}/admin'}}],
            [{'text': 'Сводка за сегодня', 'callback_data': 'today'}]]


def today_text():
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=TZ_HOURS)).date().isoformat()
    s = db.stats(today, today)['total']
    waiting = db.counts()

    lines = [f'📊 Сегодня, {today[8:10]}.{today[5:7]}',
             f"Выручка: {s['money']} сомони",
             f"Заказов: {s['orders']}"]
    if s['orders']:
        lines.append(f"Средний чек: {s['average']} сомони")
    if s['canceled']:
        lines.append(f"Отменено: {s['canceled']}")

    now = sum(waiting.get(k, 0) for k in ('new', 'confirmed', 'cooking'))
    if now:
        lines.append(f'\nСейчас на кухне: {now}')
    return '\n'.join(lines)


HELLO = ('Это панель The Burger.\n'
         'Заказы, меню, кухня, курьеры и отчёт — всё внутри Telegram.')
NO_URL = ('Панель ещё не привязана к домену: в файле .env не заполнен PUBLIC_URL. '
          'Заполните его и перезапустите сервер.')
STRANGER = 'Эта панель не для вас.'


async def handle_update(update):
    """Разбираем сообщение или нажатие кнопки от хозяина."""
    msg = update.get('message') or {}
    if msg:
        chat = msg['chat']['id']
        who = msg.get('from') or {}
        if not allowed(who.get('id')):
            await notify.send_to(chat, STRANGER, token=TOKEN)
            return {'ok': True}

        await notify.send_to(chat, HELLO if PUBLIC_URL else NO_URL, keys(), token=TOKEN)
        return {'ok': True}

    cq = update.get('callback_query')
    if cq:
        who = cq.get('from') or {}
        if not allowed(who.get('id')):
            await notify.answer(cq['id'], STRANGER, alert=True, token=TOKEN)
            return {'ok': True}

        if cq.get('data') == 'today':
            await notify.answer(cq['id'], token=TOKEN)
            await notify.send_to(cq['message']['chat']['id'], today_text(), keys(), token=TOKEN)
        else:
            await notify.answer(cq['id'], token=TOKEN)
    return {'ok': True}
