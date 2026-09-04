"""Курьеры через Telegram-бота.

Как это работает у ребят на смене:
кухня отмечает заказ готовым → бот пишет всем курьерам, кто на смене →
кто первый нажал «Беру», тому заказ и достаётся, у остальных сообщение
переписывается на «Заказ забрал такой-то». Пока никто не взял, бот
напоминает ещё несколько раз.
"""

import logging
import os
import secrets
import time

from itsdangerous import BadSignature, URLSafeTimedSerializer

try:
    from . import db, notify
except ImportError:
    import db, notify

log = logging.getLogger('burger.courier')

PUBLIC_URL = os.getenv('PUBLIC_URL', '').rstrip('/')
TOKEN_AGE = 90 * 24 * 3600          # ссылка на панель живёт три месяца

REMIND_EVERY = 120                  # раз в две минуты, пока заказ не забрали
REMIND_MAX = 5

_signer = URLSafeTimedSerializer(os.getenv('SECRET_KEY') or secrets.token_hex(32),
                                 salt='burger-courier')
_reminded = {}                      # order_id -> (сколько раз, когда в последний)


def use_key(key):
    """Ключ подписи берём тот же, что и у админки."""
    global _signer
    _signer = URLSafeTimedSerializer(key, salt='burger-courier')


# ── ссылка на панель ────────────────────────────────────

def token(chat_id):
    return _signer.dumps(str(chat_id))


def chat_from_token(value):
    if not value:
        return None
    try:
        return _signer.loads(value, max_age=TOKEN_AGE)
    except BadSignature:
        return None


def panel_url(chat_id):
    return f'{PUBLIC_URL}/courier?t={token(chat_id)}'


# ── тексты и кнопки ─────────────────────────────────────

def address_of(o):
    addr = o['address'] or '—'
    if o['flat']:
        addr += f", {o['flat']}"
    return addr


def free_text(o):
    """Что видно, пока заказ свободен. Телефон — только тому, кто взял."""
    lines = [f"🛵 Заказ №{o['number']} — доставка",
             address_of(o)]
    if o['landmark']:
        lines.append(f"Ориентир: {o['landmark']}")
    lines.append(f"К оплате: {o['total']} сомони")
    if o['note']:
        lines.append(f"Комментарий: {o['note']}")
    return '\n'.join(lines)


def mine_text(o):
    lines = [f"✅ Заказ №{o['number']} — ваш",
             address_of(o)]
    if o['landmark']:
        lines.append(f"Ориентир: {o['landmark']}")
    lines += [f"Клиент: {o['name']}", f"Телефон: {o['phone']}",
              f"К оплате: {o['total']} сомони"]
    if o['note']:
        lines.append(f"Комментарий: {o['note']}")
    return '\n'.join(lines)


def taken_text(o, who):
    return f"Заказ №{o['number']} уже забрал {who}."


def free_keys(o, chat_id):
    keys = [[{'text': '🛵 Беру заказ', 'callback_data': f"take:{o['id']}"}]]
    if PUBLIC_URL:
        keys.append([{'text': 'Открыть панель', 'url': panel_url(chat_id)}])
    return keys


def mine_keys(o):
    return [[{'text': '📦 Доставил', 'callback_data': f"done:{o['id']}"}]]


# ── рассылка ────────────────────────────────────────────

async def call_couriers(order_id):
    """Позвать всех, кто на смене. Кому не дошло — не беда, панель никуда не делась."""
    o = db.order(order_id)
    if not o or o['mode'] != 'delivery' or o['courier_id']:
        return 0

    sent = 0
    for c in db.couriers(only_active=True):
        mid = await notify.send_to(c['chat_id'], free_text(o), free_keys(o, c['chat_id']))
        if mid:
            db.save_courier_msg(order_id, c['chat_id'], mid)
            sent += 1
    if sent:
        _reminded[order_id] = (0, time.time())
    return sent


