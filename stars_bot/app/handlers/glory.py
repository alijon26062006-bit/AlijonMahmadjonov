"""«Боты для гильдии» (Glory клана Free Fire) через Donatix.

Регион → ID клана → «Оғоз» → деньги с баланса, запуск у Donatix.
Не запустилось — деньги назад сразу. Ответа нет — заказ придержан,
владелец решает (/done или /refund). Запустилось — карточка со статусом,
очками клана и кнопкой «Қатъ кардан».
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import db, effects, keyboards, texts
from app.keyboards import DANGER, PRIMARY, SUCCESS, btn, labeled
from app.money import fmt
from app.services import access, delivery
from app.services import donatix as dx
from app.states import Glory

log = logging.getLogger(__name__)
router = Router(name="glory")

STATUS_TJ = {"starting": "⏳ Оғоз мешавад", "running": "🟢 Кор мекунад",
             "stopped": "⏹ Қатъ шуд", "failed": "❌ Оғоз нашуд"}
#: Чаще не спрашиваем Donatix про один и тот же запуск.
REFRESH_EVERY = 10


def regions_kb(items: list[dict]) -> object:
    kb = InlineKeyboardBuilder()
    for r in items:
        kb.row(btn(f"{'💎 ' if r['premium'] else ''}{r['name']} — {fmt(r['price'])}",
                   f"gl:r:{r['id']}", style=PRIMARY))
    kb.row(btn("📋 Ботҳои ман", "gl:my"))
    kb.row(btn(labeled("back", "Бозгашт"), "m:games"))
    return kb.as_markup()


def card_kb(order_id: int, running: bool) -> object:
    kb = InlineKeyboardBuilder()
    kb.row(btn("🔄 Навсозӣ", f"gl:v:{order_id}", style=PRIMARY))
    if running:
        kb.row(btn("⏹ Қатъ кардан", f"gl:s:{order_id}", style=DANGER))
    kb.row(btn("📋 Ботҳои ман", "gl:my"))
    kb.row(btn(labeled("back", "Ба меню"), "m:main"))
    return kb.as_markup()


def card_text(run) -> str:
    clan_line = f"├ Клан: <b>{run['clan']}</b>\n" if run["clan"] else ""
    extra = ""
    if run["bots"]:
        extra += f"├ Ботҳо: <b>{run['bots']}</b>\n"
    if run["uptime"]:
        extra += f"├ Вақти кор: {run['uptime']}\n"
    return texts.GLORY_CARD.format(
        clan=run["clan_id"], status=STATUS_TJ.get(run["status"], run["status"]),
        region=run["region_title"] or run["region"], clan_line=clan_line,
        glory=run["glory"], farmed=run["farmed"], extra=extra,
        order_id=run["order_id"],
    )


async def apply(conn: aiosqlite.Connection, order_id: int, remote: dict) -> None:
    """Записать свежие данные Donatix о запуске."""
    clan = remote.get("clan") if isinstance(remote.get("clan"), dict) else {}

    def num(value) -> int:
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return 0

    fields = {"status": str(remote.get("status") or "")[:20] or None,
              "glory": num(remote.get("glory")), "farmed": num(remote.get("farmed")),
              "clan": str(clan.get("name") or "")[:60],
              "uptime": str(remote.get("uptime") or "")[:20],
              "bots": num(remote.get("bots"))}
    if remote.get("id"):
        fields["ext_id"] = str(remote["id"])[:30]
    await db.update_glory_run(conn, order_id, **{k: v for k, v in fields.items()
                                                 if v not in (None, "")})


@router.callback_query(F.data == "gl:menu")
async def cb_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not dx.ready():
        await call.answer("Бахш муваққатан баста аст.", show_alert=True)
        return
    try:
        items = await dx.regions()
    except (dx.GloryError, dx.GloryUnknown) as exc:
        log.warning("Glory: регионы не получены — %s", exc)
        await call.answer("Хидмат ҳоло дастрас нест, пас аз як дақиқа кӯшиш кунед.",
                          show_alert=True)
        return
    if not items:
        await call.answer("Ҳоло минтақаҳои дастрас нестанд.", show_alert=True)
        return
    from app import screens

    await screens.show(call, texts.GLORY_ENTRY, regions_kb(items), keys=("glory", "games"))
    await call.answer()


@router.callback_query(F.data.startswith("gl:r:"))
async def cb_region(call: CallbackQuery, state: FSMContext) -> None:
    region_id = call.data.split(":", 2)[2]
    try:
        items = await dx.regions()
    except (dx.GloryError, dx.GloryUnknown):
        items = []
    region = next((r for r in items if r["id"] == region_id), None)
    if region is None:
        await call.answer("Ин минтақа дигар дастрас нест.", show_alert=True)
        return
    await state.set_state(Glory.clan)
    await state.update_data(region=region["id"], region_title=region["name"],
                            price=region["price"], cost=region["cost"])
    await call.message.edit_text(
        texts.GLORY_ASK_CLAN.format(region=region["name"], price=fmt(region["price"])),
        reply_markup=keyboards.back("gl:menu", "‹ Минтақаҳо"),
    )
    await call.answer()


@router.message(Glory.clan, F.text)
async def on_clan(message: Message, state: FSMContext, conn: aiosqlite.Connection) -> None:
    clan = dx.clean_clan(message.text or "")
    if clan is None:
        await message.answer(texts.GLORY_BAD_CLAN)
        return
    if await db.glory_clan_busy(conn, clan):
        await message.answer(texts.GLORY_BUSY)
        return
    data = await state.get_data()
    user = await db.get_user(conn, message.from_user.id)
    balance = user.balance if user else 0
    await state.update_data(clan=clan)
    await state.set_state(Glory.confirm)
    kb = InlineKeyboardBuilder()
    kb.row(btn(labeled("confirm", "Оғоз кардан"), "gl:go", style=SUCCESS))
    kb.row(btn(labeled("edit", "ID-и дигар"), f"gl:r:{data['region']}"))
    kb.row(btn(labeled("cancel", "Бекор"), "m:main", style=DANGER))
    await message.answer(
        texts.GLORY_CONFIRM.format(region=data["region_title"], clan=clan,
                                   price=fmt(data["price"]),
                                   rest=fmt(max(balance - data["price"], 0))),
        reply_markup=kb.as_markup(),
    )


@router.callback_query(Glory.confirm, F.data == "gl:go")
async def cb_go(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection,
                bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    price, clan = int(data["price"]), data["clan"]
    if await db.glory_clan_busy(conn, clan):
        await call.message.edit_text(texts.GLORY_BUSY, reply_markup=keyboards.back())
        await call.answer()
        return
    if not await db.charge(conn, call.from_user.id, price):
        user = await db.get_user(conn, call.from_user.id)
        balance = user.balance if user else 0
        await call.message.edit_text(
            texts.STARS_NOT_ENOUGH.format(need=fmt(price), balance=fmt(balance),
                                          missing=fmt(price - balance)),
            reply_markup=keyboards.deposit_methods(),
        )
        await call.answer()
        return
    try:
        order = await db.create_order(
            conn, user_id=call.from_user.id, product_type="glory", quantity=1,
            recipient=clan, price=price, cost=int(data.get("cost") or 0),
        )
    except Exception:
        await db.credit(conn, call.from_user.id, price)
        raise
    await db.save_glory_run(conn, order_id=order.id, user_id=call.from_user.id,
                            region=data["region"], region_title=data["region_title"],
                            clan_id=clan, status="starting")
    await call.message.edit_text(texts.GLORY_STARTING.format(clan=clan))
    await call.answer()

    try:
        remote = await dx.launch(data["region"], clan)
    except dx.GloryError as exc:
        await _refuse(bot, conn, order, str(exc))
        await call.message.edit_text(
            texts.GLORY_FAILED.format(order_id=order.id, price=fmt(price),
                                      reason=_reason(exc)),
            reply_markup=keyboards.back(),
        )
        return
    except dx.GloryUnknown as exc:
        await _hold(bot, conn, order, str(exc))
        await call.message.edit_text(texts.GLORY_CHECKING.format(order_id=order.id),
                                     reply_markup=keyboards.back())
        return

    await db.transition_order(conn, order.id, expected=db.ORDER_DELIVERING,
                              new=db.ORDER_DELIVERED,
                              fragment_order_id=str(remote.get("id") or "")[:60])
    await apply(conn, order.id, remote)
    run = await db.get_glory_run(conn, order.id)
    await call.message.edit_text(card_text(run),
                                 reply_markup=card_kb(order.id, run["status"] in dx.OPEN))
    await delivery.notify(bot, call.from_user.id, "🏆 Ботҳо оғоз шуданд!",
                          **effects.kw("done"))
    await delivery.notify_admins(
        bot,
        "🏆 <b>Боты для гильдии запущены</b>\n"
        f"├ Заказ: <code>{order.id}</code> · Donatix <code>{remote.get('id')}</code>\n"
        f"├ Клан: <code>{clan}</code> · {data['region_title']}\n"
        f"├ Клиент: <code>{call.from_user.id}</code>\n"
        f"└ Цена: <b>{fmt(price)}</b>",
    )


def _reason(exc: dx.GloryError) -> str:
    code = getattr(exc, "code", "")
    if code == "clan_busy":
        return "Барои ин клан ботҳо аллакай кор мекунанд."
    if code == "invalid_clan_id":
        return "ID-и клан нодуруст аст — онро аз нав санҷед."
    return "Хидмат ҳоло оғоз карда натавонист. Баъдтар боз кӯшиш кунед."


async def _refuse(bot, conn, order: db.Order, reason: str) -> None:
    """Donatix отказал: денег он не взял — возвращаем клиенту."""
    if await db.transition_order(conn, order.id, expected=db.ORDER_DELIVERING,
                                 new=db.ORDER_REFUNDED, error=reason[:1000]):
        await db.credit(conn, order.user_id, order.price)
    await db.update_glory_run(conn, order.id, status="failed")
    if "insufficient" in reason.lower() or "не хватает" in reason.lower():
        await delivery.notify_admins(
            bot, "⚠️ <b>Donatix: на балансе не хватает денег</b>\n\n"
                 "Боты для гильдии не запускаются — пополните счёт Donatix. "
                 f"Клиенту по заказу <code>{order.id}</code> деньги вернули.")
    log.warning("Glory: заказ %s не запущен — %s", order.id, reason)


async def _hold(bot, conn, order: db.Order, reason: str) -> None:
    """Ответа нет — запустилось ли, неизвестно. Деньги держим, решает владелец."""
    await db.transition_order(conn, order.id, expected=db.ORDER_DELIVERING,
                              new=db.ORDER_FAILED, error=reason[:1000])
    await delivery.notify_admins(
        bot,
        "⚠️ <b>Боты для гильдии: Donatix не ответил</b>\n"
        f"├ Заказ: <code>{order.id}</code>\n"
        f"├ Клан: <code>{order.recipient}</code>\n"
        f"└ Списано: <b>{fmt(order.price)}</b>\n\n"
        f"<blockquote expandable>{reason[:400]}</blockquote>\n\n"
        "<blockquote>Проверьте в кабинете Donatix (Glory): запустилось → "
        f"<code>/done {order.id}</code>, нет → <code>/refund {order.id}</code>."
        "</blockquote>",
    )


async def _own(call: CallbackQuery, conn, order_id: int):
    run = await db.get_glory_run(conn, order_id)
    if run is None or (run["user_id"] != call.from_user.id
                       and not access.is_admin(call.from_user.id)):
        await call.answer("Фармоиш ёфт нашуд.", show_alert=True)
        return None
    return run


def _stale(run) -> bool:
    try:
        when = datetime.fromisoformat(run["updated_at"])
    except (TypeError, ValueError):
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds() >= REFRESH_EVERY


@router.callback_query(F.data.startswith("gl:v:"))
async def cb_view(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    run = await _own(call, conn, order_id)
    if run is None:
        return
    if run["ext_id"] and run["status"] in dx.OPEN and _stale(run):
        try:
            await apply(conn, order_id, await dx.status(run["ext_id"]))
        except (dx.GloryError, dx.GloryUnknown) as exc:
            log.info("Glory: статус %s не получен — %s", run["ext_id"], exc)
        run = await db.get_glory_run(conn, order_id)
    try:
        await call.message.edit_text(card_text(run),
                                     reply_markup=card_kb(order_id, run["status"] == "running"))
    except Exception:  # noqa: BLE001 — «не изменилось» не ошибка
        pass
    await call.answer()


@router.callback_query(F.data.startswith("gl:s:"))
async def cb_stop_ask(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    if await _own(call, conn, order_id) is None:
        return
    kb = InlineKeyboardBuilder()
    kb.row(btn("⏹ Ҳа, қатъ кунед", f"gl:sy:{order_id}", style=DANGER))
    kb.row(btn(labeled("back", "Не, бозгашт"), f"gl:v:{order_id}"))
    await call.message.edit_text(texts.GLORY_STOP_ASK, reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("gl:sy:"))
async def cb_stop(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    order_id = int(call.data.rsplit(":", 1)[1])
    run = await _own(call, conn, order_id)
    if run is None:
        return
    if run["status"] != "running" or not run["ext_id"]:
        await call.answer("Гурӯҳ аллакай кор намекунад.", show_alert=True)
    else:
        try:
            await apply(conn, order_id, await dx.stop(run["ext_id"]))
            await db.update_glory_run(conn, order_id, status="stopped")
            await call.answer("Қатъ шуд")
        except (dx.GloryError, dx.GloryUnknown) as exc:
            log.warning("Glory: остановка %s не прошла — %s", run["ext_id"], exc)
            await call.answer("Қатъ кардан нашуд, баъдтар боз кӯшиш кунед.", show_alert=True)
    run = await db.get_glory_run(conn, order_id)
    await call.message.edit_text(card_text(run),
                                 reply_markup=card_kb(order_id, run["status"] == "running"))


@router.callback_query(F.data == "gl:my")
async def cb_my(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    runs = await db.glory_runs_of(conn, call.from_user.id)
    kb = InlineKeyboardBuilder()
    for run in runs:
        kb.row(btn(f"{STATUS_TJ.get(run['status'], run['status'])} · клан {run['clan_id']}",
                   f"gl:v:{run['order_id']}"))
    kb.row(btn("🏆 Оғози нав", "gl:menu", style=PRIMARY))
    kb.row(btn(labeled("back", "Ба меню"), "m:main"))
    text = ("🏆 <b>Ботҳои ман</b>" if runs else texts.GLORY_MY_EMPTY)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


async def watch_loop(bot: Bot) -> None:
    """Раз в две минуты — работающие группы: закончили — сказать клиенту."""
    import asyncio

    while True:
        try:
            await asyncio.sleep(120)
            if not dx.key():
                continue
            conn = await db.connect()
            try:
                for run in await db.open_glory_runs(conn):
                    await check_run(bot, conn, run)
            finally:
                await conn.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.exception("Glory: присмотр упал: %s", exc)


async def check_run(bot, conn, run) -> None:
    try:
        remote = await dx.status(run["ext_id"])
    except (dx.GloryError, dx.GloryUnknown) as exc:
        log.info("Glory: статус %s не получен — %s", run["ext_id"], exc)
        return
    await apply(conn, run["order_id"], remote)
    fresh = await db.get_glory_run(conn, run["order_id"])
    if remote.get("refunded"):
        # Donatix вернул деньги нам — значит, запуск не состоялся. Клиенту
        # возвращает владелец: сам бот уже засчитал заказ выполненным.
        await delivery.notify_admins(
            bot, "⚠️ <b>Donatix вернул деньги за запуск Glory</b>\n"
                 f"├ Заказ: <code>{run['order_id']}</code>, клан <code>{run['clan_id']}</code>\n"
                 f"└ Клиент: <code>{run['user_id']}</code>\n\n"
                 "Верните клиенту: панель → 👥 Клиенты → ➕ Начислить.")
    if fresh["status"] not in dx.OPEN:
        await delivery.notify(
            bot, fresh["user_id"],
            texts.GLORY_FINISHED.format(clan=fresh["clan_id"], farmed=fresh["farmed"],
                                        glory=fresh["glory"]),
            reply_markup=keyboards.back(), **effects.kw("done"),
        )
