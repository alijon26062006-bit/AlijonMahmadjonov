"""Оплата с баланса, выдача через Fragment и возврат при неудаче.

Порядок операций выбран так, чтобы при любом сбое пользователь не остался
без денег и без товара:

  1. списываем деньги (атомарно, с проверкой баланса в том же UPDATE);
  2. создаём заказ в статусе delivering — он фиксирует, что деньги списаны;
  3. зовём Fragment;
  4. успех  → delivered;
     явный отказ Fragment → возвращаем деньги, refunded;
     нет ответа (таймаут/5xx) → failed, деньги held, разбирается админ.

Шаг 4 разделён намеренно: при таймауте неизвестно, ушли звёзды или нет, и
автовозврат означал бы раздачу товара бесплатно.
"""
from __future__ import annotations

import logging

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app import db, keyboards, runtime, texts
from app.config import settings
from app.money import fmt
from app.services.fragment import DeliveryError, DeliveryProvider, DeliveryUncertain

log = logging.getLogger(__name__)


async def notify(bot: Bot, chat_id: int, text: str, **kwargs) -> None:
    """Отправить сообщение, не роняя вызывающий код, если чат недоступен."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except TelegramAPIError as exc:
        log.warning("Не смог написать в чат %s: %s", chat_id, exc)


async def notify_admins(bot: Bot, text: str, **kwargs) -> None:
    for admin_id in settings.admin_ids:
        await notify(bot, admin_id, text, **kwargs)
    if settings.orders_chat_id:
        await notify(bot, settings.orders_chat_id, text, **kwargs)


class NotEnoughFunds(Exception):
    pass


async def purchase(
    bot: Bot,
    conn: aiosqlite.Connection,
    provider: DeliveryProvider,
    *,
    user_id: int,
    product_type: str,
    quantity: int,
    recipient: str,
    price: int,
    promo: str | None = None,
    discount: int = 0,
) -> db.Order:
    """Списать деньги, создать заказ и выдать товар.

    price — уже со скидкой; promo и discount едут в заказ, чтобы активация
    промокода списалась при выдаче, а в отчётах была видна причина скидки.

    Бросает NotEnoughFunds, если баланса не хватило (деньги не тронуты).
    """
    if not await db.charge(conn, user_id, price):
        raise NotEnoughFunds

    # Себестоимость фиксируем в заказе: курс меняется, и без этого прибыль
    # за прошлые дни пересчитывалась бы задним числом.
    order = await db.create_order(
        conn, user_id=user_id, product_type=product_type, quantity=quantity,
        recipient=recipient, price=price,
        cost=runtime.cost_of(product_type, quantity),
        promo=promo, discount=discount,
    )
    log.info("Заказ %s: списано %s с пользователя %s", order.id, fmt(price), user_id)
    await _run_delivery(bot, conn, provider, order)
    refreshed = await db.get_order(conn, order.id)
    return refreshed or order


async def _run_delivery(
    bot: Bot, conn: aiosqlite.Connection, provider: DeliveryProvider, order: db.Order
) -> None:
    try:
        if order.product_type == "stars":
            result = await provider.deliver_stars(order.recipient, order.quantity)
        elif order.product_type == "steam":
            result = await provider.deliver_steam(order.recipient, order.quantity)
        else:
            result = await provider.deliver_premium(order.recipient, order.quantity)

    except DeliveryError as exc:
        # Шлюз ответил отказом — выдачи точно не было, возвращаем деньги.
        await _refund(bot, conn, order, str(exc))
        await _watch_failures(bot, conn, str(exc))

    except DeliveryUncertain as exc:
        # Ответа нет. Деньги придерживаем, зовём админа разобраться вручную.
        await db.transition_order(
            conn, order.id, expected=db.ORDER_DELIVERING, new=db.ORDER_FAILED,
            error=str(exc)[:1000],
        )
        await notify(
            bot, order.user_id,
            f"⏳ <b>Заказ №{order.id} проверяется.</b>\n\n"
            f"Fragment не ответил вовремя. Проверяю вручную — напишу в течение "
            f"нескольких минут. Деньги в безопасности.",
        )
        await notify_admins(
            bot,
            texts.ADMIN_ORDER_FAILED.format(
                order_id=order.id, title=order.title, recipient=order.recipient,
                user_id=order.user_id, error=str(exc)[:400],
            )
            + "\n\n❗️ Проверьте в кабинете Fragment, дошёл ли заказ:\n"
            f"• дошёл → <code>/done {order.id}</code>\n"
            f"• не дошёл → <code>/refund {order.id}</code>",
        )
        log.error("Заказ %s: неопределённый исход — %s", order.id, exc)

    except Exception as exc:  # noqa: BLE001 — баг в коде не должен съесть деньги
        log.exception("Заказ %s: непредвиденная ошибка", order.id)
        await _refund(bot, conn, order, f"{type(exc).__name__}: {exc}")

    else:
        await db.transition_order(
            conn, order.id, expected=db.ORDER_DELIVERING, new=db.ORDER_DELIVERED,
            fragment_order_id=result.order_id, error=None,
        )
        await runtime.note_delivery_ok(conn, order.product_type, order.quantity)
        await notify(
            bot, order.user_id, _done_text(order), reply_markup=keyboards.back()
        )
        await notify_admins(
            bot,
            texts.ADMIN_ORDER_DONE.format(
                order_id=order.id, title=order.title, recipient=order.recipient,
                price=fmt(order.price), user_id=order.user_id,
                external=result.order_id or "—",
            ),
        )
        log.info("Заказ %s выдан, fragment_id=%s", order.id, result.order_id)
        await _ask_review(bot, conn, order)


async def _refund(
    bot: Bot, conn: aiosqlite.Connection, order: db.Order, reason: str
) -> None:
    """Вернуть деньги за заказ. Переход статуса делается первым, поэтому
    повторный вызов по тому же заказу не начислит деньги дважды."""
    moved = await db.transition_order(
        conn, order.id, expected=db.ORDER_DELIVERING, new=db.ORDER_REFUNDED,
        error=reason[:1000],
    )
    if not moved:
        log.warning("Заказ %s: возврат пропущен, статус уже изменён", order.id)
        return

    await db.credit(conn, order.user_id, order.price)
    await notify(
        bot, order.user_id,
        texts.REFUNDED.format(
            order_id=order.id, price=fmt(order.price), support=texts.support()
        ),
        reply_markup=keyboards.back(),
    )
    await notify_admins(
        bot,
        texts.ADMIN_ORDER_FAILED.format(
            order_id=order.id, title=order.title, recipient=order.recipient,
            user_id=order.user_id, error=reason[:400],
        ),
    )
    log.warning("Заказ %s: возвращено %s — %s", order.id, fmt(order.price), reason)


async def retry_failed(
    bot: Bot, conn: aiosqlite.Connection, provider: DeliveryProvider, order: db.Order
) -> bool:
    """Повторить выдачу зависшего заказа. Деньги уже списаны, повторно не берём."""
    if not await db.transition_order(
        conn, order.id, expected=db.ORDER_FAILED, new=db.ORDER_DELIVERING
    ):
        return False
    await _run_delivery(bot, conn, provider, order)
    return True


async def manual_refund(bot: Bot, conn: aiosqlite.Connection, order: db.Order) -> bool:
    """Возврат по решению админа для заказа, зависшего в failed."""
    if not await db.transition_order(
        conn, order.id, expected=db.ORDER_FAILED, new=db.ORDER_REFUNDED
    ):
        return False
    await db.credit(conn, order.user_id, order.price)
    await notify(
        bot, order.user_id,
        texts.REFUNDED.format(
            order_id=order.id, price=fmt(order.price), support=texts.support()
        ),
    )
    return True


async def manual_complete(bot: Bot, conn: aiosqlite.Connection, order: db.Order) -> bool:
    """Админ подтвердил, что заказ всё-таки дошёл."""
    if not await db.transition_order(
        conn, order.id, expected=db.ORDER_FAILED, new=db.ORDER_DELIVERED
    ):
        return False
    await notify(bot, order.user_id, _done_text(order))
    await _ask_review(bot, conn, order)
    return True


def _done_text(order: db.Order) -> str:
    """Сообщение о выполненном заказе. У Steam свой текст: получатель там —
    логин, а не юзернейм Telegram, и путать их нельзя."""
    if order.product_type == "steam":
        return texts.STEAM_DELIVERED.format(
            order_id=order.id, login=order.recipient,
            amount=order.quantity, currency=runtime.steam_currency(),
            price=fmt(order.price),
        )
    return texts.DELIVERED.format(
        order_id=order.id, title=order.title,
        recipient=order.recipient, price=fmt(order.price),
    )


async def _ask_review(bot: Bot, conn: aiosqlite.Connection, order: db.Order) -> None:
    """Спросить отзыв. Импорт внутри: сервис отзывов сам зовёт базу и тексты,
    а на верхнем уровне это замкнуло бы модули друг на друга."""
    from app.services import reviews

    try:
        await reviews.offer(bot, conn, order)
    except Exception as exc:  # noqa: BLE001 — отзыв не должен ломать выдачу
        log.info("Заказ %s: не спросил отзыв — %s", order.id, exc)


async def _watch_failures(bot: Bot, conn: aiosqlite.Connection, reason: str) -> None:
    """Считать неудачи подряд и гасить продажу, если выдача сломалась.

    Без этого при пустом кошельке бот продолжал бы принимать заказы: клиенты
    платили бы и получали возврат, а владелец узнавал бы об этом от них.
    """
    streak = await runtime.note_delivery_fail(conn)
    limit = runtime.autostop_after()
    if streak < limit:
        return

    already_off = runtime.get_bool("autostopped")
    await runtime.autostop(conn)
    if already_off:
        return  # не повторяем тревогу на каждый следующий заказ

    await notify_admins(
        bot,
        "🛑 <b>Продажа выключена автоматически</b>\n\n"
        f"Подряд не прошло заказов: <b>{streak}</b>.\n"
        "Скорее всего кончились деньги на кошельке Fragment "
        "или сломался шлюз.\n\n"
        f"Последняя ошибка:\n<code>{reason[:300]}</code>\n\n"
        "Деньги клиентам возвращены. Пополните кошелёк и отметьте это "
        "в /panel → 💼 Кошелёк — продажа включится обратно.",
    )
