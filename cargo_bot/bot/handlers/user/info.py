"""Информационные разделы: тарифы, склады, контакты, FAQ.

Весь контент берётся из БД и редактируется через админ-панель.
"""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import faq_kb
from bot.models import Contact, DeliveryType, Faq, Tariff, Warehouse
from bot.repositories import Repository
from bot.texts import t
from bot.utils import fmt_num

router = Router()


@router.message(F.text == t("btn_tariffs"))
async def show_tariffs(message: Message, session: AsyncSession):
    tariffs = (await session.scalars(
        select(Tariff).where(Tariff.is_active.is_(True)).order_by(Tariff.delivery_type_id)
    )).all()
    if not tariffs:
        await message.answer(t("no_data"))
        return
    dts = {d.id: d for d in await Repository(session, DeliveryType).list()}
    lines, current_dt = ["💰 <b>Актуальные тарифы</b>"], None
    for tr in tariffs:
        if tr.delivery_type_id != current_dt:
            current_dt = tr.delivery_type_id
            lines.append(f"\n<b>{dts.get(current_dt, '')}</b>")
        min_info = []
        if tr.min_weight:
            min_info.append(f"от {fmt_num(tr.min_weight)} кг")
        if tr.min_order_cost:
            min_info.append(f"мин. {fmt_num(tr.min_order_cost)} {tr.currency_code}")
        suffix = f" ({', '.join(min_info)})" if min_info else ""
        time_ = f" — {tr.delivery_time}" if tr.delivery_time else ""
        lines.append(f"• {tr.name}: <b>{fmt_num(tr.price_per_kg)} "
                     f"{tr.currency_code}/кг</b>{suffix}{time_}")
    await message.answer("\n".join(lines))


@router.message(F.text == t("btn_warehouses"))
async def show_warehouses(message: Message, session: AsyncSession):
    items = await Repository(session, Warehouse).list(
        is_active=True, order_by=[Warehouse.sort_order]
    )
    if not items:
        await message.answer(t("no_data"))
        return
    lines = ["📍 <b>Адреса складов</b>"]
    for w in items:
        lines.append(f"\n<b>{w.name}</b>\n{w.address}")
        if w.note:
            lines.append(f"ℹ️ {w.note}")
    await message.answer("\n".join(lines))


@router.message(F.text == t("btn_contacts"))
async def show_contacts(message: Message, session: AsyncSession):
    items = await Repository(session, Contact).list(
        is_active=True, order_by=[Contact.sort_order]
    )
    if not items:
        await message.answer(t("no_data"))
        return
    lines = ["☎ <b>Контакты</b>", ""]
    lines += [f"• <b>{c.title}:</b> {c.value}" for c in items]
    await message.answer("\n".join(lines))


@router.message(F.text == t("btn_faq"))
async def show_faq(message: Message, session: AsyncSession):
    items = await Repository(session, Faq).list(is_active=True, order_by=[Faq.sort_order])
    if not items:
        await message.answer(t("no_data"))
        return
    await message.answer(t("faq_title"), reply_markup=faq_kb(items))


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(cb: CallbackQuery, session: AsyncSession):
    faq = await Repository(session, Faq).get(int(cb.data.split(":")[1]))
    await cb.answer()
    if faq:
        await cb.message.answer(f"❓ <b>{faq.question}</b>\n\n{faq.answer}")
