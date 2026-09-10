"""Фоновые задачи: авто-возврат зависших заказов, очередь повторов,
запросы отзывов.

В PHP это дёргалось по cron раз в 5 минут. Здесь то же самое делает
фоновая задача внутри процесса бота — отдельный cron не нужен.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal

from aiogram import Bot

import db
from handlers.common import log, money
from services import reviews
from texts import t

TICK_SEC = 300          # как cron раз в 5 минут
STUCK_AGE_SEC = 900     # заказ считается зависшим через 15 минут


async def refund_stuck(bot: Bot, min_age: int = STUCK_AGE_SEC,
                       notify: bool = True, limit: int = 500) -> dict:
    """Вернуть деньги за заказы, которые никто не выполнил.

    Каждый заказ бронируется атомарно, поэтому заказ, который админ
    в этот же момент обрабатывает руками, второй раз не вернётся.
    """
    done = 0
    total = Decimal("0.00")
    notified = 0
    cur = await db.currency()

    for order in await db.stuck_orders(min_age, limit):
        oid = int(order["id"])
        if not await db.claim_stuck_refund(oid):
            continue                      # уже обработан кем-то

        price = Decimal(order["price"] or 0)
        uid = int(order["uid"])
        try:
            new_bal = await db.credit(
                uid, price,
                f"Возврат (заказ не выполнен) · {order.get('pack_name') or ''}",
                kind="refund", ref_id=oid)
        except Exception as e:
            log.exception("возврат по зависшему заказу #%s не прошёл: %s", oid, e)
            continue

        done += 1
        total += price

        if notify:
            lang = (await db.get_user(uid) or {}).get("lang")
            try:
                await bot.send_message(
                    uid,
                    t(lang, "auto_refund",
                      oid=oid,
                      game=order.get("game_name") or "",
                      pack=order.get("pack_name") or "",
                      amount=money(price), cur=cur, balance=money(new_bal)))
                notified += 1
            except Exception as e:
                log.debug("о возврате #%s не сообщили: %s", oid, e)
            await asyncio.sleep(0.12)     # чтобы Telegram не ругался на флуд

    if done:
        log.info("авто-возврат: %s заказов на %s %s", done, money(total), cur)
    return {"done": done, "sum": total, "notified": notified}


async def run_queue(bot: Bot, placer=None, limit: int = 25) -> tuple[int, int]:
    """Повторить заказы, отложенные из-за нехватки товара у поставщика.

    placer — асинхронная функция oid -> (ok: bool, msg: str). Пока
    интеграция с поставщиком не подключена, очередь только считается.
    """
    rows = await db.queue_rows(limit)
    if not rows or placer is None:
        return 0, await db.queue_size()

    done = 0
    for row in rows:
        oid = int(row["order_id"])
        order = await db.order(oid)
        if not order:
            await db.queue_del(oid)
            continue
        if order.get("status") not in ("wait", "new"):
            await db.queue_del(oid)       # уже решён руками
            continue

        ok, msg = await placer(oid)
        if ok:
            await db.queue_del(oid)
            done += 1
            lang = (await db.get_user(int(order["uid"])) or {}).get("lang")
            try:
                await bot.send_message(
                    int(order["uid"]),
                    t(lang, "queue_done",
                      oid=oid,
                      game=order.get("game_name") or "",
                      pack=order.get("pack_name") or "",
                      pid=order.get("player_id") or ""))
            except Exception:
                pass
        else:
            await db.queue_bump(oid, msg)
            break                          # у поставщика пусто — ждём следующий тик
        await asyncio.sleep(0.25)

    return done, await db.queue_size()


async def tick(bot: Bot) -> None:
    """Один проход всех фоновых задач."""
    try:
        await refund_stuck(bot)
    except Exception as e:
        log.exception("авто-возврат упал: %s", e)
    try:
        await run_queue(bot)
    except Exception as e:
        log.exception("очередь упала: %s", e)
    try:
        sent = await reviews.ask_pending(bot)
        if sent:
            log.info("запрошено отзывов: %s", sent)
    except Exception as e:
        log.exception("запрос отзывов упал: %s", e)


async def loop(bot: Bot, every: int = TICK_SEC) -> None:
    """Фоновый цикл. Живёт столько же, сколько бот."""
    log.info("фоновые задачи запущены, интервал %s с", every)
    while True:
        try:
            await asyncio.sleep(every)
            await tick(bot)
        except asyncio.CancelledError:
            log.info("фоновые задачи остановлены")
            raise
        except Exception as e:
            log.exception("фоновый цикл: %s", e)
