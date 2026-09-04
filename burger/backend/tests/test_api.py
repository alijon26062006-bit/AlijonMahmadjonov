"""Проверки бэкенда: меню, приём заказов и защита админки."""

import importlib
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Каждый тест — своя пустая база, чтобы не зависеть от рабочих данных."""
    monkeypatch.setenv('ADMIN_PASSWORD', 'секрет-Test')
    monkeypatch.setenv('SECRET_KEY', 'x' * 32)
    monkeypatch.setenv('ORDER_COOLDOWN', '0')

    import db
    importlib.reload(db)
    db.DB_PATH = tmp_path / 'test.db'

    import app as app_module
    importlib.reload(app_module)
    app_module.db.DB_PATH = tmp_path / 'test.db'
    app_module.db.setup()
    app_module.db.seed_if_empty()

    return TestClient(app_module.app)


def test_menu_has_dishes(client):
    data = client.get('/api/menu').json()
    assert len(data['sections']) == 14
    assert len(data['dishes']) == 94
    assert data['delivery']['minOrder'] == 40
    assert any(z['price'] is None for z in data['zones'])   # за городом — по договорённости


def test_order_counts_price_on_server(client):
    """Цена берётся из базы: то, что прислал браузер, не влияет."""
    r = client.post('/api/orders', json={
        'items': [{'id': 'hamburger', 'qty': 2}],
        'mode': 'pickup', 'name': 'Тест', 'phone': '937777777',
        'total': 1, 'goods': 1,
    })
    assert r.status_code == 200
    assert r.json()['goods'] == 47 * 2
    assert r.json()['total'] == 94


def test_delivery_price_by_zone(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'shawarma-chicken', 'qty': 1}, {'id': 'espresso', 'qty': 1}],
        'mode': 'delivery', 'zone': 'shohmansur',
        'name': 'Тест', 'phone': '937777777', 'address': 'Рудаки 1',
    })
    body = r.json()
    assert body['goods'] == 39 + 13
    assert body['delivery'] == 20          # меньше 100 сомони — доставка платная


def test_free_delivery_over_threshold(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'pizza-own-35', 'qty': 1}],
        'mode': 'delivery', 'zone': 'center',
        'name': 'Тест', 'phone': '937777777', 'address': 'Рудаки 1',
    })
    assert r.json()['delivery'] == 0


def test_out_of_town_delivery_not_in_total(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'hamburger', 'qty': 1}],
        'mode': 'delivery', 'zone': 'out',
        'name': 'Тест', 'phone': '937777777', 'address': 'Гиссар',
    })
    body = r.json()
    assert body['delivery'] == 0
    assert body['total'] == body['goods']


def test_min_order_rejected(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'espresso', 'qty': 1}],
        'mode': 'delivery', 'zone': 'center',
        'name': 'Тест', 'phone': '937777777', 'address': 'Рудаки 1',
    })
    assert r.status_code == 400
    assert 'Минимальный' in r.json()['error']


def test_delivery_needs_address(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'pizza-4kinds-35', 'qty': 1}],
        'mode': 'delivery', 'zone': 'center', 'name': 'Тест', 'phone': '937777777',
    })
    assert r.status_code == 400
    assert 'адрес' in r.json()['error'].lower()


def test_unknown_dish_rejected(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'нет-такого', 'qty': 1}],
        'mode': 'pickup', 'name': 'Тест', 'phone': '937777777',
    })
    assert r.status_code == 400


def test_short_phone_rejected(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'hamburger', 'qty': 1}],
        'mode': 'pickup', 'name': 'Тест', 'phone': '123',
    })
    assert r.status_code == 400
    assert 'error' in r.json()


def test_order_numbers_grow(client):
    body = {'items': [{'id': 'hamburger', 'qty': 1}], 'mode': 'pickup',
            'name': 'Тест', 'phone': '937777777'}
    first = client.post('/api/orders', json=body).json()['number']
    second = client.post('/api/orders', json=body).json()['number']
    assert second == first + 1


def test_breakfast_has_schedule(client):
    """Завтраки поднимаются наверх меню с 7:30 до 9:00."""
    sections = {s['id']: s for s in client.get('/api/menu').json()['sections']}
    assert sections['breakfast']['showFrom'] == '07:30'
    assert sections['breakfast']['showTo'] == '09:00'
    assert sections['burgers']['showFrom'] == ''       # у остальных окна нет


def test_admin_can_change_schedule(client):
    client.post('/admin/login', data={'password': 'секрет-Test'})
    client.post('/admin/settings', data={'hours_from_breakfast': '08:00', 'hours_to_breakfast': '11:00'})
    sections = {s['id']: s for s in client.get('/api/menu').json()['sections']}
    assert sections['breakfast']['showFrom'] == '08:00'
    assert sections['breakfast']['showTo'] == '11:00'


def test_kitchen_needs_password(client):
    assert client.get('/kitchen', follow_redirects=False).status_code == 303
    assert client.get('/api/kitchen', follow_redirects=False).status_code == 303


def test_kitchen_shows_only_unfinished(client):
    """Кухня видит то, что готовится, и не видит выданное и отменённое."""
    body = {'items': [{'id': 'hamburger', 'qty': 2}], 'mode': 'pickup',
            'name': 'Тест', 'phone': '937777777'}
    first = client.post('/api/orders', json=body).json()['number']
    client.post('/api/orders', json=body)

    client.post('/admin/login', data={'password': 'секрет-Test'})
    orders = client.get('/api/kitchen').json()['orders']
    assert len(orders) == 2
    assert orders[0]['items'][0]['qty'] == 2
    assert 'price' not in orders[0]['items'][0]      # цены кухне не нужны

    done = [o for o in orders if o['number'] == first][0]
    client.post(f'/api/kitchen/{done["id"]}/status', data={'status': 'done'})
    left = client.get('/api/kitchen').json()['orders']
    assert [o['number'] for o in left] != [first]
    assert len(left) == 1


def test_kitchen_rejects_unknown_status(client):
    client.post('/api/orders', json={'items': [{'id': 'hamburger', 'qty': 1}],
                                     'mode': 'pickup', 'name': 'Т', 'phone': '937777777'})
    client.post('/admin/login', data={'password': 'секрет-Test'})
    oid = client.get('/api/kitchen').json()['orders'][0]['id']
    assert client.post(f'/api/kitchen/{oid}/status', data={'status': 'взорвать'}).status_code == 400


def test_admin_needs_password(client):
    assert client.get('/admin', follow_redirects=False).status_code == 303
    assert client.get('/admin/menu', follow_redirects=False).status_code == 303


def test_admin_login_with_cyrillic_password(client):
    """compare_digest падал на кириллице — проверяем, что вход работает."""
    r = client.post('/admin/login', data={'password': 'секрет-Test'}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers['location'] == '/admin'
    assert 'burger_admin' in r.cookies


def test_admin_can_edit_price(client):
    client.post('/admin/login', data={'password': 'секрет-Test'})
    client.post('/admin/dish/cheeseburger', data={
        'id': 'cheeseburger', 'section': 'burgers', 'name': 'Чизбургер', 'about': 'тест',
        'weight': 260, 'kcal': 620, 'cook': '15–20 мин', 'price': 31,
        'old_price': '', 'tag': 'hit', 'parts': 'Булочка\nКотлета', 'active': '1', 'position': 0,
    })
    menu = client.get('/api/menu').json()
    dish = [d for d in menu['dishes'] if d['id'] == 'cheeseburger'][0]
    assert dish['price'] == 31
    assert dish['parts'] == ['Булочка', 'Котлета']


def test_inactive_dish_hidden_and_unorderable(client):
    client.post('/admin/login', data={'password': 'секрет-Test'})
    client.post('/admin/dish/espresso', data={
        'id': 'espresso', 'section': 'coffee', 'name': 'Экспрессо', 'about': '',
        'weight': 0, 'kcal': 0, 'cook': '10–20 мин', 'price': 13,
        'old_price': '', 'tag': '', 'parts': '', 'position': 0,   # active не передан
    })
    menu = client.get('/api/menu').json()
    assert not [d for d in menu['dishes'] if d['id'] == 'espresso']

    r = client.post('/api/orders', json={
        'items': [{'id': 'espresso', 'qty': 1}], 'mode': 'pickup',
        'name': 'Тест', 'phone': '937777777'})
    assert r.status_code == 400


# ── курьеры ─────────────────────────────────────────────

def ready_delivery_order(client, address='Рудаки 10'):
    """Заказ на доставку, который кухня уже отметила готовым."""
    client.post('/api/orders', json={
        'items': [{'id': 'hamburger', 'qty': 2}], 'mode': 'delivery', 'zone': 'center',
        'name': 'Клиент', 'phone': '937777777', 'address': address})
    import db
    oid = db.orders(limit=1)[0]['id']
    client.post('/admin/login', data={'password': 'секрет-Test'})
    client.post(f'/api/kitchen/{oid}/status', data={'status': 'done'})
    return oid


def courier_link(chat_id, name, active=True):
    import courier, db
    db.add_courier(chat_id, name)
    db.set_courier_active(chat_id, active)
    return courier.token(chat_id)


def test_courier_panel_needs_link(client):
    assert client.get('/courier').status_code == 403
    assert client.get('/courier?t=подделка').status_code == 403
    assert client.get('/api/courier/orders').status_code == 403


def test_courier_sees_ready_delivery_orders(client):
    ready_delivery_order(client, 'Айни 49')
    t = courier_link(101, 'Курьер Раҳим')

    data = client.get(f'/api/courier/orders?t={t}').json()
    assert len(data['free']) == 1
    assert data['free'][0]['address'] == 'Айни 49'
    assert data['free'][0]['total'] == 94 + 15   # два гамбургера плюс доставка по центру
    assert 'phone' not in data['free'][0]        # телефон только тому, кто взял
    assert data['mine'] == []


def test_pickup_order_not_offered_to_couriers(client):
    client.post('/api/orders', json={
        'items': [{'id': 'hamburger', 'qty': 1}], 'mode': 'pickup',
        'name': 'Клиент', 'phone': '937777777'})
    import db
    oid = db.orders(limit=1)[0]['id']
    client.post('/admin/login', data={'password': 'секрет-Test'})
    client.post(f'/api/kitchen/{oid}/status', data={'status': 'done'})

    t = courier_link(102, 'Курьер')
    assert client.get(f'/api/courier/orders?t={t}').json()['free'] == []


def test_only_first_courier_gets_the_order(client):
    oid = ready_delivery_order(client)
    one = courier_link(201, 'Первый')
    two = courier_link(202, 'Второй')

    first = client.post(f'/api/courier/orders/{oid}/take?t={one}').json()
    second = client.post(f'/api/courier/orders/{oid}/take?t={two}').json()
    assert first['ok'] is True
    assert second['ok'] is False
    assert 'Первый' in second['message']

    mine = client.get(f'/api/courier/orders?t={one}').json()
    assert len(mine['mine']) == 1
    assert mine['mine'][0]['phone'] == '937777777'   # свой заказ — телефон виден
    assert mine['free'] == []

    other = client.get(f'/api/courier/orders?t={two}').json()
    assert other['free'] == [] and other['mine'] == []


def test_courier_cannot_close_foreign_order(client):
    oid = ready_delivery_order(client)
    one = courier_link(301, 'Первый')
    two = courier_link(302, 'Второй')
    client.post(f'/api/courier/orders/{oid}/take?t={one}')

    assert client.post(f'/api/courier/orders/{oid}/delivered?t={two}').json()['ok'] is False
    assert client.post(f'/api/courier/orders/{oid}/delivered?t={one}').json()['ok'] is True

    import db
    assert db.order(oid)['status'] == 'delivered'


def test_courier_without_permission_is_not_let_in(client):
    oid = ready_delivery_order(client)
    t = courier_link(401, 'Новичок', active=False)
    assert client.get(f'/api/courier/orders?t={t}').status_code == 403

    import courier, db
    db.set_courier_active(401, True)
    assert client.get(f'/api/courier/orders?t={t}').status_code == 200
    assert courier.chat_from_token(t) == '401'
    assert db.order(oid)['courier_id'] == ''


def test_telegram_hook_guards_the_address(client):
    assert client.post('/tg/чужой-адрес', json={}).status_code == 404


def test_start_in_bot_adds_courier_but_not_to_shift(client):
    import app as app_module
    import db

    r = client.post(f'/tg/{app_module.TG_HOOK}', json={'message': {
        'chat': {'id': 555}, 'from': {'first_name': 'Далер', 'last_name': 'С.'},
        'text': '/start'}})
    assert r.status_code == 200

    c = db.courier(555)
    assert c['name'] == 'Далер С.'
    assert c['active'] == 0        # пока хозяин не допустит — заказов не увидит


def test_dish_photo_is_not_claimed_without_a_file(client):
    """Блюдо без загруженного фото не должно на него ссылаться: браузер
    просил бы картинку у каждого блюда и каждый раз получал отказ."""
    import db
    assert all(not d['photo'] for d in db.dishes())

    # старая база, где фото приписано всем: setup() чинит её сам
    with db.connect() as con:
        con.execute("UPDATE dishes SET photo = id || '.jpg'")
    db.setup()
    assert all(not d['photo'] for d in db.dishes())
