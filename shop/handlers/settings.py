"""Танзимоти дӯкон ва эълони серқадама. Танҳо барои админ."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext

from .. import catalog, keyboards, payments, requisites, texts
from ..config import Config
from ..db import Database
from ..states import Admin
from .admin import IsAdmin
from .common import safe_edit

log = logging.getLogger(__name__)

router = Router(name="settings")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

REVIEW_CHANNEL_KEY = "review_channel"
WHATSAPP_KEY = "whatsapp"
SKIP = ("-", "—", "нет", "не")


# ── экрани танзимот ───────────────────────────────────────────────────
@router.callback_query(F.data == "a:settings")
async def cb_settings(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await safe_edit(
        cb,
        texts.admin_settings(
            len(db.channels()), db.setting(REVIEW_CHANNEL_KEY), db.setting(WHATSAPP_KEY)
        ),
        keyboards.admin_settings(),
    )
    await cb.answer()


# ── корбарон ──────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:users")
async def cb_users(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    rich = db.users_with_money()
    await safe_edit(
        cb,
        texts.admin_users(
            db.stats()["users"], rich, sum(u.balance for u in rich), cfg.currency
        ),
        keyboards.admin_back(),
    )
    await cb.answer()


# ── каналҳои обунаи ҳатмӣ ─────────────────────────────────────────────
@router.callback_query(F.data == "a:channels")
async def cb_channels(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    rows = db.channels()
    await safe_edit(cb, texts.admin_channels(rows), keyboards.admin_channels(rows))
    await cb.answer()


@router.callback_query(F.data == "a:chadd")
async def cb_channel_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_channel)
    await safe_edit(cb, texts.ADMIN_ASK_CHANNEL, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_channel, F.text)
async def got_channel(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    raw = message.text.strip()
    chat_id, _, link = (part.strip() for part in raw.partition("|"))
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or chat.full_name or chat_id
        if not link and chat.username:
            link = f"https://t.me/{chat.username}"
    except Exception as exc:
        await message.answer(
            f"❌ Каналро кушода натавонистам: <code>{texts.esc(exc)}</code>\n\n"
            "Ботро дар канал <b>админ</b> кунед ва аз нав кӯшиш кунед.",
            reply_markup=keyboards.admin_back(),
        )
        return

    await state.clear()
    db.add_channel(chat_id, title, link)
    rows = db.channels()
    await message.answer(
        f"✅ Канал илова шуд: <b>{texts.esc(title)}</b>",
        reply_markup=keyboards.admin_channels(rows),
    )


@router.callback_query(F.data.startswith("a:chdel:"))
async def cb_channel_del(cb: CallbackQuery, db: Database) -> None:
    db.remove_channel(int(cb.data.rsplit(":", 1)[1]))
    rows = db.channels()
    await safe_edit(cb, texts.admin_channels(rows), keyboards.admin_channels(rows))
    await cb.answer("🗑")


# ── канали шарҳҳо ─────────────────────────────────────────────────────
@router.callback_query(F.data == "a:revch")
async def cb_review_channel(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.set_state(Admin.waiting_review_channel)
    current = db.setting(REVIEW_CHANNEL_KEY) or "—"
    await safe_edit(
        cb,
        f"{texts.ADMIN_ASK_REVIEW_CHANNEL}\n\nҲозир: <code>{texts.esc(current)}</code>",
        keyboards.admin_back(),
    )
    await cb.answer()


@router.message(Admin.waiting_review_channel, F.text)
async def got_review_channel(
    message: Message, state: FSMContext, db: Database, bot: Bot
) -> None:
    raw = message.text.strip()
    await state.clear()
    if raw in SKIP:
        db.set_setting(REVIEW_CHANNEL_KEY, "")
        await message.answer("✅ Канали шарҳҳо хомӯш шуд.", reply_markup=keyboards.admin_settings())
        return
    try:
        chat = await bot.get_chat(raw)
        await bot.send_message(raw, "✅ Бот ба ин канал пайваст шуд — шарҳҳо ин ҷо мераванд.")
    except Exception as exc:
        await message.answer(
            f"❌ Ба канал навишта натавонистам: <code>{texts.esc(exc)}</code>\n\n"
            "Ботро дар канал <b>админ</b> кунед.",
            reply_markup=keyboards.admin_back(),
        )
        return
    db.set_setting(REVIEW_CHANNEL_KEY, raw)
    await message.answer(
        f"✅ Шарҳҳо ба <b>{texts.esc(chat.title or raw)}</b> мераванд.",
        reply_markup=keyboards.admin_settings(),
    )


# ── WhatsApp ──────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:wa")
async def cb_whatsapp(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.set_state(Admin.waiting_whatsapp)
    current = db.setting(WHATSAPP_KEY) or "—"
    await safe_edit(
        cb,
        f"{texts.ADMIN_ASK_WHATSAPP}\n\nҲозир: <code>{texts.esc(current)}</code>",
        keyboards.admin_back(),
    )
    await cb.answer()


@router.message(Admin.waiting_whatsapp, F.text)
async def got_whatsapp(message: Message, state: FSMContext, db: Database) -> None:
    raw = message.text.strip()
    await state.clear()
    if raw in SKIP:
        db.set_setting(WHATSAPP_KEY, "")
        await message.answer("✅ WhatsApp бардошта шуд.", reply_markup=keyboards.admin_settings())
        return
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 9:
        await message.answer("❌ Рақам нодуруст аст. Намуна: <code>992939880805</code>")
        return
    db.set_setting(WHATSAPP_KEY, digits)
    await message.answer(
        f"✅ WhatsApp: <code>{digits}</code>\nhttps://wa.me/{digits}",
        reply_markup=keyboards.admin_settings(),
    )


# ── номи зербахшҳо ────────────────────────────────────────────────────
@router.callback_query(F.data == "a:groups")
async def cb_groups(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(cb, "🗂 Бахшро интихоб кунед:", keyboards.admin_group_categories())
    await cb.answer()


@router.callback_query(F.data.startswith("a:gcat:"))
async def cb_group_category(cb: CallbackQuery, db: Database) -> None:
    code = cb.data.rsplit(":", 1)[1]
    rows = db.groups(code, only_active=False)
    await safe_edit(cb, texts.admin_groups(rows), keyboards.admin_groups(rows))
    await cb.answer()


@router.callback_query(F.data.startswith("a:gname:"))
async def cb_group_rename(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    code = cb.data.rsplit(":", 1)[1]
    row = db.group(code)
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    await state.set_state(Admin.waiting_group_title)
    await state.update_data(group_code=code)
    await cb.message.answer(
        f"{texts.ADMIN_ASK_GROUP_TITLE}\n\nҲозир: <b>{texts.esc(row['title'])}</b>",
        reply_markup=keyboards.admin_back(),
    )
    await cb.answer()


@router.message(Admin.waiting_group_title, F.text)
async def got_group_title(message: Message, state: FSMContext, db: Database) -> None:
    title = message.text.strip()
    if not 1 <= len(title) <= 64:
        await message.answer("❌ Ном бояд аз 1 то 64 аломат бошад.")
        return
    data = await state.get_data()
    code = data.get("group_code", "")
    if not db.rename_group(code, title):
        await state.clear()
        await message.answer(texts.UNKNOWN, reply_markup=keyboards.admin_back())
        return
    await state.clear()
    row = db.group(code)
    rows = db.groups(row["category"], only_active=False)
    await message.answer(
        f"✅ Номи нав: <b>{texts.esc(title)}</b>", reply_markup=keyboards.admin_groups(rows)
    )


# ── эълони серқадама ──────────────────────────────────────────────────
# Паёмҳои админ нусхабардорӣ мешаванд, бинобар ин ҲАР навъ кор мекунад:
# овоз, стикер, доира, ҳуҷҷат, видео — ҳама чиз.
def parse_buttons(raw: str) -> list[list[InlineKeyboardButton]] | None:
    """«Ном | ҳавола» дар ҳар сатр → тугмаҳо. None — сатр нодуруст аст."""
    rows: list[list[InlineKeyboardButton]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        title, sep, url = (part.strip() for part in line.partition("|"))
        if not sep or not title or not url.lower().startswith(("http://", "https://", "tg://")):
            return None
        rows.append([InlineKeyboardButton(text=title, url=url)])
    return rows or None


@router.callback_query(F.data == "a:bc")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Admin.waiting_bc_media)
    await safe_edit(cb, texts.ADMIN_BC_STEP1, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_bc_media)
async def bc_step1(message: Message, state: FSMContext) -> None:
    if message.photo or message.video:
        await state.update_data(media_id=message.message_id)
    elif not (message.text and message.text.strip() in SKIP):
        await message.answer(
            "❌ Акс ё видео фиристед, ё нависед <code>-</code>",
            reply_markup=keyboards.admin_back(),
        )
        return
    await state.set_state(Admin.waiting_bc_text)
    await message.answer(texts.ADMIN_BC_STEP2, reply_markup=keyboards.admin_back())


@router.message(Admin.waiting_bc_text)
async def bc_step2(message: Message, state: FSMContext) -> None:
    if not (message.text and message.text.strip() in SKIP):
        await state.update_data(body_id=message.message_id)
    await state.set_state(Admin.waiting_bc_button)
    await message.answer(texts.ADMIN_BC_STEP3, reply_markup=keyboards.admin_back())


@router.message(Admin.waiting_bc_button, F.text)
async def bc_step3(message: Message, state: FSMContext, db: Database) -> None:
    raw = message.text.strip()
    buttons: list[list[InlineKeyboardButton]] | None = None
    if raw not in SKIP:
        buttons = parse_buttons(raw)
        if buttons is None:
            await message.answer(texts.ADMIN_BC_BAD_BUTTON)
            return
        await state.update_data(
            buttons=[[(b.text, b.url) for b in row] for row in buttons]
        )

    data = await state.get_data()
    if not data.get("media_id") and not data.get("body_id"):
        await state.clear()
        await message.answer(texts.ADMIN_BC_EMPTY, reply_markup=keyboards.admin_home())
        return

    await state.update_data(source_chat=message.chat.id)
    await message.answer(
        texts.admin_bc_preview(
            bool(data.get("media_id")),
            bool(data.get("body_id")),
            len(buttons or []),
            len(db.all_user_ids()),
        ),
        reply_markup=keyboards.admin_bc_confirm(),
    )


@router.callback_query(F.data == "a:bcgo")
async def cb_broadcast_send(
    cb: CallbackQuery, state: FSMContext, db: Database, bot: Bot
) -> None:
    data = await state.get_data()
    await state.clear()
    media_id = data.get("media_id")
    body_id = data.get("body_id")
    source = data.get("source_chat", cb.from_user.id)
    saved = data.get("buttons") or []
    markup = (
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=title, url=url) for title, url in row]
                for row in saved
            ]
        )
        if saved
        else None
    )

    await safe_edit(cb, "📤 Мефиристам...", None)
    await cb.answer()

    sent = failed = 0
    for user_id in db.all_user_ids():
        try:
            if media_id:
                # Тугмаҳо ба паёми охирин мечаспанд.
                await bot.copy_message(
                    user_id, source, media_id,
                    reply_markup=None if body_id else markup,
                )
            if body_id:
                await bot.copy_message(user_id, source, body_id, reply_markup=markup)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)   # то ба маҳдудияти Telegram нарасем

    await cb.message.answer(
        texts.broadcast_result(sent, failed), reply_markup=keyboards.admin_home()
    )


# ── реквизитҳои пардохт ───────────────────────────────────────────────
async def _show_requisites(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    req = requisites.get(db, cfg)
    await safe_edit(cb, texts.admin_requisites(req), keyboards.admin_requisites(req))


@router.callback_query(F.data == "a:req")
async def cb_requisites(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    await _show_requisites(cb, db, cfg)
    await cb.answer()


@router.callback_query(F.data == "a:card")
async def cb_card(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_card)
    await safe_edit(cb, texts.ADMIN_ASK_CARD, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_card, F.text)
async def got_card(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    digits = payments.card_digits(message.text)
    if not 12 <= len(digits) <= 19:
        await message.answer(
            "❌ Рақами корт нодуруст аст — аз 12 то 19 рақам бошад.",
            reply_markup=keyboards.admin_back(),
        )
        return
    await state.clear()
    db.set_setting(requisites.CARD_KEY, digits)
    req = requisites.get(db, cfg)
    await message.answer(
        f"✅ Корт: <code>{payments.format_card(digits)}</code>",
        reply_markup=keyboards.admin_requisites(req),
    )


@router.callback_query(F.data == "a:holder")
async def cb_holder(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_holder)
    await safe_edit(cb, texts.ADMIN_ASK_HOLDER, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_holder, F.text)
async def got_holder(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 64:
        await message.answer("❌ Ном бояд аз 2 то 64 аломат бошад.")
        return
    await state.clear()
    db.set_setting(requisites.HOLDER_KEY, name)
    req = requisites.get(db, cfg)
    await message.answer(
        f"✅ Номи соҳиби корт: <b>{texts.esc(name)}</b>",
        reply_markup=keyboards.admin_requisites(req),
    )


@router.callback_query(F.data == "a:alif")
async def cb_alif(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_alif)
    await safe_edit(cb, texts.ADMIN_ASK_ALIF, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_alif, F.text)
async def got_alif(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    digits = "".join(ch for ch in message.text if ch.isdigit())
    if not 6 <= len(digits) <= 15:
        await message.answer(
            "❌ Рақами ҳисоб нодуруст аст. Намуна: <code>939880805</code>",
            reply_markup=keyboards.admin_back(),
        )
        return
    await state.clear()
    db.set_setting(requisites.ALIF_KEY, digits)
    req = requisites.get(db, cfg)
    await message.answer(
        f"✅ Ҳисоби Alif: <code>{digits}</code>",
        reply_markup=keyboards.admin_requisites(req),
    )


@router.callback_query(F.data.in_({"a:dctoggle", "a:aliftoggle"}))
async def cb_toggle_method(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    """Охирин тарзи пардохтро хомӯш кардан мумкин нест."""
    req = requisites.get(db, cfg)
    is_dc = cb.data == "a:dctoggle"
    turning_off = req.dc_enabled if is_dc else req.alif_enabled
    other_on = req.alif_enabled if is_dc else req.dc_enabled

    if turning_off and not other_on:
        await cb.answer(texts.ADMIN_LAST_METHOD.replace("<b>", "").replace("</b>", ""),
                        show_alert=True)
        return

    key = requisites.DC_ON_KEY if is_dc else requisites.ALIF_ON_KEY
    db.set_setting(key, "0" if turning_off else "1")
    await _show_requisites(cb, db, cfg)
    await cb.answer("🚫 Хомӯш шуд" if turning_off else "✅ Фаъол шуд")
