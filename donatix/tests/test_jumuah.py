"""Пятница 13:00–14:00 по Душанбе: сайт и свой бот не продают, API — продаёт, пополнять можно."""
from datetime import datetime, timezone

import pytest

from donatix import accounts, catalog, jumuah, orders

FRI_13_30 = datetime(2026, 10, 16, 8, 30, tzinfo=timezone.utc)    # 13:30 в Душанбе (UTC+5), пятница
FRI_14_00 = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc)
FRI_12_59 = datetime(2026, 10, 16, 7, 59, tzinfo=timezone.utc)
THU_13_30 = datetime(2026, 10, 15, 8, 30, tzinfo=timezone.utc)


def test_window(config):
    assert jumuah.closed(config, FRI_13_30)
    assert not jumuah.closed(config, FRI_14_00)
    assert not jumuah.closed(config, FRI_12_59)
    assert not jumuah.closed(config, THU_13_30)


def test_sources(config, conn, shop):
    api_user = conn.execute("SELECT u.*, k.id AS api_key_id FROM users u JOIN api_keys k ON k.user_id = u.id "
                            "WHERE u.id = ?", (shop["id"],)).fetchone()
    for src in ("panel", "shopbot", "quick"):
        assert jumuah.blocks(config, None, src, FRI_13_30)
    assert not jumuah.blocks(config, None, "api", FRI_13_30)
    assert not jumuah.blocks(config, api_user, "panel", FRI_13_30)


@pytest.fixture
def friday(monkeypatch):
    monkeypatch.setattr(jumuah, "closed", lambda config, now=None: True)


def test_site_order_refused_api_ok(friday, conn, config, supplier, client, shop):
    uid = accounts.create_user(conn, email="j@example.com", login="juma1", password="password123", status="active")
    user = accounts.get_user(conn, uid)
    with pytest.raises(orders.OrderError) as e:
        orders.create_order(conn, config, supplier, user, product_id="tg-stars", quantity=100,
                            fields={"telegram_username": "@player_one"}, source="panel")
    assert e.value.code == "friday_break"
    r = client.post("/api/v1/orders", headers=shop["h"],
                    json={"product_id": "tg-stars", "quantity": 100, "fields": {"telegram_username": "@player_one"}})
    assert r.status_code == 201, r.text


def test_strip_shown(friday, client):
    assert "friday-break" in client.get("/").text


def test_no_strip_normally(client, monkeypatch):
    monkeypatch.setattr(jumuah, "closed", lambda config, now=None: False)
    assert "friday-break" not in client.get("/").text
    assert catalog is not None
