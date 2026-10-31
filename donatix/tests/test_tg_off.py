"""Telegram Stars и Premium недоступны у поставщика — их нет нигде: каталог, сайт, мини-приложение, бот, API."""

from fastapi.testclient import TestClient

from donatix import catalog


def test_stars_and_premium_hidden_everywhere(app, conn, monkeypatch):
    monkeypatch.setattr(catalog, "OFF_KINDS", ("telegram_stars", "telegram_premium"))
    from donatix.cache import clear
    clear()
    assert catalog.get_product(conn, "tg-stars") is None
    assert not [p for p in catalog.list_products(conn) if p["kind"] in catalog.OFF_KINDS]
    assert not [c for c in catalog.categories(conn) if c["kind"] in catalog.OFF_KINDS]
    assert catalog.get_product(conn, "tg-stars", for_sale=False) is not None    # старые заказы и цена подарков
    c = TestClient(app)
    r = c.get("/panel/catalog?kind=telegram", follow_redirects=False)
    assert r.status_code in (302, 303) and r.headers["location"] == "/panel/catalog"
    home = c.get("/").text
    assert "kind=telegram" not in home
    page = c.get("/panel/catalog").text
    assert "kind=telegram" not in page


def test_sync_skips_and_disables_them(app, conn, supplier, monkeypatch):
    monkeypatch.setattr(catalog, "OFF_KINDS", ("telegram_stars", "telegram_premium"))
    catalog.sync_catalog(conn, supplier)
    n = conn.execute("SELECT COUNT(*) FROM products WHERE active = 1 AND kind IN "
                     "('telegram_stars', 'telegram_premium')").fetchone()[0]
    assert n == 0
