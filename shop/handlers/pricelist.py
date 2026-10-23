"""«💰 Нархҳо»: нархҳои API ва яклухт барои соҳибони калид ва шарикони конструктор."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import catalog, costs, keyboards, pricelist
from ..config import Config
from ..db import Database
from ..i18n import texts
from .common import current_user, safe_edit, send_long

router = Router(name="pricelist")


def _viewer(cb: CallbackQuery, db: Database, cfg: Config) -> pricelist.Viewer:
    if cfg.is_tenant:                 # нархҳои платформа танҳо дар боти асосӣ
        return pricelist.Viewer()
    return pricelist.viewer_of(db, cb.from_user.id, is_admin=cfg.is_admin(cb.from_user.id))


@router.callback_query(F.data == keyboards.CB_PRICES)
async def cb_prices(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    viewer = _viewer(cb, db, cfg)
    if not viewer.any:
        await cb.answer("Нархҳо барои соҳибони калиди API ва шарикони конструктор.",
                        show_alert=True)
        return
    user = current_user(cb, db)
    cats = pricelist.categories(db, viewer)
    await safe_edit(
        cb,
        texts.prices_home(cats, user.balance, viewer.api, viewer.wholesale,
                          db.setting(costs.UPDATED_KEY), cfg.currency),
        keyboards.prices_categories(cats),
    )
    await cb.answer()


@router.callback_query(F.data.startswith(keyboards.CB_PRICES_CAT))
async def cb_prices_category(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    category = cb.data[len(keyboards.CB_PRICES_CAT):]
    viewer = _viewer(cb, db, cfg)
    if not viewer.any or category not in catalog.CATEGORY_INFO:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    rows = pricelist.items(db, category, viewer)
    lines = texts.price_lines(category, rows, viewer.api, viewer.wholesale, cfg.currency)
    await send_long(cb, pricelist.chunks(lines), keyboards.prices_back())
    await cb.answer()