async def close_for_others(order_id, winner_chat, winner_name):
    """У остальных курьеров заказ пропадает из чата."""
    o = db.order(order_id)
    for m in db.courier_msgs(order_id):
        if m['chat_id'] == str(winner_chat):
            continue
        await notify.edit(m['chat_id'], m['message_id'], taken_text(o, winner_name))
    db.clear_courier_msgs(order_id)
    _reminded.pop(order_id, None)


async def take(order_id, chat_id):
    """Курьер жмёт «Беру». Возвращает (получилось, текст ответа)."""
    c = db.courier(chat_id)
    if not c or not c['active']:
        return False, 'Вас ещё не допустили к заказам'

    if db.take_order(order_id, chat_id, c['name']):
        await close_for_others(order_id, chat_id, c['name'])
        return True, 'Заказ ваш. Адрес и телефон в сообщении'

    o = db.order(order_id)
    if o and o['courier_id'] == str(chat_id):
        return True, 'Этот заказ и так ваш'
    who = o['courier_name'] if o else ''
    return False, f'Уже забрал {who}' if who else 'Заказ больше не свободен'


async def delivered(order_id, chat_id):
    if db.deliver_order(order_id, chat_id):
        return True, 'Записал. Спасибо!'
    return False, 'Это не ваш заказ'


async def remind_tick(now=None):
    """Напоминание, пока заказ висит свободным. Молчать нельзя — еда стынет."""
    now = now or time.time()
    sent = 0
    for o in db.free_orders():
        count, last = _reminded.get(o['id'], (0, 0))
        if count >= REMIND_MAX or now - last < REMIND_EVERY:
            continue
        text = f"⏰ Заказ №{o['number']} ещё никто не взял\n\n" + free_text(o)
        for c in db.couriers(only_active=True):
            mid = await notify.send_to(c['chat_id'], text, free_keys(o, c['chat_id']))
            if mid:
                db.save_courier_msg(o['id'], c['chat_id'], mid)
                sent += 1
        _reminded[o['id']] = (count + 1, now)
    return sent


# ── что приходит от Telegram ────────────────────────────

HELLO_NEW = ('Здравствуйте! Вы записаны курьером The Burger.\n'
             'Осталось дождаться, пока вас допустят — тогда заказы начнут приходить сюда.')


def hello_ready(chat_id):
    text = 'Вы на смене. Как только заказ будет готов — пришлю его сюда.'
    keys = [[{'text': 'Открыть панель', 'url': panel_url(chat_id)}]] if PUBLIC_URL else None
    return text, keys


async def handle_update(update):
    """Разбираем то, что прислал Telegram: команду или нажатие кнопки."""
    msg = update.get('message') or {}
    text = (msg.get('text') or '').strip()
    if text.startswith('/start') or text.startswith('/panel'):
        chat = msg['chat']['id']
        who = msg.get('from') or {}
        name = ' '.join(x for x in (who.get('first_name'), who.get('last_name')) if x) \
            or who.get('username') or f'Курьер {chat}'

        known = db.courier(chat)
        db.add_courier(chat, name)
        if known and known['active']:
            hi, keys = hello_ready(chat)
            await notify.send_to(chat, hi, keys)
        else:
            await notify.send_to(chat, HELLO_NEW)
        return {'ok': True}

    cq = update.get('callback_query')
    if cq:
        data = cq.get('data') or ''
        chat = cq['message']['chat']['id']
        mid = cq['message']['message_id']

        if data.startswith('take:'):
            ok, answer = await take(int(data[5:]), chat)
            await notify.answer(cq['id'], answer, alert=not ok)
            o = db.order(int(data[5:]))
            if ok and o:
                await notify.edit(chat, mid, mine_text(o), mine_keys(o))
            elif o:
                await notify.edit(chat, mid, taken_text(o, o['courier_name']))
            return {'ok': True}

        if data.startswith('done:'):
            ok, answer = await delivered(int(data[5:]), chat)
            await notify.answer(cq['id'], answer, alert=not ok)
            if ok:
                o = db.order(int(data[5:]))
                await notify.edit(chat, mid, f"📦 Заказ №{o['number']} доставлен")
            return {'ok': True}

        await notify.answer(cq['id'])
    return {'ok': True}
