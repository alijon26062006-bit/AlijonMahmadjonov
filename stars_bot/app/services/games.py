"""Продажа игровых пополнений: цены, проверка ID, заказ и присмотр за ним.

Три правила, купленные чужим опытом (в документации сервиса они помечены
как «деньги теряли»):

  1. Ответ ok:true означает «заказ принят», а не «алмазы у игрока».
     Почти всегда приходит processing, и настоящий исход узнаётся только
     опросом статуса.
  2. Если не присматривать за такими заказами, они зависают навсегда.
     Поэтому фоновая задача добирает их каждые несколько минут.
  3. У ожидания должен быть конец. Заказ, висящий дольше срока, закрывается
     возвратом денег — иначе клиент остаётся и без денег, и без товара.

Возврат по таймауту — не бесплатное решение: заказ может выполниться
позже, и тогда товар уйдёт даром. Поэтому владельцу шлётся заметное
предупреждение с номером заказа у поставщика, чтобы он проверил кабинет.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import ROUND_HALF_UP, Decimal

import aiosqlite
from aiogram import Bot

from app import db, runtime
from app.money import fmt, round_price
from app.services.fragment import DeliveryError, DeliveryUncertain

log = logging.getLogger(__name__)

#: Как часто добирать заказы, оставшиеся в работе.
WATCH_EVERY = 5 * 60
#: Сколько ждём выполнения, прежде чем вернуть деньги.
TIMEOUT_MINUTES = 20

DONE = {"completed", "complete", "done", "delivered", "success", "fulfilled"}
FAILED = {"failed", "fail", "error", "cancelled", "canceled", "rejected",
          "refunded", "expired"}


def offer_price(usd: Decimal, margin: int) -> int:
    """Цена пакета в дирамах: себестоимость по курсу плюс наценка."""
    rate = runtime.usd_rate()
    if rate <= 0:
        return 0
    cost = usd * rate
    with_margin = cost * (100 + max(margin, 0)) / 100
    return round_price(int(with_margin.to_integral_value(rounding=ROUND_HALF_UP)))


def offer_cost(usd: Decimal) -> int:
    """Во что пакет обходится владельцу, в дирамах."""
    rate = runtime.usd_rate()
    return int((usd * rate).to_integral_value(rounding=ROUND_HALF_UP)) if rate else 0


def margin_of(game: db.Game) -> int:
    return game.margin or runtime.margin_percent()


def idempotency_key(order_id: int) -> str:
    """Уникальный ключ заказа. Один заказ бота — один ключ, поэтому повтор
    запроса не спишет у поставщика деньги дважды."""
    return f"bot-{order_id}-{uuid.uuid5(uuid.NAMESPACE_URL, str(order_id)).hex[:12]}"


def status_of(order: dict | None) -> str:
    if not isinstance(order, dict):
        return ""
    return str(order.get("status") or order.get("state") or "").strip().lower()


async def place(
    provider, *, game: db.Game, offer_id: str, player_id: str,
    quantity: int, order_id: int,
) -> str:
    """Отправить заказ поставщику. Возвращает его номер заказа."""
    order = await provider.order_game(
        category_id=game.category_id, offer_id=offer_id,
        fields={game.field: player_id}, quantity=quantity,
        idempotency_key=idempotency_key(order_id),
    )
    external = str(order.get("order_id") or order.get("id") or "")
    status = status_of(order)

    if status in FAILED:
        raise DeliveryError(
            f"Поставщик отклонил заказ: {order.get('error') or status}"
        )
    if not external:
        raise DeliveryUncertain(
            "Поставщик не вернул номер заказа — проверить выдачу нечем."
        )
    return external


async def check(
    bot: Bot, conn: aiosqlite.Connection, provider, order: db.Order,
) -> str:
    """Спросить статус и закрыть заказ, если он решился.

    Возвращает: done | failed | waiting | timeout.
    """
    from app.services import delivery

    if not order.fragment_order_id:
        return "waiting"

    remote = await provider.order_status(order.fragment_order_id)
    status = status_of(remote)

    if status in DONE:
        if await db.transition_order(
            conn, order.id, expected=order.status, new=db.ORDER_DELIVERED, error=None
        ):
            await delivery.notify(bot, order.user_id, delivery._done_text(order))
            await delivery._ask_review(bot, conn, order)
            log.info("Игры: заказ %s выполнен", order.id)
        return "done"

    if status in FAILED:
        await _refund(bot, conn, order, f"поставщик вернул статус {status}")
        return "failed"

    if _minutes_waiting(order) >= TIMEOUT_MINUTES:
        await _refund(bot, conn, order, "заказ не выполнился за отведённое время")
        await delivery.notify_admins(
            bot,
            "⚠️ <b>Игровой заказ висел слишком долго</b>\n"
            f"├ Наш номер: <code>{order.id}</code>\n"
            f"├ У поставщика: <code>{order.fragment_order_id}</code>\n"
            f"└ Клиенту вернули <b>{fmt(order.price)}</b>\n\n"
            "<blockquote>Проверьте кабинет поставщика: если заказ всё-таки "
            "прошёл, товар ушёл бесплатно — списать деньги обратно можно "
            "в разделе «Клиенты».</blockquote>",
        )
        return "timeout"

    return "waiting"


def _minutes_waiting(order: db.Order) -> int:
    from datetime import datetime, timezone

    try:
        created = datetime.fromisoformat(order.created_at)
    except ValueError:
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - created).total_seconds() // 60)


async def _refund(
    bot: Bot, conn: aiosqlite.Connection, order: db.Order, reason: str,
) -> None:
    from app import texts
    from app.services import delivery

    if not await db.transition_order(
        conn, order.id, expected=order.status, new=db.ORDER_REFUNDED,
        error=reason[:1000],
    ):
        return
    await db.credit(conn, order.user_id, order.price)
    await delivery.notify(
        bot, order.user_id,
        texts.REFUNDED.format(
            order_id=order.id, price=fmt(order.price), support=texts.support()
        ),
    )
    log.warning("Игры: заказ %s возвращён — %s", order.id, reason)


async def watch_loop(provider, bot: Bot) -> None:
    """Фоновый присмотр: заказ без присмотра зависает навсегда."""
    while True:
        try:
            await asyncio.sleep(WATCH_EVERY)
            conn = await db.connect()
            try:
                pending = await db.unfinished_game_orders(conn)
                for order in pending:
                    await check(bot, conn, provider, order)
            finally:
                await conn.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.exception("Игры: присмотр за заказами упал: %s", exc)
            await asyncio.sleep(60)
