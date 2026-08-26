"""Пополнение вручную: оплата по реквизитам и чек на проверку.

Второй способ купить голоса — для тех, у кого нет звёзд. Человек платит по
реквизитам, присылает скриншот чека, админ принимает или отклоняет.

Главная защита — **одна открытая заявка на человека**. Держит её сама база
частичным уникальным индексом, поэтому десять чеков подряд не превратятся в
десять начислений даже при одновременных нажатиях.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import CallbackQuery, Message

from config import Config
from services import keyboards, texts, ui
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="topup")


class Topup(StatesGroup):
    waiting_receipt = State()


def enabled(settings: Settings) -> bool:
    return bool(settings.get("manual_pay_enabled")) and bool(
        settings.get("manual_pay_details")
    )


def amount_of(settings: Settings, votes: int) -> str:
    return texts.manual_amount(
        votes, settings.get("manual_pay_price"), settings.get("manual_pay_currency")
    )


@router.callback_query(F.data.startswith("manual:receipt:"))
async def ask_receipt(
    callback: CallbackQuery, repo: Repo, settings: Settings, state: FSMContext
) -> None:
    """«Я оплатил» — просим чек и заводим заявку."""
    if not enabled(settings):
        await callback.answer("Этот способ сейчас недоступен.", show_alert=True)
        return

    votes = _votes(callback.data)
    if votes is None:
        await callback.answer("Кнопка устарела.", show_alert=True)
        return

    amount = amount_of(settings, votes)
    waiting = repo.pending_topup(callback.from_user.id)

    if waiting is not None and waiting["photo_id"]:
        # чек уже у админа — второй заявкой его не обойти
        await ui.send(
            callback,
            texts.manual_already_pending(int(waiting["votes"]), str(waiting["amount"])),
        )
        await callback.answer("Заявка уже на проверке.", show_alert=True)
        return

    if waiting is not None:
        # заявка есть, но чек так и не пришёл — продолжаем её, а не плодим новые
        topup_id = int(waiting["id"])
        repo.retarget_topup(topup_id, votes, amount)
    else:
        topup_id = repo.open_topup(callback.from_user.id, votes, amount)
        if topup_id is None:  # успел создать в другом окне
            await callback.answer("Заявка уже на проверке.", show_alert=True)
            return

    await state.set_state(Topup.waiting_receipt)
    await state.update_data(topup_id=topup_id)
    await ui.edit_or_send(
        callback, texts.MANUAL_ASK_RECEIPT, reply_markup=keyboards.manual_wait()
    )
    await callback.answer()


@router.callback_query(F.data == "manual:cancel")
async def cancel(callback: CallbackQuery, repo: Repo, state: FSMContext) -> None:
    """Передумал платить — снимаем заявку, чтобы не блокировала следующую."""
    await state.clear()
    repo.cancel_topup(callback.from_user.id)
    await ui.edit_or_send(callback, "Заявка отменена.")
    await callback.answer()


@router.message(Topup.waiting_receipt, F.photo | F.document)
async def take_receipt(
    message: Message, bot: Bot, repo: Repo, config: Config, settings: Settings,
    state: FSMContext,
) -> None:
    """Получили чек — отправляем админу на решение."""
    data = await state.get_data()
    topup = repo.topup(int(data.get("topup_id", 0)))
    await state.clear()

    if topup is None or topup["status"] != "pending":
        await message.answer("Заявка не найдена. Начните заново.")
        return

    photo_id = message.photo[-1].file_id if message.photo else message.document.file_id
    repo.attach_receipt(int(topup["id"]), photo_id)

    await message.answer(texts.manual_sent(int(topup["votes"]), str(topup["amount"])))
    await _send_to_admins(bot, repo, config, topup, photo_id)


@router.message(
    Topup.waiting_receipt,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
async def command_leaves_receipt(message: Message, repo: Repo, state: FSMContext) -> None:
    """Команда или кнопка меню выводят из ожидания чека.

    Заявку при этом снимаем: человек ушёл заниматься другим, а висящая
    заявка не давала бы ему начать заново.
    """
    await state.clear()
    repo.cancel_topup(message.from_user.id)
    raise SkipHandler()


@router.message(Topup.waiting_receipt)
async def not_a_receipt(message: Message) -> None:
    """Прислали текст вместо картинки — объясняем, а заявку не теряем."""
    await message.answer(texts.MANUAL_NEED_PHOTO, reply_markup=keyboards.manual_wait())


async def _send_to_admins(
    bot: Bot, repo: Repo, config: Config, topup, photo_id: str
) -> None:
    user = repo.get_user(int(topup["user_id"]))
    caption = texts.manual_for_admin(
        user, int(topup["votes"]), str(topup["amount"]), int(topup["id"])
    )
    markup = keyboards.topup_decision(int(topup["id"]))
    for admin_id in config.admin_ids:
        try:
            await bot.send_photo(
                admin_id, photo_id, caption=caption, reply_markup=markup
            )
        except TelegramAPIError as error:
            log.warning("Не смог показать чек админу %s: %s", admin_id, error)


@router.callback_query(F.data.startswith("topup:"))
async def decide(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config
) -> None:
    """Админ принимает или отклоняет чек."""
    if callback.from_user.id not in config.admin_ids:
        return

    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Кнопка устарела.", show_alert=True)
        return

    accepted = parts[1] == "ok"
    topup_id = int(parts[2])
    topup = repo.topup(topup_id)
    if topup is None:
        await callback.answer("Заявки нет.", show_alert=True)
        return

    # решение принимается один раз: два админа могли нажать одновременно
    if not repo.decide_topup(topup_id, accepted):
        await callback.answer("Эту заявку уже рассмотрели.", show_alert=True)
        return

    user_id = int(topup["user_id"])
    votes = int(topup["votes"])
    if accepted:
        repo.add_votes(user_id, votes)
        note = f"✅ Принято: +{votes} голосов"
        message = texts.manual_accepted(votes, repo.vote_balance(user_id))
    else:
        note = "❌ Отклонено"
        message = texts.manual_declined()

    try:
        await bot.send_message(user_id, message)
    except TelegramAPIError as error:
        log.info("Не смог сказать %s о решении по заявке: %s", user_id, error)

    await callback.answer(note)
    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n{note}"
        )
    except (TelegramAPIError, AttributeError):
        pass  # подпись не обновилась — решение всё равно записано


def _votes(data: str) -> int | None:
    tail = data.rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() and 0 < int(tail) <= 10_000 else None
