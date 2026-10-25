"""Жалоба правообладателя: игру показываем как «FF <регион>», без их картинок."""
from donatix import catalog, db
from donatix.suppliers.base import FF_COVER, brand_safe, is_ff


def test_names():
    assert brand_safe("Free Fire (CIS)") == "FF СНГ"
    assert brand_safe("Free Fire — СНГ") == "FF СНГ"
    assert brand_safe("FF CIS") == "FF СНГ" and brand_safe("FF Indonesia") == "FF Инд"
    assert brand_safe("Free Fire [ID]") == "FF Инд"
    assert brand_safe("FREE FIRE - Global") == "FF Global"
    assert brand_safe("Free Fire Indonesia") == "FF Инд"
    assert brand_safe("PUBG Mobile") == "PUBG Mobile"
    assert is_ff("FF CIS") and not is_ff("BUFF") and not is_ff("Offer")


def test_catalog_has_no_ff_brand_or_images(conn, supplier):
    catalog.sync_catalog(conn, supplier)
    rows = conn.execute("SELECT category_name, name, image_url FROM products WHERE category_id = 'free_fire'").fetchall()
    assert rows and all(r["category_name"].startswith("FF") and r["image_url"] == FF_COVER for r in rows)
    assert not conn.execute("SELECT 1 FROM products WHERE category_name LIKE '%Free Fire%' "
                            "OR name LIKE '%Free Fire%'").fetchone()


def test_old_rows_renamed_on_start(conn):
    with db.tx(conn):
        conn.execute("INSERT INTO products (id, kind, category_id, category_name, name, base_price, unit, min_qty, "
                     "max_qty, stock, fields_json, supplier_ref_json, active, updated_at, image_url, region) "
                     "VALUES ('x1', 'topup', 'ff', 'Free Fire (CIS)', '100 Diamonds', '1', 'item', 1, 1, 0, '[]', "
                     "'{}', 1, ?, 'https://cdn.example/ff.png', 'CIS')", (db.now(),))
    urls = catalog.rename_brands(conn)
    r = conn.execute("SELECT category_name, image_url FROM products WHERE id = 'x1'").fetchone()
    assert r["category_name"] == "FF СНГ" and r["image_url"] == FF_COVER and urls == ["https://cdn.example/ff.png"]
    assert catalog.rename_brands(conn) == []   # второй запуск — уже ничего не меняет


def test_ff_cover_everywhere(client, conn, shop, supplier, monkeypatch):
    from donatix import cache, catalog_job, popular
    monkeypatch.setattr(catalog_job, "_base", "https://donatix.tj")
    catalog.sync_catalog(conn, supplier)
    with db.tx(conn):
        conn.execute("UPDATE products SET region = 'CIS' WHERE category_id = 'free_fire'")
    cache.clear()
    ff = [i for i in popular.compute(conn) if i["title"].startswith("FF")]
    assert ff and all(i["image_url"] == FF_COVER for i in ff)
    items = client.get("/api/v1/products?category_id=free_fire", headers=shop["h"]).json()["items"]
    assert items and all(i["image_url"] == "https://donatix.tj" + FF_COVER for i in items)
    assert client.get(FF_COVER).status_code == 200
