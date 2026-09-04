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
    return [
        [{'text': '📦 Доставил', 'callback_data': f"done:{o['id']}"}],
        [{'text': 'Не смогу — вернуть заказ', 'callback_data': f"drop:{o['id']}"}],
    ]


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


async def give_back(order_id, chat_id):
    """Курьер не может везти. Заказ возвращается всем — лучше так, чем молча ждать."""
    if not db.release_order(order_id, chat_id):
        return False, 'Это не ваш заказ'

    _reminded.pop(order_id, None)
    await call_couriers(order_id)
    return True, 'Заказ вернулся в общий список'


async def remind_tick(now=None):
    """Напоминание, пока заказ висит свободным. Молчать нельзя — еда стынет."""
    now = now or time.time()
    free = db.free_orders()
    due = []
    for o in free:
        count, last = _reminded.get(o['id'], (0, 0))
        if count < REMIND_MAX and now - last >= REMIND_EVERY:
            due.append(o)
    if not due:
        return 0

    # одно письмо на курьера, а не по одному на каждый заказ: иначе это спам
    head = ('⏰ Не пропустите: заказы ждут курьера'
            if len(free) > 1 else '⏰ Заказ ждёт курьера')
    text = head + '\n\n' + '\n\n'.join(free_text(o) for o in free)

    sent = 0
    for c in db.couriers(only_active=True):
        keys = [[{'text': f"🛵 Беру №{o['number']}", 'callback_data': f"take:{o['id']}"}]
                for o in free]
        if PUBLIC_URL:
            keys.append([{'text': 'Открыть панель', 'url': panel_url(c['chat_id'])}])

        mid = await notify.send_to(c['chat_id'], text, keys)
        if mid:
            for o in free:
                db.save_courier_msg(o['id'], c['chat_id'], mid)
            sent += 1

    for o in due:
        count, _ = _reminded.get(o['id'], (0, 0))
        _reminded[o['id']] = (count + 1, now)
    return sent


# ── анкета курьера в боте ───────────────────────────────

"""Три шага и ничего лишнего:
   /start → номер телефона одной кнопкой → имя → ждать допуска.
   Телефон берём только кнопкой «Отправить номер»: так это точно его номер,
   а не переписанный от руки чужой."""

ASK_PHONE = ('Здравствуйте! Это бот курьеров The Burger.\n\n'
             'Чтобы вас записать, нажмите кнопку ниже — Telegram отправит ваш номер.')
PHONE_KEYS = {'keyboard': [[{'text': '📱 Отправить мой номер', 'request_contact': True}]],
              'resize_keyboard': True, 'one_time_keyboard': True}

ASK_NAME = 'Записал номер. Теперь напишите, как вас зовут — это имя увидит кухня.'
HIDE_KEYS = {'remove_keyboard': True}

WAIT = ('Спасибо, {name}! Заявка ушла хозяину.\n'
        'Как только вас допустят, заказы начнут приходить сюда — я напишу.')
NOT_A_PHONE = 'Нажмите кнопку «📱 Отправить мой номер» — так номер придёт правильно.'


def panel_keys(chat_id):
    return [[{'text': '🛵 Открыть панель', 'url': panel_url(chat_id)}]] if PUBLIC_URL else None


def hello_ready(chat_id):
    free = len(db.free_orders())
    text = ('Вы на смене. Как только заказ будет готов — пришлю его сюда.'
            if not free else
            f'Вы на смене. Прямо сейчас свободных заказов: {free} — откройте панель.')
    return text, panel_keys(chat_id)


def admin_keys(chat_id):
    return [[{'text': '✅ Допустить', 'callback_data': f'ok:{chat_id}'},
             {'text': '✖ Отказать', 'callback_data': f'no:{chat_id}'}]]


async def start(chat, who):
    """Кнопка «Старт». Дальше зависит от того, на чём человек остановился."""
    c = db.courier(chat)

    if c and c['active']:
        hi, keys = hello_ready(chat)
        await notify.send_to(chat, hi, keys)
        return

    if not c:
        db.add_courier(chat, step='phone')
        await notify.send_to(chat, ASK_PHONE, markup=PHONE_KEYS)
        return

    if not c['phone']:
        db.update_courier(chat, step='phone')
        await notify.send_to(chat, ASK_PHONE, markup=PHONE_KEYS)
    elif not c['name']:
        db.update_courier(chat, step='name')
        await notify.send_to(chat, ASK_NAME, markup=HIDE_KEYS)
    else:
        await notify.send_to(chat, WAIT.format(name=c['name']), markup=HIDE_KEYS)


