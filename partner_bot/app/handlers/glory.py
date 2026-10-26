"""Боты для гильдии (Glory клана FF): регион → ID клана → оплата → «живое» сообщение с цифрами.

Вся работа — в app/services/glory. Раздел виден, только когда бот подключён к
Donatix и Donatix сейчас продаёт Glory.
"""
from __future__ import annotations

import aiosqlite
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import db
from app.money import fmt
from app.services import glory

router = Router(name="glory")


class GloryForm(StatesGroup):
    clan = State()      # ждём ID клана


def _kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row]
                                                 for row in rows])


async def _screen(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except (TelegramAPIError, AttributeError):
        await call.bot.send_message(call.from_user.id, text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "gl:home")
async def home(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    items = await glory.regions()
    if not items:
        await _screen(call, "🛡 <b>Glory барои клан</b>\n\nХизмат ҳоло дастрас нест. Баъдтар боз кӯшиш кунед.",
                      _kb([("🏠 Меню", "m:main")]))
        await call.answer()
        return
    rows = []
    for r in items:
        price, _ = glory.price_of(r)
        if price > 0:
            rows.append([(f"{glory.flag(r.get('code'))} {r.get('name')} — {fmt(price)}", f"gl:r:{r['id']}")])
    rows += [[("📋 Фармоишҳои ман", "gl:my")], [("🏠 Меню", "m:main")]]
    await _screen(call, "🛡 <b>Glory барои клан</b>\n\n"
                        "Гурӯҳи ботҳо ба бозӣ ворид шуда, барои клани шумо glory ҷамъ мекунад. "
                        "Рақамҳо дар як паём худ ба худ нав мешаванд.\n\n"
                        "• Барои як клан — як гурӯҳ дар як вақт.\n"
                        "• Агар оғоз нашавад — пул худ ба худ бармегардад.\n"
                        "• Баъди оғоз пул баргардонида намешавад, танҳо қатъ кардан мумкин аст.\n\n"
                        "Минтақаи серверро интихоб кунед:", _kb(*rows))
    await call.answer()


@router.callback_query(F.data.startswith("gl:r:"))
async def pick_region(call: CallbackQuery, state: FSMContext) -> None:
    region = call.data.split(":", 2)[2]
    await state.set_state(GloryForm.clan)
    await state.update_data(region=region)
    await _screen(call, "🛡 <b>ID-и кланро нависед</b>\n\nТанҳо рақамҳо, масалан: <code>3012345678</code>",
                  _kb([("✖️ Бекор", "gl:home")]))
    await call.answer()


@router.message(GloryForm.clan, F.text)
async def got_clan(message: Message, state: FSMContext) -> None:
    clan = (message.text or "").strip().replace(" ", "")
    if not glory.CLAN_RE.match(clan):
        await message.answer("ID-и клан нодуруст аст. Танҳо рақамҳо, масалан <code>3012345678</code>.",
                             parse_mode="HTML", reply_markup=_kb([("✖️ Бекор", "gl:home")]))
        return
    data = await state.get_data()
    region = next((r for r in await glory.regions() if r.get("id") == data.get("region")), None)
    if region is None:
        await state.clear()
        await message.answer("Минтақаро аз нав интихоб кунед.", reply_markup=_kb([("🛡 Glory", "gl:home")]))
        return
    price, _ = glory.price_of(region)
    await state.update_data(clan=clan)
    await message.answer(f"🛡 <b>Тасдиқ кунед</b>\n\nКлан: <code>{clan}</code>\n"
                         f"Минтақа: {glory.flag(region.get('code'))} {region.get('name')}\n"
                         f"Нарх: <b>{fmt(price)}</b>\n\nБаъди оғоз пул баргардонида намешавад.",
                         parse_mode="HTML", reply_markup=_kb([("✅ Оғоз кардан", "gl:go")], [("✖️ Бекор", "gl:home")]))


@router.callback_query(F.data == "gl:go")
async def go(call: CallbackQuery, state: FSMContext, conn: aiosqlite.Connection, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    if not data.get("clan") or not data.get("region"):
        await call.answer("Аз нав оғоз кунед.", show_alert=True)
        return
    await call.answer("Оғоз мешавад…")
    try:
        gid = await glory.launch(bot, conn, call.from_user.id, data["region"], data["clan"])
    except glory.GloryFail as exc:
        await _screen(call, f"❌ {exc}", _kb([("🛡 Glory", "gl:home")], [("🏠 Меню", "m:main")]))
        return
    g = await glory.get(conn, gid)
    await glory.show(bot, conn, g, chat_id=call.from_user.id, message_id=call.message.message_id)


@router.callback_query(F.data.startswith("gl:u:") | F.data.startswith("gl:o:"))
async def update(call: CallbackQuery, conn: aiosqlite.Connection, bot: Bot) -> None:
    gid = call.data.split(":")[2]
    g = await glory.get(conn, int(gid), call.from_user.id) if gid.isdigit() else None
    if g is None:
        await call.answer("Фармоиш ёфт нашуд.", show_alert=True)
        return
    await glory.show(bot, conn, g, chat_id=call.from_user.id, message_id=call.message.message_id)
    await call.answer("Нав шуд")


@router.callback_query(F.data.startswith("gl:s:"))
async def ask_stop(call: CallbackQuery) -> None:
    gid = call.data.split(":")[2]
    await _screen(call, "⏹ <b>Гурӯҳро қатъ кунем?</b>\n\nПул баргардонида намешавад.",
                  _kb([("⏹ Ҳа, қатъ кун", f"gl:sy:{gid}")], [("↩️ Не", f"gl:u:{gid}")]))
    await call.answer()


@router.callback_query(F.data.startswith("gl:sy:"))
async def do_stop(call: CallbackQuery, conn: aiosqlite.Connection, bot: Bot) -> None:
    gid = call.data.split(":")[2]
    g = await glory.get(conn, int(gid), call.from_user.id) if gid.isdigit() else None
    if g is None:
        await call.answer("Фармоиш ёфт нашуд.", show_alert=True)
        return
    ok = await glory.stop(conn, g)
    await glory.show(bot, conn, await glory.get(conn, g["id"]), chat_id=call.from_user.id,
                     message_id=call.message.message_id)
    await call.answer("Қатъ шуд" if ok else "Ҳоло қатъ нашуд — баъдтар боз кӯшиш кунед.", show_alert=not ok)


@router.callback_query(F.data == "gl:my")
async def my(call: CallbackQuery, conn: aiosqlite.Connection) -> None:
    rows = await glory.mine(conn, call.from_user.id)
    if not rows:
        await _screen(call, "📋 Шумо ҳоло фармоиши Glory надоред.", _kb([("🛡 Glory", "gl:home")]))
        await call.answer()
        return
    buttons = [[(f"{glory.STATUS.get(g['status'], g['status'])} · клан {g['clan_id']}", f"gl:o:{g['id']}")]
               for g in rows]
    await _screen(call, "📋 <b>Фармоишҳои Glory</b>", _kb(*buttons, [("🛡 Glory", "gl:home")]))
    await call.answer()
