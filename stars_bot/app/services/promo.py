"""Промокоды при покупке: одно поле на все коды и все товары.

Клиенту неважно, какой у него код — на скидку или на баланс. Он видит
кнопку «Промокод» на экране подтверждения и вводит туда что есть:
скидочный код уменьшает цену заказа, бонусный сразу кладёт деньги на
баланс. Код на скидку можно ввести и заранее, в профиле: бот запомнит
его и сам подставит в следующую покупку.

Скидка по коду — одна на клиента: активация списывается после выдачи
(db.transition_order), а пока заказ идёт, второй заказ с тем же кодом
не пропускает db.check_discount.
"""
from __future__ import annotations

import aiosqlite

from app import db, texts
from app.money import discount_of, fmt


async def pending(conn: aiosqlite.Connection, user_id: int):
    """Сохранённый код на скидку, если им ещё можно воспользоваться."""
    code = await db.saved_promo_code(conn, user_id)
    if not code:
        return None
    promo = await db.check_discount(conn, code, user_id)
    if isinstance(promo, str):
        # Пока код держит незавершённый заказ, не забываем его: заказ
        # может сорваться, и тогда скидка снова понадобится.
        if promo != "in_use":
            await db.forget_saved_promo(conn, user_id)
        return None
    return promo


async def autofill(state, conn: aiosqlite.Connection, user_id: int) -> None:
    """Подставить сохранённый код, если клиент сам ничего не выбирал."""
    data = await state.get_data()
    if data.get("promo") or data.get("promo_touched"):
        return
    promo = await pending(conn, user_id)
    if promo is not None:
        await state.update_data(promo=promo["code"], promo_percent=promo["percent"])


def totals(data: dict) -> tuple[int, int, int]:
    """(полная цена, скидка, к оплате)."""
    price = int(data.get("price") or 0)
    discount = discount_of(price, int(data.get("promo_percent") or 0))
    return price, discount, price - discount


def block(data: dict) -> str:
    """Строки про скидку для экрана подтверждения. Пусто — скидки нет."""
    price, discount, _ = totals(data)
    if not discount:
        return ""
    return texts.CONFIRM_DISCOUNT.format(
        full=fmt(price), code=data["promo"],
        percent=data["promo_percent"], saved=fmt(discount),
    )


async def enter(
    conn: aiosqlite.Connection, state, code: str, user_id: int,
) -> tuple[bool, str]:
    """Код, введённый на шаге покупки. (принят ли, ответ клиенту).

    Скидочный — ложится в заказ; бонусный — сразу на баланс, чтобы
    клиенту не надо было искать для него другое место.
    """
    promo = await db.check_discount(conn, code, user_id)
    if not isinstance(promo, str):
        await state.update_data(promo=promo["code"], promo_percent=promo["percent"],
                                promo_touched=True)
        _, discount, _ = totals(await state.get_data())
        return True, texts.ORDER_PROMO_OK.format(
            code=promo["code"], percent=promo["percent"], saved=fmt(discount),
        )
    if promo != "not_for_order":
        return False, texts.PROMO_ERRORS.get(promo, texts.PROMO_ERRORS["not_found"])

    result = await db.redeem_promo(conn, code, user_id)
    if isinstance(result, str):
        return False, texts.PROMO_ERRORS.get(result, texts.PROMO_ERRORS["not_found"])
    user = await db.get_user(conn, user_id)
    return True, texts.PROMO_OK.format(amount=fmt(result),
                                       balance=fmt(user.balance if user else 0))


async def still_valid(conn: aiosqlite.Connection, data: dict, user_id: int) -> bool:
    """Перед оплатой: код мог кончиться, пока клиент думал."""
    if not data.get("promo") or not data.get("promo_percent"):
        return True
    return not isinstance(await db.check_discount(conn, data["promo"], user_id), str)


async def drop(state) -> None:
    await state.update_data(promo=None, promo_percent=0, promo_touched=True)
