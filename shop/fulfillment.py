"""Иҷрои худкори фармоиш тавассути таъминкунанда.

Мантиқ дар як ҷо ҷамъ аст, то ҳам харид аз меню ва ҳам тасдиқи админ
якхела кор кунанд:

1. Фармоишро ба таъминкунанда мефиристем.
2. Агар қабул нашуд — пулро ФАВРАН ба харидор бармегардонем.
3. Агар қабул шуд — то ҳолати ниҳоӣ интизор мешавем.
4. ``completed`` → чек ба харидор; ``failed``/``refunded`` → пул баргардонида мешавад.
5. Молҳои дастӣ (Premium) ва ҷавобҳои дер → дар навбати админ мемонанд.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from . import catalog, keyboards, texts
from .config import Config
from .db import Database, ORDER_DONE, ORDER_REJECTED, ORDER_SENT
from .supplier import Supplier

log = logging.getLogger(__name__)


async def _tell(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except Exception as exc:
        log.info("Паём ба %s нарасид: %s", chat_id, exc)


async def _tell_admins(bot: Bot, cfg: Config, text: str, markup=None) -> None:
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as exc:
            log.warning("Ба админ %s нарасид: %s", admin_id, exc)


async def _send_receipt(bot: Bot, cfg: Config, db: Database, order_id: int) -> None:
    row = db.order(order_id)
    if row is None:
        return
    info = catalog.CATEGORY_INFO.get(row["category"])
    receipt = texts.receipt(
        order_id=order_id,
        title=row["title"],
        target=row["target"] or "",
        nickname=row["nickname"],
        price=row["price"],
        external_id=row["external_id"],
        is_player=bool(info and info.target == "player"),
        currency=cfg.currency,
    )
    # Ҳар харидорро ба навиштани шарҳ даъват мекунем.
    try:
        await bot.send_message(
            row["user_id"],
            receipt + texts.REVIEW_INVITE,
            reply_markup=keyboards.review_invite(),
        )
    except Exception as exc:
        log.info("Чек ба %s нарасид: %s", row["user_id"], exc)


async def _refund(
    bot: Bot, cfg: Config, db: Database, order_id: int, reason: str | None
) -> None:
    """Фармоишро рад мекунад — базаи маълумот пулро бармегардонад."""
    row = db.set_order_status(order_id, ORDER_REJECTED, note=reason)
    if row is None:
        return
    await _tell(
        bot,
        row["user_id"],
        texts.auto_refunded(order_id, row["price"], reason, cfg.currency),
    )
    await _tell_admins(
        bot,
        cfg,
        f"↩️ <b>Фармоиши #{order_id} худкор баргардонида шуд.</b>\n"
        f"📦 {texts.esc(row['title'])} → <code>{texts.esc(row['target'])}</code>\n"
        f"💳 {texts.money(row['price'], cfg.currency)} ба харидор баргашт\n"
        f"📌 Сабаб: <code>{texts.esc(reason or '—')}</code>",
    )


async def deliver_order(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, order_id: int
) -> None:
    """Фармоишро иҷро мекунад. Ҳеҷ гоҳ хато намепартояд."""
    try:
        await _deliver(bot, db, cfg, supplier, order_id)
    except Exception:
        log.exception("Иҷрои фармоиши #%s канда шуд", order_id)
        row = db.order(order_id)
        if row is not None and row["status"] in ("new", ORDER_SENT):
            await _tell(bot, row["user_id"], texts.order_pending_admin(order_id))
            await _tell_admins(
                bot,
                cfg,
                f"⚠️ Фармоиши #{order_id} худкор иҷро нашуд — дастӣ санҷед.",
                keyboards.admin_order(order_id),
            )


async def _deliver(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, order_id: int
) -> None:
    row = db.order(order_id)
    if row is None:
        return

    kind = row["kind"] or "game"
    sku = row["sku"] or ""
    product = db.product(row["product_code"])
    amount = product["amount"] if product else 0

    # ── моли дастӣ ё таъминкунанда хомӯш ──────────────────────────────
    if kind == "manual" or not sku or not cfg.has_supplier:
        await _tell(bot, row["user_id"], texts.order_pending_admin(order_id))
        await _tell_admins(
            bot,
            cfg,
            texts.admin_new_order(row, db.user(row["user_id"]), cfg.currency)
            + "\n\n✋ <b>Дастӣ иҷро кунед.</b>",
            keyboards.admin_order(order_id),
        )
        return

    # ── ба таъминкунанда мефиристем ───────────────────────────────────
    result = await supplier.place_order(
        kind=kind, sku=sku, target=row["target"] or "", amount=amount,
        order_id=str(order_id),
    )

    if not result.ok:
        # Фармоиш қабул нашуд — пулро фавран бармегардонем.
        log.warning("Фармоиши #%s қабул нашуд: %s", order_id, result.error)
        await _refund(bot, cfg, db, order_id, result.error)
        return

    if not result.external_id:
        # Ҷавоб омад, аммо рақами фармоиш нест — админ санҷад.
        db.set_order_status(order_id, ORDER_SENT)
        await _tell(bot, row["user_id"], texts.order_pending_admin(order_id))
        await _tell_admins(
            bot, cfg,
            f"⚠️ Фармоиши #{order_id} фиристода шуд, аммо рақами таъминкунанда наомад.",
            keyboards.admin_order(order_id),
        )
        return

    db.set_order_status(order_id, ORDER_SENT, external_id=result.external_id)

    # ── интизори ҳолати ниҳоӣ ─────────────────────────────────────────
    final = await supplier.wait_until_done(result.external_id)
    if not final.ok or final.status not in ("completed", "failed", "refunded"):
        # Бо рақами дохилии худамон боз як бор мепурсем.
        fallback = await supplier.order_status(str(order_id), by_external=True)
        if fallback.ok:
            final = fallback

    if final.status == "completed":
        db.set_order_status(order_id, ORDER_DONE)
        await _send_receipt(bot, cfg, db, order_id)
        await _tell_admins(
            bot, cfg,
            f"✅ <b>Фармоиши #{order_id} худкор иҷро шуд.</b>\n"
            f"📦 {texts.esc(row['title'])} → <code>{texts.esc(row['target'])}</code>\n"
            f"💰 {texts.money(row['price'], cfg.currency)}",
        )
    elif final.status in ("failed", "refunded"):
        await _refund(bot, cfg, db, order_id, final.status)
    else:
        # Ҳанӯз дар коркард — пулро намебардорем, админ месанҷад.
        await _tell(bot, row["user_id"], texts.order_pending_admin(order_id))
        await _tell_admins(
            bot, cfg,
            f"⏳ Фармоиши #{order_id} ҳанӯз дар коркард аст "
            f"(№ {texts.esc(result.external_id)}). Дастӣ санҷед.",
            keyboards.admin_order(order_id),
        )


def deliver_in_background(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, order_id: int
) -> asyncio.Task:
    """Иҷроро дар паси парда оғоз мекунад, то бот ҷавобгӯ монад."""
    return asyncio.create_task(deliver_order(bot, db, cfg, supplier, order_id))
