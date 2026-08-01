from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    after_calc_kb, cancel_kb, categories_kb, delivery_types_kb, main_menu,
)
from bot.models import Category, DeliveryType, User
from bot.repositories import Repository
from bot.services import CalculatorService
from bot.states import CalcStates
from bot.texts import t
from bot.utils import parse_number, render_calc_result

router = Router()


@router.message(F.text == t("btn_calc"))
async def calc_start(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    items = await Repository(session, DeliveryType).list(
        is_active=True, order_by=[DeliveryType.sort_order]
    )
    if not items:
        await message.answer(t("calc_no_tariff"))
        return
    await state.set_state(CalcStates.delivery_type)
    await message.answer(t("calc_delivery_type"), reply_markup=delivery_types_kb(items))


@router.callback_query(CalcStates.delivery_type, F.data.startswith("calc:dt:"))
async def calc_delivery_type(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.update_data(delivery_type_id=int(cb.data.split(":")[2]))
    items = await Repository(session, Category).list(
        is_active=True, order_by=[Category.sort_order]
    )
    await state.set_state(CalcStates.category)
    await cb.message.edit_text(t("calc_category"), reply_markup=categories_kb(items))
    await cb.answer()


@router.callback_query(CalcStates.category, F.data.startswith("calc:cat:"))
async def calc_category(cb: CallbackQuery, state: FSMContext):
    await state.update_data(category_id=int(cb.data.split(":")[2]))
    await state.set_state(CalcStates.weight)
    await cb.message.edit_text(t("calc_weight"))
    await cb.answer()


@router.message(CalcStates.weight)
async def calc_weight(message: Message, state: FSMContext):
    value = parse_number(message.text or "")
    if value is None or value <= 0:
        await message.answer(t("calc_bad_number"))
        return
    await state.update_data(weight=value)
    await state.set_state(CalcStates.volume)
    await message.answer(t("calc_volume"), reply_markup=cancel_kb())


@router.message(CalcStates.volume)
async def calc_volume(message: Message, state: FSMContext,
                      session: AsyncSession, db_user: User):
    value = parse_number(message.text or "")
    if value is None:
        await message.answer(t("calc_bad_number"))
        return
    data = await state.get_data()
    await state.clear()

    result = await CalculatorService(session).calculate(
        delivery_type_id=data["delivery_type_id"],
        category_id=data["category_id"],
        weight=data["weight"],
        volume=value,
        user_id=db_user.id,
    )
    if not result:
        await message.answer(t("calc_no_tariff"), reply_markup=main_menu())
        return

    # запоминаем данные расчёта для предзаполнения заявки
    await state.update_data(
        prefill_weight=data["weight"], prefill_volume=value,
        prefill_calc=f"{result.delivery_type}, {result.category.name if result.category else ''}",
    )
    await message.answer(render_calc_result(result), reply_markup=main_menu())
    await message.answer("Оформить заявку на эту доставку?", reply_markup=after_calc_kb())
