from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import cancel_kb, main_menu
from bot.models import Order, User
from bot.repositories import Repository
from bot.services import log_action, notify_admins, snapshot
from bot.states import OrderStates
from bot.texts import t
from bot.utils import fmt_num, parse_number

router = Router()


def _skip(text: str) -> str | None:
    text = (text or "").strip()
    return None if text in {"-", "—", ""} else text


async def _begin(state: FSMContext, target: Message):
    await state.set_state(OrderStates.name)
    await target.answer(t("order_name"), reply_markup=cancel_kb())


@router.message(F.text == t("btn_order"))
async def order_start(message: Message, state: FSMContext):
    await state.set_data({})
    await _begin(state, message)


@router.callback_query(F.data == "order:start")
async def order_from_calc(cb: CallbackQuery, state: FSMContext):
    # данные расчёта (prefill_*) уже лежат в state
    await cb.answer()
    await _begin(state, cb.message)


@router.message(OrderStates.name)
async def order_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(OrderStates.phone)
    await message.answer(t("order_phone"))


@router.message(OrderStates.phone)
async def order_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await state.set_state(OrderStates.product_url)
    await message.answer(t("order_url"))


@router.message(OrderStates.product_url)
async def order_url(message: Message, state: FSMContext):
    await state.update_data(product_url=_skip(message.text))
    await state.set_state(OrderStates.description)
    await message.answer(t("order_description"))


@router.message(OrderStates.description)
async def order_description(message: Message, state: FSMContext):
    await state.update_data(description=_skip(message.text))
    data = await state.get_data()
    if data.get("prefill_weight") is not None:
        await state.update_data(weight=data["prefill_weight"],
                                volume=data.get("prefill_volume"))
        await state.set_state(OrderStates.comment)
        await message.answer(t("order_comment"))
    else:
        await state.set_state(OrderStates.weight)
        await message.answer(t("order_weight"))


@router.message(OrderStates.weight)
async def order_weight(message: Message, state: FSMContext):
    raw = _skip(message.text)
    weight = parse_number(raw) if raw else None
    if raw and weight is None:
        await message.answer(t("calc_bad_number"))
        return
    await state.update_data(weight=weight)
    await state.set_state(OrderStates.volume)
    await message.answer(t("order_volume"))


@router.message(OrderStates.volume)
async def order_volume(message: Message, state: FSMContext):
    raw = _skip(message.text)
    volume = parse_number(raw) if raw else None
    if raw and volume is None:
        await message.answer(t("calc_bad_number"))
        return
    await state.update_data(volume=volume)
    await state.set_state(OrderStates.comment)
    await message.answer(t("order_comment"))


@router.message(OrderStates.comment)
async def order_comment(message: Message, state: FSMContext, bot: Bot,
                        session: AsyncSession, db_user: User):
    data = await state.get_data()
    await state.clear()

    comment = _skip(message.text)
    if data.get("prefill_calc"):
        comment = f"{comment or ''}\n[Расчёт: {data['prefill_calc']}]".strip()

    repo = Repository(session, Order)
    order = await repo.add(
        number="TMP", user_id=db_user.id,
        name=data["name"], phone=data["phone"],
        product_url=data.get("product_url"), description=data.get("description"),
        weight=data.get("weight"), volume=data.get("volume"),
        comment=comment, status="Новая",
    )
    order = await repo.update(order, number=f"ORD-{order.id:05d}")
    await log_action(session, db_user.tg_id, "create", "orders", order.id,
                     new=snapshot(order))

    await message.answer(t("order_done", number=order.number), reply_markup=main_menu())

    await notify_admins(bot, session, (
        f"🆕 <b>Новая заявка {order.number}</b>\n"
        f"👤 {order.name}\n📱 {order.phone}\n"
        f"🔗 {order.product_url or '-'}\n"
        f"📄 {order.description or '-'}\n"
        f"⚖️ {fmt_num(order.weight) + ' кг' if order.weight is not None else '-'} | "
        f"📐 {fmt_num(order.volume) + ' м³' if order.volume is not None else '-'}\n"
        f"💬 {order.comment or '-'}\n"
        f"От: @{db_user.username or '-'} (id {db_user.tg_id})"
    ))
