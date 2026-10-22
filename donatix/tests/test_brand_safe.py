"""Жалоба правообладателя: игру показываем как «FF <регион>», без их картинок."""
from donatix import catalog, db
from donatix.suppliers.base import brand_safe, is_ff


def test_names():
    assert brand_safe("Free Fire (CIS)") == "FF CIS"
    assert brand_safe("Free Fire — СНГ") == "FF CIS"
    assert brand_safe("FREE FIRE - Global") == "FF Global"
    assert brand_safe("Free Fire Indonesia") == "FF Indonesia"
    assert brand_safe("PUBG Mobile") == "PUBG Mobile"
    assert is_ff("FF CIS") and not is_ff("BUFF") and not is_ff("Offer")


def test_catalog_has_no_ff_brand_or_images(conn, supplier):
    catalog.sync_catalog(conn, supplier)
    rows = conn.execute("SELECT category_name, name, image_url FROM products WHERE category_id = 'free_fire'").fetchall()
    assert rows and all(r["category_name"].startswith("FF") and r["image_url"] is None for r in rows)
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
    assert r["category_name"] == "FF CIS" and r["image_url"] is None and urls == ["https://cdn.example/ff.png"]
