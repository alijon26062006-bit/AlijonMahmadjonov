"""Покупка дополнительных голосов за Telegram Stars (валюта XTR).

Первый голос в матче всегда бесплатный. Купленные голоса — это возможность
поддержать участника ещё раз; списываются по одному при голосовании.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import Config
from services import keyboards
from storage.repo import Repo

log = logging.getLogger(__name__)
router = Router(name="payments")

CURRENCY = "XTR"


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_BUY)))
@router.message(Command("buy"))
async def show_packs(message: Message, repo: Repo, config: Config) -> None:
    if not config.paid_votes_enabled:
        await message.answer("Покупка голосов сейчас отключена.")
        return

    balance = repo.vote_balance(message.from_user.id)
    await message.answer(
        "🎁 <b>Дополнительные голоса</b>\n\n"
        "Первый голос в каждом матче бесплатный. Купленные голоса позволяют "
        "поддержать участника ещё раз.\n\n"
        f"Ваш баланс: <b>{balance}</b>",
        reply_markup=keyboards.vote_packs(config.vote_packs),
    )


@router.callback_query(F.data.startswith("buy:"))
async def send_invoice(callback: CallbackQuery, config: Config, bot: Bot) -> None:
    if not config.paid_votes_enabled:
        await callback.answer("Покупка голосов отключена.", show_alert=True)
        return

    votes = int(callback.data.split(":")[1])
    pack = next((p for p in config.vote_packs if p.votes == votes), None)
    if pack is None:
        await callback.answer("Такого пакета нет.", show_alert=True)
        return

    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=pack.title,
            description=f"{pack.votes} дополнительных голосов в батлах",
            payload=f"votes:{pack.votes}",
            currency=CURRENCY,
            prices=[LabeledPrice(label=pack.title, amount=pack.stars)],
        )
    except TelegramAPIError as error:
        log.error("Не удалось выставить счёт: %s", error)
        await callback.answer("Не получилось выставить счёт, попробуйте позже.", show_alert=True)
        return
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, config: Config) -> None:
    ok = config.paid_votes_enabled and query.invoice_payload.startswith("votes:")
    await query.answer(ok=ok, error_message=None if ok else "Покупка недоступна.")


@router.message(F.successful_payment)
async def payment_done(message: Message, repo: Repo) -> None:
    payment = message.successful_payment
    votes = int(payment.invoice_payload.split(":")[1])

    # charge_id уникален в БД — повторная доставка апдейта не начислит голоса дважды
    if not repo.record_payment(
        user_id=message.from_user.id,
        charge_id=payment.telegram_payment_charge_id,
        stars=payment.total_amount,
        votes=votes,
    ):
        log.info("Повторный апдейт об оплате %s пропущен", payment.telegram_payment_charge_id)
        return

    repo.add_votes(message.from_user.id, votes)
    await message.answer(
        f"✅ Начислено <b>{votes}</b> голосов.\n"
        f"Баланс: <b>{repo.vote_balance(message.from_user.id)}</b>\n\n"
        f"<code>{payment.telegram_payment_charge_id}</code>"
    )


@router.message(Command("payments"))
async def history(message: Message, repo: Repo) -> None:
    rows = repo.payment_history(message.from_user.id)
    if not rows:
        await message.answer("Покупок пока не было.")
        return
    lines = [
        f"{row['created_at']} · {row['votes']} голосов за {row['stars']}⭐ ({row['status']})"
        for row in rows
    ]
    await message.answer("🧾 <b>История покупок</b>\n\n" + "\n".join(lines))


@router.message(Command("refund"))
async def refund(
    message: Message, command: CommandObject, repo: Repo, config: Config, bot: Bot
) -> None:
    """Возврат звёзд по charge_id. Только для админов."""
    if message.from_user.id not in config.admin_ids:
        return
    args = (command.args or "").split()
    if len(args) != 2 or not args[0].isdigit():
        await message.answer("Формат: /refund &lt;user_id&gt; &lt;charge_id&gt;")
        return

    user_id, charge_id = int(args[0]), args[1]
    try:
        await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)
    except TelegramAPIError as error:
        await message.answer(f"Возврат не прошёл: {error}")
        return

    if repo.mark_refunded(charge_id):
        await message.answer("Возврат выполнен, голоса сняты с баланса.")
    else:
        await message.answer("Звёзды возвращены, но платёж не найден в базе.")
