"""Покупка дополнительных голосов за Telegram Stars (валюта XTR).

Первый голос в матче всегда бесплатный. Купленные — возможность поддержать
участника ещё раз. Второй способ получить голос — позвать друга, поэтому он
предлагается прямо здесь же.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from config import Config
from handlers.referral import show_invite
from services import keyboards, texts, ui
from services.validation import InputError, as_int
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="payments")

CURRENCY = "XTR"


class Buy(StatesGroup):
    waiting_amount = State()


def max_votes(price: int) -> int:
    """Сколько голосов влезает в один счёт Telegram."""
    return max(1, texts.MAX_STARS_PER_INVOICE // max(1, price))


async def _screen(message: Message, repo: Repo, settings: Settings, state: FSMContext) -> None:
    price = settings.vote_price
    limit = max_votes(price)
    await state.set_state(Buy.waiting_amount)
    await message.answer(
        texts.buy_screen(
            price=price,
            balance=repo.vote_balance(message.from_user.id),
            stars_link=settings.get("stars_link"),
            max_votes=limit,
        ),
        reply_markup=keyboards.buy(price, settings.get("referral_enabled"), limit),
        disable_web_page_preview=True,
    )


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_BUY)))
@router.message(Command("buy"))
async def open_buy(
    message: Message, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    if not settings.get("paid_votes_enabled"):
        await message.answer("Покупка голосов сейчас отключена.")
        return
    repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await _screen(message, repo, settings, state)


@router.message(
    Buy.waiting_amount,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
async def command_leaves_buying(message: Message, state: FSMContext) -> None:
    """Из ввода количества выходим командой или кнопкой меню."""
    await state.clear()
    raise SkipHandler()


@router.message(Buy.waiting_amount)
async def amount_entered(
    message: Message, repo: Repo, settings: Settings, state: FSMContext
) -> None:
    """Человек ввёл количество — считаем сумму и показываем к оплате."""
    price = settings.vote_price
    limit = max_votes(price)
    try:
        votes = as_int(message.text or "", minimum=1, maximum=limit, example="5")
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    await state.clear()
    await message.answer(
        texts.buy_confirm(votes, price), reply_markup=keyboards.pay(votes, votes * price)
    )


@router.callback_query(F.data == "buy:invite")
async def invite_instead(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    """Второй способ получить голос — позвать друга."""
    await state.clear()
    await callback.answer()
    await show_invite(callback.message, repo, config, settings, user=callback.from_user)


@router.callback_query(F.data == "buy:cancel")
async def cancel_buy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await ui.edit_or_send(callback, "Покупка отменена.")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def send_invoice(
    callback: CallbackQuery, bot: Bot, config: Config, settings: Settings, state: FSMContext
) -> None:
    if not settings.get("paid_votes_enabled"):
        await callback.answer("Покупка голосов отключена.", show_alert=True)
        return

    raw = callback.data.split(":")[1]
    if not raw.isdigit():
        await callback.answer("Не понял количество.", show_alert=True)
        return

    price = settings.vote_price
    votes = int(raw)
    total = votes * price
    if not 1 <= votes <= max_votes(price):
        await callback.answer("Такое количество не подходит.", show_alert=True)
        return

    await state.clear()
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"{texts.votes_word(votes)}",
            description=f"Дополнительные голоса в батлах. {votes} × {price}⭐",
            payload=f"votes:{votes}",
            currency=CURRENCY,
            prices=[LabeledPrice(label=texts.votes_word(votes), amount=total)],
        )
    except TelegramAPIError as error:
        log.error("Не удалось выставить счёт: %s", error)
        await callback.answer("Не получилось выставить счёт, попробуйте позже.", show_alert=True)
        return
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, settings: Settings) -> None:
    ok = settings.get("paid_votes_enabled") and query.invoice_payload.startswith("votes:")
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
        f"✅ Начислено <b>{votes}</b> "
        f"{texts.plural(votes, 'голос', 'голоса', 'голосов')}.\n"
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
