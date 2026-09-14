"""Пополнение баланса переводом на карту с ручной проверкой чека."""
from __future__ import annotations

import logging

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import db, keyboards, texts
from app.services import dcpay
from app import runtime
from app.config import settings
from app.money import fmt, parse
from app.states import Deposit

log = logging.getLogger(__name__)
router = Router(name="deposit")


@router.callback_query(F.data == "m:deposit")
async def cb_methods(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        texts.DEPOSIT_METHODS, reply_markup=keyboards.deposit_methods()
    )
    await call.answer()


@router.callback_query(F.data == "dep:soon")
async def cb_soon(call: CallbackQuery) -> None:
    await call.answer(texts.DEPOSIT_SOON, show_alert=True)


@router.callback_query(F.data == "dep:card")
async def cb_card(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Deposit.amount)
    await call.message.edit_text(
        texts.DEPOSIT_ASK_AMOUNT.format(min_amount=fmt(runtime.min_deposit())),
        reply_markup=keyboards.cancel(),
    )
    await call.answer()


@router.message(Deposit.amount, F.text)
async def on_amount(message: Message, state: FSMContext) -> None:
    amount = parse(message.text or "")
    if amount is None or amount <= 0:
        await message.answer(texts.DEPOSIT_BAD_AMOUNT)
        return
    if amount < runtime.min_deposit():
        await message.answer(
            texts.DEPOSIT_TOO_SMALL.format(min_amount=fmt(runtime.min_deposit()))
        )
        return

    # Код платежа нужен, чтобы найти перевод в выписке, даже если чек
    # придёт позже или не придёт вовсе.
    reference = dcpay.make_reference()
    await state.update_data(amount=amount, reference=reference)
    await state.set_state(Deposit.receipt)
    body, markup = _requisites(amount, reference)
    await message.answer(body, reply_markup=markup)


def _requisites(amount: int, reference: str) -> tuple[str, object]:
    """Экран реквизитов: один, короткий, с кнопками под рукой.

    Раньше на нём же просили прислать чек. Клиент этого ещё не сделал —
    и просьба тонула в длинном тексте. Теперь про чек говорим отдельным
    шагом, после нажатия «Я оплатил».
    """
    card = runtime.get("pay_card_number") or "— реквизиты не заданы —"
    holder = runtime.get("pay_card_holder")
    bank = runtime.get("pay_card_bank")
    city = runtime.get("pay_city")
    note = runtime.get("pay_extra")

    where = " · ".join(part for part in (bank, city) if part)
    body = texts.DEPOSIT_REQUISITES.format(
        amount=fmt(amount),
        card=card,
        holder=f"👤 <b>{holder}</b>\n" if holder else "",
        bank=f"🏦 {where}\n" if where else "",
        extra=f"\n{note}\n" if note else "\n",
        dc_block=texts.DEPOSIT_DC_BLOCK.format(reference=reference),
    )

    link = ""
    if dcpay.is_ready():
        link = dcpay.build_link(
            dcpay.account(), amount,
            dcpay.build_comment(dcpay.comment_prefix(), reference),
            dcpay.service(),
        )
    # Копировать даём только настоящий номер: владелец мог записать
    # реквизиты словами, и кнопка «скопировать» скопировала бы фразу.
    digits = "".join(ch for ch in card if ch.isdigit())
    return body, keyboards.deposit_pay(link, digits if len(digits) >= 8 else "")


@router.callback_query(Deposit.receipt, F.data == "dep:paid")
async def cb_paid(call: CallbackQuery, state: FSMContext) -> None:
    """«Я оплатил» — теперь и только теперь просим чек."""
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await state.clear()
        await call.answer("Заявка потерялась, начните заново.", show_alert=True)
        return
    await call.message.edit_text(
        texts.DEPOSIT_ASK_RECEIPT.format(amount=fmt(amount)),
        reply_markup=keyboards.deposit_receipt(),
    )
    await call.answer()


@router.callback_query(Deposit.receipt, F.data == "dep:back")
async def cb_back_to_requisites(call: CallbackQuery, state: FSMContext) -> None:
    """Вернуться к реквизитам: клиент мог закрыть банк, не заплатив."""
    data = await state.get_data()
    amount, reference = data.get("amount"), data.get("reference", "")
    if not amount:
        await state.clear()
        await call.answer("Заявка потерялась, начните заново.", show_alert=True)
        return
    body, markup = _requisites(amount, reference)
    await call.message.edit_text(body, reply_markup=markup)
    await call.answer()


@router.message(Deposit.receipt, F.photo | F.document)
async def on_receipt(
    message: Message, state: FSMContext, conn: aiosqlite.Connection, bot: Bot
) -> None:
    data = await state.get_data()
    amount = data.get("amount")
    if not amount:
        await state.clear()
        await message.answer("Заявка потерялась. Начните заново: /menu")
        return

    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    deposit = await db.create_deposit(
        conn, user_id=message.from_user.id, amount=amount,
        method="Перевод на карту", receipt_file_id=file_id,
        reference=data.get("reference"),
    )
    await state.clear()
    await message.answer(
        texts.DEPOSIT_SENT.format(deposit_id=deposit.id, amount=fmt(amount)),
        reply_markup=keyboards.back(),
    )

    buyer = f"@{message.from_user.username}" if message.from_user.username else (
        message.from_user.first_name or "без имени"
    )
    caption = texts.ADMIN_NEW_DEPOSIT.format(
        deposit_id=deposit.id, amount=fmt(amount), method=deposit.method,
        buyer=buyer, user_id=message.from_user.id,
        reference=deposit.reference or "—",
    )
    targets = list(settings.admin_ids)
    if settings.orders_chat_id:
        targets.append(settings.orders_chat_id)
    for chat_id in targets:
        try:
            await message.copy_to(
                chat_id, caption=caption, reply_markup=keyboards.admin_deposit(deposit.id)
            )
        except TelegramAPIError as exc:
            log.warning("Заявка %s не ушла в чат %s: %s", deposit.id, chat_id, exc)


@router.message(Deposit.receipt)
async def on_receipt_wrong(message: Message) -> None:
    await message.answer(texts.DEPOSIT_NEED_PHOTO)