async def got_phone(chat, contact, who):
    """Номер пришёл кнопкой. Чужой контакт не принимаем."""
    if str(contact.get('user_id') or '') != str(who.get('id') or ''):
        await notify.send_to(chat, 'Это чужой номер. ' + NOT_A_PHONE, markup=PHONE_KEYS)
        return

    phone = contact.get('phone_number', '')
    if phone and not phone.startswith('+'):
        phone = '+' + phone

    db.add_courier(chat)
    db.update_courier(chat, phone=phone, step='name')
    await notify.send_to(chat, ASK_NAME, markup=HIDE_KEYS)


async def got_name(chat, name):
    name = ' '.join(name.split())[:60]
    if len(name) < 2:
        await notify.send_to(chat, 'Слишком коротко. Напишите имя целиком.')
        return

    db.update_courier(chat, name=name, step='')
    await notify.send_to(chat, WAIT.format(name=name), markup=HIDE_KEYS)

    c = db.courier(chat) or {}
    if notify.CHAT:
        await notify.send_to(
            notify.CHAT,
            f"🛵 Новый курьер\nИмя: {name}\nТелефон: {c.get('phone', '—')}",
            admin_keys(chat))


async def approve(chat_id, yes):
    """Хозяин нажал «Допустить» или «Отказать» прямо в чате с ботом."""
    c = db.courier(chat_id)
    if not c:
        return 'Такого курьера уже нет'

    if yes:
        db.set_courier_active(chat_id, True)
        hi, keys = hello_ready(chat_id)
        await notify.send_to(chat_id, f"Готово, {c['name']}! " + hi, keys)
        return f"{c['name']} на смене"

    db.delete_courier(chat_id)
    await notify.send_to(chat_id, 'К сожалению, заявку отклонили.')
    return f"{c['name']} отклонён"


# ── что приходит от Telegram ────────────────────────────

async def handle_update(update):
    """Разбираем то, что прислал Telegram: команду, анкету или нажатие кнопки."""
    msg = update.get('message') or {}
    if msg:
        chat = msg['chat']['id']
        who = msg.get('from') or {}
        text = (msg.get('text') or '').strip()

        if msg.get('contact'):
            await got_phone(chat, msg['contact'], who)
            return {'ok': True}

        if text.startswith('/start') or text.startswith('/panel'):
            await start(chat, who)
            return {'ok': True}

        c = db.courier(chat)
        if c and c['step'] == 'name' and text and not text.startswith('/'):
            await got_name(chat, text)
            return {'ok': True}

        if c and c['step'] == 'phone':
            await notify.send_to(chat, NOT_A_PHONE, markup=PHONE_KEYS)
            return {'ok': True}

        if c and c['active']:
            hi, keys = hello_ready(chat)
            await notify.send_to(chat, hi, keys)
        elif text:
            await start(chat, who)
        return {'ok': True}

    cq = update.get('callback_query')
    if cq:
        data = cq.get('data') or ''
        chat = cq['message']['chat']['id']
        mid = cq['message']['message_id']

        if data.startswith(('ok:', 'no:')):
            # допускать курьеров может только хозяин
            if not notify.CHAT or str(chat) != str(notify.CHAT):
                await notify.answer(cq['id'], 'Это может только хозяин', alert=True)
                return {'ok': True}
            said = await approve(data[3:], data.startswith('ok:'))
            await notify.answer(cq['id'], said)
            await notify.edit(chat, mid, f"{cq['message'].get('text', '')}\n\n→ {said}")
            return {'ok': True}

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

        if data.startswith('drop:'):
            ok, answer = await give_back(int(data[5:]), chat)
            await notify.answer(cq['id'], answer, alert=not ok)
            if ok:
                o = db.order(int(data[5:]))
                await notify.edit(chat, mid, f"Заказ №{o['number']} вернулся в общий список")
            return {'ok': True}

        await notify.answer(cq['id'])
    return {'ok': True}
