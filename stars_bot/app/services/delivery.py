"""Оркестрация выдачи: подтверждение оплаты → Fragment → уведомления."""
from __future__ import annotations

import logging

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app import db, texts
from app.services.fragment import DeliveryError, DeliveryProvider

log = logging.getLogger(__name__)


async def notify_user(bot: Bot, user_id: int, text: str) -> None:
    """Уведомить покупателя. Заблокированный бот не должен ронять выдачу."""
    try:
        await bot.send_message(user_id, text)
    except TelegramAPIError as exc:
        log.warning("Не смог написать пользователю %s: %s", user_id, exc)


async def deliver(
    bot: Bot,
    conn: aiosqlite.Connection,
    provider: DeliveryProvider,
    order: db.Order,
) -> tuple[bool, str]:
    """Выдать оплаченный заказ.

    Заказ уже должен быть переведён в статус ``delivering`` вызывающей стороной —
    это защищает от двойной выдачи при одновременном клике двух админов.

    Возвращает (успех, текст для админа).
    """
    try:
        if order.product_type == "stars":
            result = await provider.deliver_stars(order.recipient, order.quantity)
        else:
            result = await provider.deliver_premium(order.recipient, order.quantity)
    except DeliveryError as exc:
        message = str(exc)
    except Exception as exc:  # noqa: BLE001 — сеть/парсинг: заказ не должен зависнуть
        log.exception("Неожиданная ошибка выдачи заказа %s", order.id)
        message = f"{type(exc).__name__}: {exc}"
    else:
        await db.update_order(
            conn, order.id,
            status=db.STATUS_DELIVERED,
            fragment_order_id=result.order_id,
            error=None,
        )
        await notify_user(
            bot, order.user_id,
            texts.ORDER_DELIVERED.format(
                order_id=order.id, title=order.title,
                recipient=order.recipient, support=texts.support(),
            ),
        )
        log.info("Заказ %s выдан, fragment_id=%s", order.id, result.order_id)
        return True, texts.ADMIN_DELIVERED.format(
            order_id=order.id, fragment_id=result.order_id or "—"
        )

    await db.update_order(conn, order.id, status=db.STATUS_FAILED, error=message[:1000])
    await notify_user(
        bot, order.user_id,
        texts.ORDER_FAILED_USER.format(order_id=order.id, support=texts.support()),
    )
    log.error("Заказ %s: выдача не удалась — %s", order.id, message)
    return False, texts.ADMIN_FAILED.format(order_id=order.id, error=message[:500])
