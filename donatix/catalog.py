"""Каталог: храним копию каталога поставщика у себя и обновляем по расписанию
(FazerCards просит не дёргать каталог перед каждым заказом)."""

from __future__ import annotations

import json
import logging
import sqlite3
from decimal import Decimal
from typing import Any

from . import db
from .money import apply_markup, fmt_unit, to_decimal
from .suppliers import KIND_TITLES, Supplier, SupplierError

log = logging.getLogger(__name__)


def sync_catalog(conn: sqlite3.Connection, supplier: Supplier) -> dict[str, int]:
    """Забрать каталог у поставщика. Пропавшие товары выключаются, а не удаляются:
    на них ссылаются старые заказы."""
    started = db.now()
    seen: set[str] = set()
    for p in supplier.fetch_catalog():
        seen.add(p.id)
        conn.execute(
            """
            INSERT INTO products (id, kind, category_id, category_name, name, base_price, unit,
                                  min_qty, max_qty, stock, fields_json, supplier_ref_json, active, updated_at,
                                  image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind, category_id = excluded.category_id,
                category_name = excluded.category_name, name = excluded.name,
                base_price = excluded.base_price, unit = excluded.unit,
                min_qty = excluded.min_qty, max_qty = excluded.max_qty, stock = excluded.stock,
                fields_json = excluded.fields_json, supplier_ref_json = excluded.supplier_ref_json,
                active = 1, updated_at = excluded.updated_at,
                image_url = COALESCE(excluded.image_url, products.image_url)
            """,
            (p.id, p.kind, p.category_id, p.category_name, p.name, str(p.base_price), p.unit,
             p.min_qty, max(p.max_qty, p.min_qty), p.stock, json.dumps(p.fields, ensure_ascii=False),
             json.dumps(p.supplier_ref, ensure_ascii=False), started, p.image_url),
        )
    disabled = 0
    if seen:
        placeholders = ",".join("?" * len(seen))
        disabled = conn.execute(
            f"UPDATE products SET active = 0 WHERE active = 1 AND id NOT IN ({placeholders})",
            tuple(seen),
        ).rowcount
    if "steam-gift" in seen:
        from . import steam_gifts
        try:
            n = steam_gifts.sync_games(conn, supplier)
            log.info("steam-гифты: %s игр", n)
        except SupplierError as exc:
            log.warning("steam-гифты: каталог игр не обновлён: %s", exc)
        steam_gifts.clear_cache()
    db.set_setting(conn, "catalog_synced_at", db.now())
    log.info("каталог: %s товаров, выключено %s", len(seen), disabled)
    return {"products": len(seen), "disabled": disabled}


def load_product(row: sqlite3.Row) -> dict[str, Any]:
    product = dict(row)
    product["fields"] = json.loads(row["fields_json"] or "[]")
    product["supplier_ref"] = json.loads(row["supplier_ref_json"] or "{}")
    return product


def get_product(conn: sqlite3.Connection, product_id: str, *, for_sale: bool = True) -> dict[str, Any] | None:
    sql = "SELECT * FROM products WHERE id = ?"
    if for_sale:
        sql += " AND active = 1 AND hidden = 0"
    row = conn.execute(sql, (product_id,)).fetchone()
    return load_product(row) if row else None


def list_products(
    conn: sqlite3.Connection, *, kind: str = "", q: str = "", category_id: str = "", include_hidden: bool = False,
    limit: int = 500, offset: int = 0,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM products WHERE active = 1"
    args: list[Any] = []
    if not include_hidden:
        sql += " AND hidden = 0"
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    if category_id:
        sql += " AND category_id = ?"
        args.append(category_id)
    if q:
        sql += " AND (name LIKE ? OR category_name LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY kind, category_name, CAST(base_price AS REAL), name LIMIT ? OFFSET ?"
    args += [limit, offset]
    return [load_product(r) for r in conn.execute(sql, args)]


def categories(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT kind, category_id, category_name, COUNT(*) AS n, MIN(CAST(base_price AS REAL)) AS from_price, "
        "MAX(image_url) AS image_url "
        "FROM products WHERE active = 1 AND hidden = 0 GROUP BY kind, category_id, category_name "
        "ORDER BY kind, category_name"
    ).fetchall()


def public_view(product: dict[str, Any], markup: Decimal) -> dict[str, Any]:
    """Товар, как его видит клиент: наша цена, без закупочной и без данных поставщика."""
    price = apply_markup(to_decimal(product["base_price"]), markup)
    return {
        "product_id": product["id"],
        "kind": product["kind"],
        "kind_title": KIND_TITLES.get(product["kind"], product["kind"]),
        "category_id": product["category_id"],
        "category_name": product["category_name"],
        "name": product["name"],
        "unit": product["unit"],
        "price_usd": fmt_unit(price),
        "min_quantity": product["min_qty"],
        "max_quantity": product["max_qty"],
        "stock": product["stock"],
        "fields": product["fields"],
        "image_url": product.get("image_url"),
        **(_steam_extra(product, price) if product["kind"] == "steam_topup" else {}),
    }


def _steam_extra(product: dict[str, Any], price: Decimal) -> dict[str, Any]:
    ref = product["supplier_ref"]
    return {
        "rates": ref.get("rates", {}),
        "min_usd": ref.get("min_usd"),
        "max_usd": ref.get("max_usd"),
        # Сколько клиент платит за 1 USD, зачисленный на Steam.
        "discount_percent": fmt_unit((Decimal(1) - price) * 100) if price < 1 else "0.0000",
    }
