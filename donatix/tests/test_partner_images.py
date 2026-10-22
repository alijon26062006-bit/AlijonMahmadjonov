"""Картинки для партнёров: только наша ссылка (donatix.tj/media/…), ссылка поставщика — никогда."""
from donatix import catalog_job, db

SUPPLIER = "https://cdn.supplier-example.com/covers/ff.png"
BASE = "https://donatix.tj"


def _product(conn, pid, image):
    with db.tx(conn):
        conn.execute("INSERT INTO products (id, kind, category_id, category_name, name, base_price, unit, min_qty, "
                     "max_qty, stock, fields_json, supplier_ref_json, active, updated_at, image_url, region) "
                     "VALUES (?, 'topup', 'pubg_mobile', 'PUBG Mobile', ?, '1.0', 'item', 1, 10, 0, '[]', '{}', 1, ?, ?, '')",
                     (pid, f"{pid} 100", db.now(), image))


def test_api_gets_our_media_url_and_never_supplier(client, conn, shop, monkeypatch):
    key = catalog_job._key(SUPPLIER)
    monkeypatch.setattr(catalog_job, "_images", {key: f"{key}.png"})
    monkeypatch.setattr(catalog_job, "_thumbs", set())
    monkeypatch.setattr(catalog_job, "_base", BASE)
    _product(conn, "topup-a1", SUPPLIER)
    _product(conn, "topup-b2", "https://cdn.supplier-example.com/not-downloaded.png")
    from donatix import cache
    cache.clear()

    items = client.get("/api/v1/products?kind=topup", headers=shop["h"]).json()["items"]
    by_id = {i["product_id"]: i for i in items}
    assert by_id["topup-a1"]["image_url"] == f"{BASE}/media/{key}.png"
    assert by_id["topup-b2"]["image_url"] is None          # не скачана — пусто, а не ссылка поставщика

    cats = client.get("/api/v1/categories", headers=shop["h"]).json()["items"]
    assert all("supplier-example" not in str(c) for c in cats)
    ff = next(c for c in cats if c["category_id"] == "pubg_mobile")
    assert ff["image_url"].startswith(f"{BASE}/media/")

    for path in ("/api/v1/products?kind=topup", "/api/v1/categories"):
        assert "supplier-example" not in client.get(path, headers=shop["h"]).text


def test_compat_v2_gets_our_media_url(client, conn, shop, monkeypatch):
    key = catalog_job._key(SUPPLIER)
    monkeypatch.setattr(catalog_job, "_images", {key: f"{key}.png"})
    monkeypatch.setattr(catalog_job, "_thumbs", set())
    monkeypatch.setattr(catalog_job, "_base", BASE)
    _product(conn, "topup-a1", SUPPLIER)
    from donatix import cache
    cache.clear()
    text = client.get("/api/v2/topups/offers?category_id=pubg_mobile", headers=shop["h"]).text
    assert "supplier-example" not in text
