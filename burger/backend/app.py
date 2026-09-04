"""The Burger — сервер сайта.

Две части:
  • публичный API — меню и приём заказов, им пользуется сайт
  • админка — заведение само добавляет блюда, цены, фото и ведёт заказы

Запуск:
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
import os
import re
import secrets
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field, field_validator

try:
    from . import courier, db, notify
except ImportError:
    import courier, db, notify

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('burger')

HERE = Path(__file__).parent
UPLOADS = HERE / 'uploads'
UPLOADS.mkdir(exist_ok=True)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
SECRET_KEY = os.getenv('SECRET_KEY', '')
ORIGINS = [o.strip() for o in os.getenv('ALLOWED_ORIGINS', '*').split(',') if o.strip()]

if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = 'burger'
    log.warning('ADMIN_PASSWORD не задан — временный пароль "burger". Задайте свой перед запуском!')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    log.warning('SECRET_KEY не задан — сгенерирован временный, входы слетят при перезапуске')

signer = URLSafeTimedSerializer(SECRET_KEY, salt='burger-admin')
courier.use_key(SECRET_KEY)

# адрес вебхука знает только Telegram — иначе кто угодно пришлёт «нажатие кнопки»
TG_HOOK = os.getenv('TG_HOOK_SECRET', '') or secrets.token_hex(8)

app = FastAPI(title='The Burger', docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=['GET', 'POST'],
                   allow_headers=['Content-Type'])
app.mount('/uploads', StaticFiles(directory=UPLOADS), name='uploads')
app.mount('/static', StaticFiles(directory=HERE / 'static'), name='static')
templates = Jinja2Templates(directory=HERE / 'templates')

db.setup()
if db.seed_if_empty():
    log.info('база наполнена начальным меню')


# ── вход в админку ──────────────────────────────────────

def current_admin(request: Request):
    token = request.cookies.get('burger_admin')
    if not token:
        return None
    try:
        signer.loads(token, max_age=7 * 24 * 3600)
        return True
    except BadSignature:
        return None


def require_admin(request: Request):
    if not current_admin(request):
        raise HTTPException(status_code=303, headers={'Location': '/admin/login'})
    return True


# ── публичный API ───────────────────────────────────────

@app.get('/api/menu')
def api_menu():
    """Всё, что нужно сайту для отрисовки меню."""
    st = db.settings()
    return {
        'sections': [{'id': s['id'], 'title': s['title'], 'note': s['note'],
                      'layout': s['layout'], 'showFrom': s['show_from'], 'showTo': s['show_to']}
                     for s in db.sections()],
        'dishes': [{
            'id': d['id'], 'section': d['section'], 'name': d['name'], 'about': d['about'],
            'weight': d['weight'], 'kcal': d['kcal'], 'cook': d['cook'],
            'price': d['price'], 'oldPrice': d['old_price'], 'tag': d['tag'],
            'parts': d['parts'], 'photo': d['photo'],
        } for d in db.dishes()],
        'addons': db.addons(),
        'removals': db.removals(),
        'zones': db.zones(),
        'delivery': {
            'freeFrom': int(st.get('free_from', 100)),
            'minOrder': int(st.get('min_order', 40)),
            'time': st.get('delivery_time', ''),
            'pickup': st.get('pickup', ''),
        },
        'contacts': {
            'phone': st.get('phone_main', ''),
            'phoneExtra': st.get('phone_extra', ''),
            'address': st.get('address', ''),
            'hours': st.get('hours', ''),
        },
    }


class OrderItem(BaseModel):
    id: str
    qty: int = Field(ge=1, le=50)
    add: list[str] = []
    remove: list[str] = []


class OrderIn(BaseModel):
    items: list[OrderItem] = Field(min_length=1, max_length=40)
    mode: str
    zone: str = ''
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=6, max_length=30)
    address: str = ''
    flat: str = ''
    landmark: str = ''
    note: str = ''

    @field_validator('mode')
    @classmethod
    def check_mode(cls, v):
        if v not in ('delivery', 'pickup'):
            raise ValueError('способ получения указан неверно')
        return v

    @field_validator('phone')
    @classmethod
    def check_phone(cls, v):
        if len(re.sub(r'\D', '', v)) < 9:
            raise ValueError('в номере не хватает цифр')
        return v.strip()


LAST_ORDERS = {}          # ip -> время последнего заказа
COOLDOWN = int(os.getenv('ORDER_COOLDOWN', '20'))   # секунд между заказами с одного адреса


@app.post('/api/orders')
async def api_order(payload: OrderIn, request: Request):
    ip = request.client.host if request.client else '?'
    now = time.time()
    if now - LAST_ORDERS.get(ip, 0) < COOLDOWN:
        raise HTTPException(429, 'Слишком часто. Подождите немного.')

    # Считаем всё по базе: цены из браузера не принимаем
    goods, items = 0, []
    for it in payload.items:
        d = db.dish(it.id)
        if not d or not d['active']:
            raise HTTPException(400, f'Блюда «{it.id}» больше нет в меню')

        price = d['price']
        names = []
        for a_id in it.add:
            a = db.addon(a_id)
            if a:
                price += a['price']
                names.append(f"+ {a['name']}")
        for r in it.remove:
            names.append(f'без {r}')

        goods += price * it.qty
        items.append({'dish_id': d['id'], 'name': d['name'], 'qty': it.qty,
                      'price': price, 'options': ', '.join(names)})

    st = db.settings()
    min_order = int(st.get('min_order', 40))
    free_from = int(st.get('free_from', 100))

    delivery, zone_name = 0, ''
    if payload.mode == 'delivery':
        if goods < min_order:
            raise HTTPException(400, f'Минимальный заказ на доставку — {min_order} сомони')
        if not payload.address.strip():
            raise HTTPException(400, 'Укажите адрес доставки')
        z = db.zone(payload.zone) or (db.zones() or [{}])[0]
        zone_name = z.get('name', '')
        if z.get('price') is not None and goods < free_from:
            delivery = z['price']

    order = {
        'number': db.next_number(), 'mode': payload.mode, 'zone': payload.zone,
        'name': payload.name.strip(), 'phone': payload.phone.strip(),
        'address': payload.address.strip(), 'flat': payload.flat.strip(),
        'landmark': payload.landmark.strip(), 'note': payload.note.strip(),
        'goods': goods, 'delivery': delivery, 'total': goods + delivery,
    }
    db.create_order(order, items)
    LAST_ORDERS[ip] = now

    await notify.send(notify.order_text(order, items, zone_name))
    log.info('заказ №%s на %s сомони', order['number'], order['total'])

    return {'number': order['number'], 'goods': goods, 'delivery': delivery,
            'total': order['total'], 'time': st.get('delivery_time', '')}


@app.get('/api/health')
def health():
    return {'ok': True, 'dishes': len(db.dishes()), 'orders': db.counts()}


# ── панель кухни ────────────────────────────────────────

KITCHEN_STATUSES = ('new', 'confirmed', 'cooking')


def kitchen_orders():
    """Заказы, которые кухня ещё готовит. Цены здесь не нужны."""
    out = []
    for o in db.orders(limit=60):
        if o['status'] not in KITCHEN_STATUSES:
            continue
        out.append({
            'id': o['id'], 'number': o['number'], 'status': o['status'],
            'created_at': o['created_at'], 'mode': o['mode'],
            'note': o['note'],
            'items': [{'name': i['name'], 'qty': i['qty'], 'options': i['options']}
                      for i in o['items']],
        })
    return out


@app.get('/kitchen', response_class=HTMLResponse)
def kitchen(request: Request, _=Depends(require_admin)):
    return templates.TemplateResponse(request, 'kitchen.html', {})


@app.get('/api/kitchen')
def api_kitchen(request: Request, _=Depends(require_admin)):
    return {'orders': kitchen_orders(), 'now': time.strftime('%Y-%m-%dT%H:%M:%S')}


@app.post('/api/kitchen/{order_id}/status')
async def api_kitchen_status(order_id: int, status: str = Form(...), _=Depends(require_admin)):
    if status not in notify.STATUS_RU:
        raise HTTPException(400, 'Неизвестный статус')
    db.set_status(order_id, status)
    if status == 'done':
        await courier.call_couriers(order_id)
    return {'ok': True}


# ── курьеры ─────────────────────────────────────────────

def current_courier(request: Request, t: str = ''):
    """Курьер входит по ссылке из бота: ?t=... Дальше ссылка лежит в куке."""
    value = t or request.cookies.get('burger_courier', '')
    chat = courier.chat_from_token(value)
    if not chat:
        return None
    c = db.courier(chat)
    return c if c and c['active'] else None


def require_courier(request: Request, t: str = ''):
    c = current_courier(request, t)
    if not c:
        raise HTTPException(403, 'Ссылка не подходит. Напишите боту /start')
    return c


@app.post('/tg/{secret}')
async def telegram_hook(secret: str, request: Request):
    """Сюда Telegram шлёт сообщения и нажатия кнопок."""
    if not secrets.compare_digest(secret.encode(), TG_HOOK.encode()):
        raise HTTPException(404, 'Не найдено')
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(400, 'Не разобрал запрос')
    return await courier.handle_update(update)


@app.get('/courier', response_class=HTMLResponse)
def courier_panel(request: Request, t: str = ''):
    c = require_courier(request, t)
    resp = templates.TemplateResponse(request, 'courier.html', {'courier': c})
    if t:
        resp.set_cookie('burger_courier', t, httponly=True, samesite='lax',
                        max_age=courier.TOKEN_AGE)
    return resp


def courier_view(o, mine=False):
    """Курьеру нужен адрес и сумма. Телефон — только по своему заказу."""
    out = {'id': o['id'], 'number': o['number'], 'address': courier.address_of(o),
           'landmark': o['landmark'], 'note': o['note'], 'total': o['total'],
           'created_at': o['created_at'],
           'items': [{'name': i['name'], 'qty': i['qty']} for i in o['items']]}
    if mine:
        out['name'] = o['name']
        out['phone'] = o['phone']
    return out


@app.get('/api/courier/orders')
def api_courier_orders(request: Request, t: str = ''):
    c = require_courier(request, t)
    data = db.courier_orders(c['chat_id'])
    return {'name': c['name'],
            'free': [courier_view(o) for o in data['free']],
            'mine': [courier_view(o, mine=True) for o in data['mine']]}


@app.post('/api/courier/orders/{order_id}/take')
async def api_courier_take(order_id: int, request: Request, t: str = ''):
    c = require_courier(request, t)
    ok, message = await courier.take(order_id, c['chat_id'])
    return {'ok': ok, 'message': message}


@app.post('/api/courier/orders/{order_id}/delivered')
async def api_courier_delivered(order_id: int, request: Request, t: str = ''):
    c = require_courier(request, t)
    ok, message = await courier.delivered(order_id, c['chat_id'])
    return {'ok': ok, 'message': message}


@app.get('/admin/couriers', response_class=HTMLResponse)
def admin_couriers(request: Request, _=Depends(require_admin)):
    return templates.TemplateResponse(request, 'couriers.html', {
        'couriers': db.couriers(), 'hook': TG_HOOK, 'public_url': courier.PUBLIC_URL,
        'bot_ready': bool(notify.TOKEN),
    })


@app.post('/admin/couriers/{chat_id}/active')
async def admin_courier_active(chat_id: str, active: str = Form(''), _=Depends(require_admin)):
    on = active == '1'
    db.set_courier_active(chat_id, on)
    if on:
        hi, keys = courier.hello_ready(chat_id)
        await notify.send_to(chat_id, hi, keys)
    return RedirectResponse('/admin/couriers', status_code=303)


@app.post('/admin/couriers/{chat_id}/delete')
def admin_courier_delete(chat_id: str, _=Depends(require_admin)):
    db.delete_courier(chat_id)
    return RedirectResponse('/admin/couriers', status_code=303)


@app.on_event('startup')
async def start_reminders():
    """Пока заказ никто не взял — бот напоминает. Кухня не должна ждать молча."""
    if not notify.TOKEN:
        return

    async def loop():
        while True:
            try:
                await courier.remind_tick()
            except Exception as e:
                log.error('напоминание курьерам не ушло: %s', e)
            await asyncio.sleep(30)

    asyncio.create_task(loop())


# ── админка ─────────────────────────────────────────────

@app.get('/admin/login', response_class=HTMLResponse)
def login_form(request: Request, error: str = ''):
    return templates.TemplateResponse(request, 'login.html', {'error': error})


@app.post('/admin/login')
def login(request: Request, password: str = Form('')):
    if not secrets.compare_digest(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')):
        return RedirectResponse('/admin/login?error=1', status_code=303)
    resp = RedirectResponse('/admin', status_code=303)
    resp.set_cookie('burger_admin', signer.dumps('ok'), httponly=True,
                    samesite='lax', max_age=7 * 24 * 3600)
    return resp


@app.get('/admin/logout')
def logout():
    resp = RedirectResponse('/admin/login', status_code=303)
    resp.delete_cookie('burger_admin')
    return resp


@app.get('/admin', response_class=HTMLResponse)
def admin_orders(request: Request, _=Depends(require_admin), status: str = ''):
    return templates.TemplateResponse(request, 'orders.html', {
        'orders': db.orders(status or None),
        'counts': db.counts(), 'status': status, 'status_ru': notify.STATUS_RU,
        'zones': {z['id']: z['name'] for z in db.zones()},
    })


@app.post('/admin/orders/{order_id}/status')
async def admin_set_status(order_id: int, status: str = Form(...), _=Depends(require_admin)):
    if status in notify.STATUS_RU:
        db.set_status(order_id, status)
        if status == 'done':
            await courier.call_couriers(order_id)
    return RedirectResponse('/admin', status_code=303)


@app.get('/admin/menu', response_class=HTMLResponse)
def admin_menu(request: Request, _=Depends(require_admin)):
    by_section = {}
    for d in db.dishes(only_active=False):
        by_section.setdefault(d['section'], []).append(d)
    return templates.TemplateResponse(request, 'menu.html', {
        'sections': db.sections(), 'by_section': by_section})


@app.get('/admin/dish/{dish_id}', response_class=HTMLResponse)
def admin_dish(request: Request, dish_id: str, _=Depends(require_admin)):
    d = db.dish(dish_id) if dish_id != 'new' else None
    if dish_id != 'new' and not d:
        raise HTTPException(404, 'Блюдо не найдено')
    return templates.TemplateResponse(request, 'dish.html', {
        'dish': d, 'sections': db.sections(), 'new': dish_id == 'new'})


SLUG_OK = re.compile(r'^[a-z0-9-]{2,40}$')


@app.post('/admin/dish/{dish_id}')
async def admin_save_dish(
    request: Request, dish_id: str, _=Depends(require_admin),
    id: str = Form(...), section: str = Form(...), name: str = Form(...),
    about: str = Form(''), weight: int = Form(0), kcal: int = Form(0), cook: str = Form(''),
    price: int = Form(...), old_price: str = Form(''), tag: str = Form(''),
    parts: str = Form(''), active: str = Form(''), position: int = Form(0),
    photo: UploadFile = File(None),
):
    new = dish_id == 'new'
    slug = id.strip().lower()
    if not SLUG_OK.match(slug):
        raise HTTPException(400, 'Адрес блюда: латиница, цифры и дефис, от 2 знаков')
    if new and db.dish(slug):
        raise HTTPException(400, 'Блюдо с таким адресом уже есть')
    if price < 0:
        raise HTTPException(400, 'Цена не может быть отрицательной')

    old = db.dish(slug) if not new else None
    filename = old['photo'] if old else f'{slug}.jpg'

    if photo and photo.filename:
        ext = Path(photo.filename).suffix.lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
            raise HTTPException(400, 'Фото должно быть jpg, png или webp')
        data = await photo.read()
        if len(data) > 6 * 1024 * 1024:
            raise HTTPException(400, 'Фото больше 6 МБ — сожмите его')
        filename = f'{slug}{ext}'
        (UPLOADS / filename).write_bytes(data)

    db.save_dish({
        'id': slug, 'section': section, 'name': name.strip(), 'about': about.strip(),
        'weight': weight, 'kcal': kcal, 'cook': cook.strip(), 'price': price,
        'old_price': int(old_price) if old_price.strip().isdigit() else None,
        'tag': tag, 'photo': filename, 'active': 1 if active else 0, 'position': position,
        'parts': [p.strip() for p in parts.splitlines() if p.strip()],
    }, new=new)

    return RedirectResponse('/admin/menu', status_code=303)


@app.post('/admin/dish/{dish_id}/delete')
def admin_delete_dish(dish_id: str, _=Depends(require_admin)):
    db.delete_dish(dish_id)
    return RedirectResponse('/admin/menu', status_code=303)


@app.get('/admin/settings', response_class=HTMLResponse)
def admin_settings(request: Request, _=Depends(require_admin), saved: str = ''):
    return templates.TemplateResponse(request, 'settings.html', {
        'settings': db.settings(), 'zones': db.zones(), 'sections': db.sections(),
        'addons': db.addons(), 'saved': saved})


@app.post('/admin/settings')
async def admin_save_settings(request: Request, _=Depends(require_admin)):
    form = await request.form()

    for key in ('free_from', 'min_order', 'delivery_time', 'pickup',
                'phone_main', 'phone_extra', 'address', 'hours'):
        if key in form:
            db.save_setting(key, str(form[key]).strip())

    for z in db.zones():
        name = form.get(f'zone_name_{z["id"]}')
        price = str(form.get(f'zone_price_{z["id"]}', '')).strip()
        if name:
            db.save_zone(z['id'], str(name).strip(), int(price) if price.isdigit() else None)

    for sec in db.sections():
        if f'hours_from_{sec["id"]}' in form:
            db.save_section_hours(sec['id'],
                                  str(form.get(f'hours_from_{sec["id"]}', '')).strip(),
                                  str(form.get(f'hours_to_{sec["id"]}', '')).strip())

    for a in db.addons():
        name = form.get(f'addon_name_{a["id"]}')
        price = str(form.get(f'addon_price_{a["id"]}', '')).strip()
        if name and price.isdigit():
            db.save_addon(a['id'], a['section'], str(name).strip(), int(price))

    return RedirectResponse('/admin/settings?saved=1', status_code=303)


FIELD_RU = {
    'name': 'имя', 'phone': 'телефон', 'items': 'состав заказа',
    'mode': 'способ получения', 'address': 'адрес',
}


@app.exception_handler(RequestValidationError)
async def bad_fields(request: Request, exc: RequestValidationError):
    spots = []
    for e in exc.errors():
        field = e['loc'][-1] if e.get('loc') else ''
        spots.append(FIELD_RU.get(str(field), str(field)))
    where = ', '.join(dict.fromkeys(s for s in spots if s))
    return JSONResponse({'error': f'Проверьте поля: {where}' if where else 'Проверьте данные заказа'},
                        status_code=400)


# Сам сайт. На бою его быстрее отдаёт Caddy, но пусть и один сервер умеет всё:
# так `run.sh` на своей машине показывает ровно то же, что увидит клиент.
SITE = HERE.parent
if (SITE / 'index.html').exists():
    app.mount('/', StaticFiles(directory=SITE, html=True), name='site')


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 303 and 'Location' in (exc.headers or {}):
        return RedirectResponse(exc.headers['Location'], status_code=303)
    if request.url.path.startswith('/api/'):
        return JSONResponse({'error': exc.detail}, status_code=exc.status_code)
    return templates.TemplateResponse(request, 'error.html', {'detail': exc.detail},
                                      status_code=exc.status_code)
