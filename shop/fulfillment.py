"""Иҷрои худкори фармоиш тавассути таъминкунанда.

Мантиқ дар як ҷо ҷамъ аст, то ҳам харид аз меню ва ҳам тасдиқи админ
якхела кор кунанд:

1. Фармоишро ба таъминкунанда мефиристем.
2. Агар таъминкунанда АНИҚ рад кард — пулро фавран бармегардонем.
3. Агар ҷавоб наомад (таймаут, 5xx) — пулро НАМЕГАРДОНЕМ: фармоиш шояд
   қабул шуда бошад. Бо рақами худамон месанҷем, вагарна админ мебинад.
4. Агар қабул шуд — то ҳолати ниҳоӣ интизор мешавем.
5. ``completed`` → чек ба харидор; ``failed``/``refunded`` → пул бармегардад.
6. Молҳои дастӣ (Premium) ва ҷавобҳои дер → дар навбати админ мемонанд.
7. Пас аз азнавоғозкунӣ фармоишҳои нимкора то охир расонида мешаванд.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot

from . import catalog, keyboards, texts
from .config import Config
from .db import ORDER_DONE, ORDER_NEW, ORDER_OPEN, ORDER_REJECTED, ORDER_SENT, Database
from .supplier import OrderResult, Supplier

log = logging.getLogger(__name__)

FINAL = ("completed", "failed", "refunded")

# Вазифаҳои паси парда. Бе истинод Python онҳоро дар мобайни кор нест карда метавонад.
_TASKS: set[asyncio.Task] = set()

# Фармоишҳое, ки ҳоло иҷро мешаванд — то як фармоиш ду бор фиристода нашавад.
_BUSY: set[int] = set()

# Фармоиши кӯҳнатар аз ин пас аз азнавоғозкунӣ худкор фиристода намешавад:
# шояд админ онро аллакай дастӣ иҷро кардааст.
RESUME_MAX_AGE = timedelta(hours=6)

# Пауза пеш аз санҷиши фармоиш, агар таъминкунанда ҷавоб надод (сония).
UNCERTAIN_DELAY = 3.0


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


def _is_open(db: Database, order_id: int) -> bool:
    row = db.order(order_id)
    return row is not None and row["status"] in ORDER_OPEN


async def _refund(
    bot: Bot, cfg: Config, db: Database, order_id: int, reason: str | None
) -> None:
    """Фармоишро рад мекунад — базаи маълумот пулро бармегардонад.

    Агар фармоиш аллакай анҷом ёфта бошад (админ дастӣ иҷро ё рад кард),
    ҳеҷ чиз намекунем — вагарна харидор хабари бардурӯғ мегирифт.
    """
    if not _is_open(db, order_id):
        return
    row = db.set_order_status(order_id, ORDER_REJECTED, note=reason)
    if row is None or row["status"] != ORDER_REJECTED:
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


async def _complete(bot: Bot, cfg: Config, db: Database, order_id: int) -> None:
    before = db.order(order_id)
    if before is None:
        return
    if before["status"] not in ORDER_OPEN:
        if before["status"] == ORDER_REJECTED:
            # Админ пулро баргардонд, аммо таъминкунанда молро расонд.
            await _tell_admins(
                bot, cfg,
                f"⚠️ <b>Фармоиши #{order_id}</b> рад шуда буд ва пул баргашт, "
                f"аммо таъминкунанда онро <b>иҷро кард</b>.\n"
                f"📦 {texts.esc(before['title'])} → <code>{texts.esc(before['target'])}</code>\n"
                f"💰 {texts.money(before['price'], cfg.currency)} — ҳисоби харидорро санҷед.",
            )
        return
    db.set_order_status(order_id, ORDER_DONE)
    await _send_receipt(bot, cfg, db, order_id)
    await _tell_admins(
        bot, cfg,
        f"✅ <b>Фармоиши #{order_id} худкор иҷро шуд.</b>\n"
        f"📦 {texts.esc(before['title'])} → <code>{texts.esc(before['target'])}</code>\n"
        f"💰 {texts.money(before['price'], cfg.currency)}",
    )


async def _to_admin(
    bot: Bot, cfg: Config, db: Database, order_id: int, why: str, *, tell_user: bool = True
) -> None:
    """Фармоиш дар навбати админ мемонад; пул дар ҳолати интизорӣ."""
    row = db.order(order_id)
    if row is None or row["status"] not in ORDER_OPEN:
        return
    if tell_user:
        await _tell(bot, row["user_id"], texts.order_pending_admin(order_id))
    await _tell_admins(bot, cfg, why, keyboards.admin_order(order_id))


async def deliver_order(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, order_id: int
) -> None:
    """Фармоишро иҷро мекунад. Ҳеҷ гоҳ хато намепартояд."""
    if order_id in _BUSY:
        return
    _BUSY.add(order_id)
    try:
        await _deliver(bot, db, cfg, supplier, order_id)
    except asyncio.CancelledError:
        # Бот хомӯш мешавад — пас аз оғоз resume_open_orders идома медиҳад.
        raise
    except Exception:
        log.exception("Иҷрои фармоиши #%s канда шуд", order_id)
        await _to_admin(
            bot, cfg, db, order_id,
            f"⚠️ Фармоиши #{order_id} худкор иҷро нашуд — дастӣ санҷед.",
        )
    finally:
        _BUSY.discard(order_id)


async def _finish(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier,
    order_id: int, poll_id: str, *, by_external: bool,
) -> None:
    """То ҳолати ниҳоӣ интизор мешавад ва фармоишро мебандад."""
    final = await supplier.wait_until_done(poll_id, by_external=by_external)
    if not by_external and (not final.ok or final.status not in FINAL):
        # Бо рақами дохилии худамон боз як бор мепурсем.
        fallback = await supplier.order_status(str(order_id), by_external=True)
        if fallback.ok:
            final = fallback

    if final.status == "completed":
        await _complete(bot, cfg, db, order_id)
    elif final.status in ("failed", "refunded"):
        await _refund(bot, cfg, db, order_id, final.status)
    else:
        # Ҳанӯз дар коркард — пулро намебардорем, админ месанҷад.
        await _to_admin(
            bot, cfg, db, order_id,
            f"⏳ Фармоиши #{order_id} ҳанӯз дар коркард аст "
            f"(№ {texts.esc(poll_id)}). Дастӣ санҷед.",
        )


async def _lookup(supplier: Supplier, order_id: int) -> tuple[str, OrderResult]:
    """Оё таъминкунанда фармоиши моро медонад? → found | absent | unknown"""
    found = await supplier.order_status(str(order_id), by_external=True)
    if found.ok:
        return "found", found
    if found.code == "order_not_found" or (found.error or "").startswith("404"):
        return "absent", found
    return "unknown", found


async def _deliver(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, order_id: int
) -> None:
    row = db.order(order_id)
    if row is None or row["status"] not in ORDER_OPEN:
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
    # Дар база «123456789 (1234)» нигоҳ дошта мешавад — ҷудо мекунем.
    target_raw = row["target"] or ""
    target, _, server_part = target_raw.partition(" (")
    server = server_part.rstrip(")") if server_part else ""

    result = await supplier.place_order(
        kind=kind, sku=sku, target=target.strip(), amount=amount,
        order_id=str(order_id), server=server,
    )

    if not result.ok and result.uncertain:
        # Ҷавоб наомад — шояд фармоиш қабул шуда бошад. Пулро фавран
        # баргардонидан хатарнок аст: харидор ҳам мол ва ҳам пулро мегирифт.
        log.warning("Фармоиши #%s: ҷавоби номуайян (%s), месанҷем", order_id, result.error)
        await asyncio.sleep(UNCERTAIN_DELAY)
        state, found = await _lookup(supplier, order_id)
        if state == "found":
            db.set_order_status(order_id, ORDER_SENT)
            await _finish(bot, db, cfg, supplier, order_id, str(order_id), by_external=True)
            return
        if state == "absent" and result.code != "duplicate_order":
            await _refund(bot, cfg, db, order_id, result.error)
            return
        db.set_order_status(order_id, ORDER_SENT)
        await _to_admin(
            bot, cfg, db, order_id,
            f"⚠️ <b>Фармоиши #{order_id}</b>: таъминкунанда ҷавоб надод "
            f"(<code>{texts.esc(result.error or '—')}</code>).\n"
            "Шояд фармоиш қабул шуда бошад — дар кабинети FireLoot санҷед, "
            "баъд «иҷро» ё «рад»-ро пахш кунед.",
        )
        return

    if not result.ok:
        # Таъминкунанда аниқ рад кард — пулро фавран бармегардонем.
        log.warning("Фармоиши #%s қабул нашуд: %s", order_id, result.error)
        await _refund(bot, cfg, db, order_id, result.error)
        return

    if not result.external_id:
        # Ҷавоб омад, аммо рақами фармоиш нест — бо рақами худамон месанҷем.
        db.set_order_status(order_id, ORDER_SENT)
        await _finish(bot, db, cfg, supplier, order_id, str(order_id), by_external=True)
        return

    db.set_order_status(order_id, ORDER_SENT, external_id=result.external_id)
    await _finish(bot, db, cfg, supplier, order_id, result.external_id, by_external=False)


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


def deliver_in_background(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, order_id: int
) -> asyncio.Task:
    """Иҷроро дар паси парда оғоз мекунад, то бот ҷавобгӯ монад."""
    return _spawn(deliver_order(bot, db, cfg, supplier, order_id))


# ── пас аз азнавоғозкунӣ ──────────────────────────────────────────────
def _age(row) -> timedelta:
    try:
        stamp = datetime.fromisoformat(row["updated_at"])
    except (TypeError, ValueError):
        return RESUME_MAX_AGE * 2
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - stamp


async def _resume_one(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier, row
) -> str:
    order_id = row["id"]
    if order_id in _BUSY:
        return "busy"
    _BUSY.add(order_id)
    try:
        if row["status"] == ORDER_SENT and row["external_id"]:
            await _finish(bot, db, cfg, supplier, order_id, row["external_id"], by_external=False)
            return "resumed"
        state, _ = await _lookup(supplier, order_id)
        if state == "found":
            db.set_order_status(order_id, ORDER_SENT)
            await _finish(bot, db, cfg, supplier, order_id, str(order_id), by_external=True)
            return "resumed"
        if state == "absent" and row["status"] == ORDER_NEW:
            # Ба таъминкунанда нарасида буд — ҳоло мефиристем.
            _BUSY.discard(order_id)
            await deliver_order(bot, db, cfg, supplier, order_id)
            return "resent"
        await _to_admin(
            bot, cfg, db, order_id,
            f"⚠️ Фармоиши #{order_id} ҳангоми азнавоғозкунии бот нимкора монд. "
            "Дар FireLoot санҷед ва «иҷро» ё «рад»-ро пахш кунед.",
            tell_user=False,
        )
        return "admin"
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Идомаи фармоиши #%s нашуд", order_id)
        return "error"
    finally:
        _BUSY.discard(order_id)


async def resume_open_orders(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier
) -> dict[str, int]:
    """Фармоишҳои худкорро, ки бот ҳангоми хомӯшшавӣ нимкора монд, идома медиҳад.

    Ҳар навсозии `bot` ботро аз нав оғоз мекунад. Бе ин фармоише, ки дар ҳамон
    лаҳза иҷро мешуд, то абад «дар коркард» мемонд, пул аз харидор гирифта.
    """
    counts: dict[str, int] = {}
    if not cfg.has_supplier:
        return counts
    for row in db.open_orders(200):
        if (row["kind"] or "game") == "manual" or not row["sku"]:
            continue          # фармоишҳои дастӣ — кори админ
        if _age(row) > RESUME_MAX_AGE:
            counts["old"] = counts.get("old", 0) + 1
            continue
        outcome = await _resume_one(bot, db, cfg, supplier, row)
        counts[outcome] = counts.get(outcome, 0) + 1
    if counts:
        log.info("Фармоишҳои нимкора пас аз оғоз: %s", counts)
    return counts


def resume_in_background(
    bot: Bot, db: Database, cfg: Config, supplier: Supplier
) -> asyncio.Task:
    return _spawn(resume_open_orders(bot, db, cfg, supplier))


async def shutdown() -> None:
    """Вазифаҳои паси пардаро пеш аз бастани база ва шабака қатъ мекунад.

    Фармоиш дар ҳолати худ мемонад; пас аз оғоз resume_open_orders онро идома медиҳад.
    """
    tasks = [t for t in _TASKS if not t.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
