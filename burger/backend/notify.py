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
    'done': 'готов',
    'on_way': 'у курьера',
    'delivered': 'доставлен',
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


async def call(method, payload):
    """Один вызов Telegram. Молча возвращает None, если бот не настроен или молчит."""
    if not TOKEN:
        log.warning('Telegram не настроен (TG_TOKEN пуст)')
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f'https://api.telegram.org/bot{TOKEN}/{method}', json=payload)
            data = r.json()
        if not data.get('ok'):
            log.error('Telegram отказал (%s): %s', method, data.get('description'))
            return None
        return data.get('result')
    except Exception as e:                     # заказ важнее уведомления
        log.error('Telegram не ответил (%s): %s', method, e)
        return None


async def send(text):
    """Сообщение владельцу — о новом заказе."""
    if not CHAT:
        log.warning('TG_ADMIN_CHAT не задан — заказ только в админке')
        return False
    return await send_to(CHAT, text) is not None


async def send_to(chat_id, text, keyboard=None):
    """Сообщение конкретному человеку. Возвращает id сообщения."""
    payload = {'chat_id': str(chat_id), 'text': text, 'disable_web_page_preview': True}
    if keyboard:
        payload['reply_markup'] = {'inline_keyboard': keyboard}
    res = await call('sendMessage', payload)
    return res.get('message_id') if res else None


async def edit(chat_id, message_id, text, keyboard=None):
    """Переписать уже отправленное сообщение — так заказ «исчезает» у остальных."""
    payload = {'chat_id': str(chat_id), 'message_id': message_id, 'text': text,
               'disable_web_page_preview': True}
    payload['reply_markup'] = {'inline_keyboard': keyboard or []}
    return await call('editMessageText', payload) is not None


async def answer(callback_id, text='', alert=False):
    """Ответ на нажатие кнопки — всплывашка у курьера."""
    return await call('answerCallbackQuery',
                      {'callback_query_id': callback_id, 'text': text, 'show_alert': alert})
