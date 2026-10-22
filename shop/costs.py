"""Нархи харид аз таъминкунандаҳо ва нархи API.

Нархи API = нархи харид × курси доллар × (1 + наценкаи админ / 100).
Нархи харид худкор нав мешавад (ҳангоми оғоз ва ҳар чанд соат), то API
бо нархи кӯҳна — шояд бо зарар — нафурӯшад.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from . import catalog
from .config import Config
from .db import Database, now

log = logging.getLogger(__name__)

RATE_KEY = "usd_rate"
DEFAULT_RATE = 11.0
API_MARKUP_KEY = "api_markup_percent"
DEFAULT_API_MARKUP = 10.0
UPDATED_KEY = "costs_updated_at"

REFRESH_EVERY = 3 * 3600      # сония
FIRST_DELAY = 20              # пас аз оғоз


def usd_rate(db: Database) -> float:
    """Курси доллар ба сомонӣ — аз панели админ."""
    try:
        rate = float(db.setting(RATE_KEY) or DEFAULT_RATE)
    except ValueError:
        return DEFAULT_RATE
    return rate if rate > 0 else DEFAULT_RATE


def api_markup(db: Database) -> float:
    """Наценкаи API бо фоиз — аз панели админ."""
    try:
        value = float(db.setting(API_MARKUP_KEY) or DEFAULT_API_MARKUP)
    except ValueError:
        return DEFAULT_API_MARKUP
    return value if 0 <= value <= 500 else DEFAULT_API_MARKUP


def api_price(cost_milli: int | None, rate: float, markup: float) -> int | None:
    """Нархи API дар дирам, ба боло то 1 дирам. Бе нархи харид — None (намефурӯшем)."""
    if not cost_milli or cost_milli <= 0:
        return None
    try:
        dirams = (
            Decimal(int(cost_milli)) * Decimal(str(rate)) * (Decimal(100) + Decimal(str(markup)))
            / Decimal(1000)
        )
    except InvalidOperation:
        return None
    value = int(dirams.to_integral_value(rounding=ROUND_CEILING))
    return value if value > 0 else None


def api_price_of(db: Database, row) -> int | None:
    cost = row["cost"] if "cost" in row.keys() else None
    return api_price(cost, usd_rate(db), api_markup(db))


async def refresh_costs(db: Database, cfg: Config, supplier) -> dict:
    """Нархи хариди ҳамаи молҳоро аз FireLoot ва Donatix мегирад."""
    report = {"fireloot_total": 0, "fireloot": None, "donatix": None, "donatix_missing": 0}
    if cfg.has_supplier:
        live = await supplier.products()
        if live:
            report["fireloot_total"] = len(live)
            report["fireloot"] = db.update_costs(
                {sku: item.get("price") for sku, item in live.items()}
            )
    telegram = getattr(supplier, "telegram", None)
    if telegram is not None:
        updated = missing = 0
        for category, kind in ((catalog.CAT_STARS, "stars"), (catalog.CAT_PREMIUM, "premium")):
            for row in db.products(category, only_active=False):
                if row["kind"] != kind:
                    continue
                cost = await telegram.cost_usd(kind, row["amount"])
                if cost is None:
                    missing += 1
                    continue
                db.set_cost(row["code"], round(cost * 1000))
                updated += 1
        report["donatix"], report["donatix_missing"] = updated, missing
    if report["fireloot"] is not None or report["donatix"] is not None:
        db.set_setting(UPDATED_KEY, now())
    return report


async def refresh_forever(db: Database, cfg: Config, supplier) -> None:
    """Нархи харидро дар паси парда нав мекунад — то бот хомӯш шавад."""
    await asyncio.sleep(FIRST_DELAY)
    while True:
        try:
            report = await refresh_costs(db, cfg, supplier)
            log.info("Нархи харид нав шуд: %s", report)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Нархи харид нав нашуд")
        await asyncio.sleep(REFRESH_EVERY)
