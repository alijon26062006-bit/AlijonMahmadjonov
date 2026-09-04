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
    assert len(data['sections']) == 5
    assert len(data['dishes']) == 25
    assert data['delivery']['minOrder'] == 40
    assert any(z['price'] is None for z in data['zones'])   # за городом — по договорённости


def test_order_counts_price_on_server(client):
    """Цена берётся из базы: то, что прислал браузер, не влияет."""
    r = client.post('/api/orders', json={
        'items': [{'id': 'classic', 'qty': 2, 'add': ['cheese']}],
        'mode': 'pickup', 'name': 'Тест', 'phone': '937777777',
        'total': 1, 'goods': 1,
    })
    assert r.status_code == 200
    assert r.json()['goods'] == (25 + 5) * 2
    assert r.json()['total'] == 60


def test_delivery_price_by_zone(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'bbq-bacon', 'qty': 1}, {'id': 'fries', 'qty': 1}],
        'mode': 'delivery', 'zone': 'shohmansur',
        'name': 'Тест', 'phone': '937777777', 'address': 'Рудаки 1',
    })
    body = r.json()
    assert body['goods'] == 34 + 12
    assert body['delivery'] == 20          # меньше 100 сомони — доставка платная


def test_free_delivery_over_threshold(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'set-company', 'qty': 1}],
        'mode': 'delivery', 'zone': 'center',
        'name': 'Тест', 'phone': '937777777', 'address': 'Рудаки 1',
    })
    assert r.json()['delivery'] == 0


def test_out_of_town_delivery_not_in_total(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'cheeseburger', 'qty': 3}],
        'mode': 'delivery', 'zone': 'out',
        'name': 'Тест', 'phone': '937777777', 'address': 'Гиссар',
    })
    body = r.json()
    assert body['delivery'] == 0
    assert body['total'] == body['goods']


def test_min_order_rejected(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'cheeseburger', 'qty': 1}],
        'mode': 'delivery', 'zone': 'center',
        'name': 'Тест', 'phone': '937777777', 'address': 'Рудаки 1',
    })
    assert r.status_code == 400
    assert 'Минимальный' in r.json()['error']


def test_delivery_needs_address(client):
    r = client.post('/api/orders', json={
        'items': [{'id': 'set-duo', 'qty': 1}],
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
        'items': [{'id': 'classic', 'qty': 1}],
        'mode': 'pickup', 'name': 'Тест', 'phone': '123',
    })
    assert r.status_code == 400
    assert 'error' in r.json()


def test_order_numbers_grow(client):
    body = {'items': [{'id': 'classic', 'qty': 1}], 'mode': 'pickup',
            'name': 'Тест', 'phone': '937777777'}
    first = client.post('/api/orders', json=body).json()['number']
    second = client.post('/api/orders', json=body).json()['number']
    assert second == first + 1


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
    client.post('/admin/dish/classic', data={
        'id': 'classic', 'section': 'burgers', 'name': 'Классик', 'about': 'тест',
        'weight': 260, 'kcal': 620, 'cook': '12 мин', 'price': 31,
        'old_price': '', 'tag': 'hit', 'parts': 'Булочка\nКотлета', 'active': '1', 'position': 0,
    })
    menu = client.get('/api/menu').json()
    dish = [d for d in menu['dishes'] if d['id'] == 'classic'][0]
    assert dish['price'] == 31
    assert dish['parts'] == ['Булочка', 'Котлета']


def test_inactive_dish_hidden_and_unorderable(client):
    client.post('/admin/login', data={'password': 'секрет-Test'})
    client.post('/admin/dish/fries', data={
        'id': 'fries', 'section': 'snacks', 'name': 'Картошка фри', 'about': '',
        'weight': 150, 'kcal': 340, 'cook': '8 мин', 'price': 12,
        'old_price': '', 'tag': '', 'parts': 'Картофель', 'position': 0,   # active не передан
    })
    menu = client.get('/api/menu').json()
    assert not [d for d in menu['dishes'] if d['id'] == 'fries']

    r = client.post('/api/orders', json={
        'items': [{'id': 'fries', 'qty': 1}], 'mode': 'pickup',
        'name': 'Тест', 'phone': '937777777'})
    assert r.status_code == 400
