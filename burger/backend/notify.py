"""Уведомление о заказе в Telegram.

Если бот не настроен или Telegram недоступен — заказ всё равно сохраняется
в базе и виден в админке. Приём заказов не должен зависеть от мессенджера.
"""

import logging
import os

import httpx

log = logging.getLogger('burger.notify')

TOKEN = os.getenv('TG_TOKEN', '')
CHAT = os.getenv('TG_ADMIN_CHAT', '')

STATUS_RU = {
    'new': 'новый',
    'confirmed': 'подтверждён',
    'cooking': 'готовится',
    'done': 'выполнен',
    'canceled': 'отменён',
}


def order_text(order, items, zone_name=''):
    rows = []
    for i in items:
        opts = f" ({i['options']})" if i['options'] else ''
        rows.append(f"• {i['name']}{opts} × {i['qty']} — {i['price'] * i['qty']} сомони")

    lines = [f"🆕 Заказ №{order['number']}", '', *rows, '', f"Товары: {order['goods']} сомони"]

    if order['mode'] == 'delivery':
        cost = f"{order['delivery']} сомони" if order['delivery'] else 'бесплатно'
        lines.append(f"Доставка: {zone_name} — {cost}")
        addr = order['address'] + (f", {order['flat']}" if order['flat'] else '')
        lines.append(f"Адрес: {addr}")
        if order['landmark']:
            lines.append(f"Ориентир: {order['landmark']}")
    else:
        lines.append('Самовывоз')

    lines += [f"Итого: {order['total']} сомони", '',
              f"Имя: {order['name']}", f"Телефон: {order['phone']}"]
    if order['note']:
        lines.append(f"Комментарий: {order['note']}")

    return '\n'.join(lines)


async def send(text):
    if not TOKEN or not CHAT:
        log.warning('Telegram не настроен — заказ только в админке')
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f'https://api.telegram.org/bot{TOKEN}/sendMessage',
                json={'chat_id': CHAT, 'text': text, 'disable_web_page_preview': True})
            r.raise_for_status()
        return True
    except Exception as e:                     # заказ важнее уведомления
        log.error('Telegram не ответил: %s', e)
        return False
