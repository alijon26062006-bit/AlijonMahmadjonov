"""Пополнение баланса через TelegaPAY: пересчёт валюты и слежение за оплатой.

Клиент называет сумму в сомони — привычных ему деньгах. Шлюз сомони не
принимает, поэтому счёт выставляется в рублях (или USDT) по курсу из
панели, а на баланс возвращается ровно та сумма в сомони, которую человек
и просил.

Баланс пополняется только при явно успешном статусе. Незнакомый статус —
это «ещё не оплачено», а не «оплачено»: начислить за непрошедший платёж
хуже, чем заставить подождать.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import ROUND_HALF_UP, Decimal

import aiosqlite
from aiogram import Bot

from app import db, runtime, texts
from app.config import settings
from app.money import fmt
from app.services.telegapay import PaymentError, TelegaPay

log = logging.getLogger(__name__)

METHOD = "telegapay"
POLL_EVERY = 15          # секунд между проверками статуса
POLL_MINUTES = 30        # сколько всего ждём оплату


def client() -> TelegaPay:
    from app.services.telegapay import BASE_URL

    return TelegaPay(
        runtime.get("tpay_key") or settings.telegapay_key,
        base_url=runtime.get("tpay_base") or BASE_URL,
    )


def enabled() -> bool:
    return runtime.get_bool("tpay_on") and bool(
        runtime.get("tpay_key") or settings.telegapay_key
    )


def currency() -> str:
    return (runtime.get("tpay_currency") or "RUB").upper()


def rate_diram() -> int:
    """Сколько дирам в одной единице валюты шлюза."""
    return runtime.get_int("tpay_rate_diram")


def to_currency(diram: int) -> Decimal | None:
    """Сомони -> валюта шлюза. None, если курс не задан."""
    rate = rate_diram()
    if rate <= 0:
        return None
    return (Decimal(diram) / Decimal(rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def to_diram(amount: Decimal) -> int:
    return int((amount * rate_diram()).to_integral_value(rounding=ROUND_HALF_UP))


async def start_payment(
    conn: aiosqlite.Connection, user_id: int, diram: int,
) -> tuple[db.Deposit, str]:
    """Создать платёж и заявку. Бросает PaymentError, если шлюз отказал."""
    amount = to_currency(diram)
    if amount is None:
        raise PaymentError("не задан курс валюты — заполните его в панели")

    deposit = await db.create_deposit(
        conn, user_id=user_id, amount=diram, method=METHOD, receipt_file_id="",
    )
    try:
        link = await client().create_paylink(
            amount=amount, currency=currency(),
            order_id=f"dep{deposit.id}",
            description=f"Пополнение баланса №{deposit.id}",
            user_id=str(user_id),
        )
    except PaymentError:
        # Заявку не оставляем висеть: платежа за ней не будет.
        await db.resolve_deposit(conn, deposit.id, approved=False, admin_id=0)
        raise

    await db.set_deposit_reference(conn, deposit.id, link.transaction_id)
    return deposit, link.url


async def check_once(
    bot: Bot, conn: aiosqlite.Connection, deposit: db.Deposit,
) -> str:
    """Спросить статус и зачислить, если оплачено. Возвращает статус словом."""
    if not deposit.reference:
        return "no_transaction"

    status = await client().check_status(deposit.reference)
    if status.paid:
        await credit(bot, conn, deposit)
        return "paid"
    if status.failed:
        await db.resolve_deposit(conn, deposit.id, approved=False, admin_id=0)
        return "failed"
    return status.raw_status or "pending"


async def credit(bot: Bot, conn: aiosqlite.Connection, deposit: db.Deposit) -> bool:
    """Зачислить оплату. Переход статуса первым — деньги не удвоятся."""
    if not await db.resolve_deposit(conn, deposit.id, approved=True, admin_id=0):
        return False
    await db.credit(conn, deposit.user_id, deposit.amount, as_deposit=True)
    user = await db.get_user(conn, deposit.user_id)
    try:
        await bot.send_message(
            deposit.user_id,
            texts.DEPOSIT_APPROVED.format(
                amount=fmt(deposit.amount),
                balance=fmt(user.balance if user else deposit.amount),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — деньги уже зачислены
        log.info("Не смог сообщить о пополнении %s: %s", deposit.id, exc)
    log.info("TelegaPAY: заявка %s оплачена, зачислено %s",
             deposit.id, fmt(deposit.amount))
    return True


async def watch(bot: Bot, deposit_id: int) -> None:
    """Ждать оплату в фоне, пока клиент платит на стороне шлюза."""
    deadline = POLL_MINUTES * 60 // POLL_EVERY
    for _ in range(deadline):
        await asyncio.sleep(POLL_EVERY)
        conn = await db.connect()
        try:
            deposit = await db.get_deposit(conn, deposit_id)
            if deposit is None or deposit.status != db.DEP_PENDING:
                return
            result = await check_once(bot, conn, deposit)
            if result in ("paid", "failed"):
                return
        except PaymentError as exc:
            log.info("TelegaPAY: статус заявки %s не пришёл — %s", deposit_id, exc)
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.exception("TelegaPAY: слежение за заявкой %s упало: %s", deposit_id, exc)
            return
        finally:
            await conn.close()
