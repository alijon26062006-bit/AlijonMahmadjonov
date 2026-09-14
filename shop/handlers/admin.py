"""Панели админ: омор, корбарон, фармоишҳо, пардохтҳо, нархҳо, эълон."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from .. import catalog, keyboards, texts
from ..config import Config
from ..db import (
    Database,
    NotEnoughMoney,
    ORDER_DONE,
    ORDER_REJECTED,
)
from ..states import Admin
from .common import notify_user, safe_edit

log = logging.getLogger(__name__)


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, cfg: Config) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and cfg.is_admin(user.id))


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ── вуруд ─────────────────────────────────────────────────────────────
@router.message(Command("admin", "panel"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ADMIN_HOME, reply_markup=keyboards.admin_home())


@router.callback_query(F.data == "a:home")
async def cb_home(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(cb, texts.ADMIN_HOME, keyboards.admin_home())
    await cb.answer()


@router.callback_query(F.data == "a:stats")
async def cb_stats(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    await safe_edit(cb, texts.admin_stats(db.stats(), cfg.currency), keyboards.admin_back())
    await cb.answer()


# ── корбарон ──────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:find")
async def cb_find(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_user)
    await safe_edit(cb, texts.ADMIN_ASK_USER, keyboards.admin_back())
    await cb.answer()


async def _send_user_card(message: Message, user, db: Database, cfg: Config) -> None:
    await message.answer(
        texts.admin_user_card(
            user, db.user_orders(user.id, 5), db.user_topups(user.id, 5), cfg.currency,
            partner=db.is_partner(user.id),
        ),
        reply_markup=keyboards.admin_user(user),
    )


@router.message(Admin.waiting_user, F.text)
async def got_user_query(
    message: Message, state: FSMContext, db: Database, cfg: Config
) -> None:
    found = db.find_user(message.text)
    if found is None:
        await message.answer(texts.ADMIN_USER_NOT_FOUND, reply_markup=keyboards.admin_back())
        return
    await state.clear()
    await _send_user_card(message, found, db, cfg)


@router.callback_query(F.data.startswith("a:plus:"))
async def cb_plus(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = int(cb.data.rsplit(":", 1)[1])
    await state.set_state(Admin.waiting_plus)
    await state.update_data(target_id=user_id)
    await cb.message.answer(texts.ADMIN_ASK_SUM_PLUS, reply_markup=keyboards.admin_back())
    await cb.answer()


@router.callback_query(F.data.startswith("a:minus:"))
async def cb_minus(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = int(cb.data.rsplit(":", 1)[1])
    await state.set_state(Admin.waiting_minus)
    await state.update_data(target_id=user_id)
    await cb.message.answer(texts.ADMIN_ASK_SUM_MINUS, reply_markup=keyboards.admin_back())
    await cb.answer()


async def _apply_delta(
    message: Message,
    state: FSMContext,
    db: Database,
    cfg: Config,
    bot: Bot,
    sign: int,
) -> None:
    amount = texts.to_diram(message.text)
    if amount is None:
        await message.answer(texts.bad_amount(1, cfg.max_topup, cfg.currency))
        return
    data = await state.get_data()
    user_id = data.get("target_id")
    if not user_id:
        await state.clear()
        await message.answer(texts.ADMIN_USER_NOT_FOUND)
        return
    try:
        db.change_balance(
            user_id, sign * amount, "admin", admin_id=message.from_user.id
        )
    except NotEnoughMoney:
        await message.answer("❌ Дар ҳисоби корбар ин қадар маблағ нест.")
        return
    await state.clear()
    fresh = db.user(user_id)
    await message.answer(texts.admin_balance_changed(fresh, sign * amount, cfg.currency))
    note = (
        texts.user_balance_added(amount, fresh.balance, cfg.currency)
        if sign > 0
        else texts.user_balance_removed(amount, fresh.balance, cfg.currency)
    )
    await notify_user(bot, user_id, note)
    await _send_user_card(message, fresh, db, cfg)


@router.message(Admin.waiting_plus, F.text)
async def got_plus(
    message: Message, state: FSMContext, db: Database, cfg: Config, bot: Bot
) -> None:
    await _apply_delta(message, state, db, cfg, bot, +1)


@router.message(Admin.waiting_minus, F.text)
async def got_minus(
    message: Message, state: FSMContext, db: Database, cfg: Config, bot: Bot
) -> None:
    await _apply_delta(message, state, db, cfg, bot, -1)


@router.callback_query(F.data.startswith("a:block:") | F.data.startswith("a:unblock:"))
async def cb_block(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    action, raw_id = cb.data.split(":")[1], cb.data.rsplit(":", 1)[1]
    user_id = int(raw_id)
    db.set_blocked(user_id, action == "block")
    fresh = db.user(user_id)
    if fresh is None:
        await cb.answer(texts.ADMIN_USER_NOT_FOUND, show_alert=True)
        return
    await safe_edit(
        cb,
        texts.admin_user_card(
            fresh, db.user_orders(user_id, 5), db.user_topups(user_id, 5), cfg.currency,
            partner=db.is_partner(user_id),
        ),
        keyboards.admin_user(fresh),
    )
    await cb.answer("🚫 Маҳдуд шуд" if action == "block" else "✅ Кушода шуд")


# ── фармоишҳо ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:orders")
async def cb_orders(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    rows = db.open_orders(10)
    if not rows:
        await safe_edit(cb, texts.ADMIN_NO_ORDERS, keyboards.admin_back())
        await cb.answer()
        return
    await safe_edit(cb, f"🧾 Фармоишҳои кушода: <b>{len(rows)}</b>", keyboards.admin_back())
    for row in rows:
        await cb.message.answer(
            texts.admin_order_card(row, db.user(row["user_id"]), cfg.currency),
            reply_markup=keyboards.admin_order(row["id"]),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("a:odone:") | F.data.startswith("a:orej:"))
async def cb_order_action(cb: CallbackQuery, db: Database, cfg: Config, bot: Bot) -> None:
    action = cb.data.split(":")[1]
    order_id = int(cb.data.rsplit(":", 1)[1])
    status = ORDER_DONE if action == "odone" else ORDER_REJECTED
    row = db.set_order_status(order_id, status)
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    await safe_edit(
        cb,
        texts.admin_order_card(row, db.user(row["user_id"]), cfg.currency),
        keyboards.admin_back(),
    )
    note = (
        texts.order_done_note(order_id, row["title"], row["target"] or "")
        if status == ORDER_DONE
        else texts.order_rejected_note(order_id, row["price"], cfg.currency)
    )
    await notify_user(bot, row["user_id"], note)
    await cb.answer("✅" if status == ORDER_DONE else "❌")


# ── пардохтҳо ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:topups")
async def cb_topups(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    rows = db.open_topups(10)
    if not rows:
        await safe_edit(cb, texts.ADMIN_NO_TOPUPS, keyboards.admin_back())
        await cb.answer()
        return
    await safe_edit(cb, f"💳 Пардохтҳои интизорӣ: <b>{len(rows)}</b>", keyboards.admin_back())
    for row in rows:
        await cb.message.answer(
            texts.admin_topup_card(row, db.user(row["user_id"]), cfg.currency),
            reply_markup=keyboards.admin_topup(row["id"]),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("a:tok:") | F.data.startswith("a:trej:"))
async def cb_topup_action(cb: CallbackQuery, db: Database, cfg: Config, bot: Bot) -> None:
    action = cb.data.split(":")[1]
    topup_id = int(cb.data.rsplit(":", 1)[1])
    if action == "tok":
        row = db.confirm_topup(topup_id, cb.from_user.id)
    else:
        row = db.reject_topup(topup_id, cb.from_user.id)
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    user = db.user(row["user_id"])
    await safe_edit(cb, texts.admin_topup_card(row, user, cfg.currency), keyboards.admin_back())
    if action == "tok" and user:
        await notify_user(
            bot,
            user.id,
            texts.topup_confirmed(row["amount"], user.balance, cfg.currency),
        )
    elif action == "trej":
        await notify_user(bot, row["user_id"], texts.topup_rejected(topup_id))
    await cb.answer("✅" if action == "tok" else "❌")


# ── нархҳо ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:prices")
async def cb_prices(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit(cb, "💲 Бахшро интихоб кунед:", keyboards.admin_price_categories())
    await cb.answer()


@router.callback_query(F.data.startswith("a:pcat:"))
async def cb_price_category(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    code = cb.data.rsplit(":", 1)[1]
    info = catalog.CATEGORY_INFO.get(code)
    if info is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    rows = db.products(code, only_active=False)
    await safe_edit(
        cb,
        texts.admin_prices(rows, info.title, cfg.currency),
        keyboards.admin_price_list(rows, currency=cfg.currency),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("a:price:"))
async def cb_price_item(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    code = cb.data.rsplit(":", 1)[1]
    row = db.product(code)
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    status = "✅ фаъол" if row["active"] else "🚫 хомӯш"
    partner_price = row["partner_price"]
    partner_line = (
        f"🤝 Нархи шарикӣ: <b>{texts.money(partner_price, cfg.currency)}</b>"
        if partner_price
        else "🤝 Нархи шарикӣ: <i>гузошта нашудааст</i> (шарик нархи оддиро медиҳад)"
    )
    await safe_edit(
        cb,
        f"📦 <b>{texts.esc(row['title'])}</b>\n\n"
        f"💰 Нархи оддӣ: <b>{texts.money(row['price'], cfg.currency)}</b>\n"
        f"{partner_line}\n"
        f"📶 Ҳолат: {status}\n"
        f"🔖 Код: <code>{texts.esc(code)}</code>",
        keyboards.admin_price_item(code, bool(row["active"]), bool(partner_price)),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("a:toggle:"))
async def cb_toggle(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    code = cb.data.rsplit(":", 1)[1]
    row = db.product(code)
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    db.set_active(code, not row["active"])
    await cb_price_item(cb, db, cfg)


@router.callback_query(F.data.startswith("a:setprice:"))
async def cb_set_price(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.rsplit(":", 1)[1]
    await state.set_state(Admin.waiting_price)
    await state.update_data(price_code=code)
    await cb.message.answer(texts.ADMIN_ASK_PRICE, reply_markup=keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_price, F.text)
async def got_price(message: Message, state: FSMContext, db: Database, cfg: Config) -> None:
    price = texts.to_diram(message.text)
    if price is None:
        await message.answer(texts.ADMIN_ASK_PRICE)
        return
    data = await state.get_data()
    code = data.get("price_code", "")
    if not db.set_price(code, price):
        await state.clear()
        await message.answer(texts.UNKNOWN, reply_markup=keyboards.admin_back())
        return
    await state.clear()
    row = db.product(code)
    await message.answer(
        f"✅ Нархи оддии <b>{texts.esc(row['title'])}</b> акнун "
        f"<b>{texts.money(price, cfg.currency)}</b>",
        reply_markup=keyboards.admin_price_item(
            code, bool(row["active"]), bool(row["partner_price"])
        ),
    )


# ── шарикон ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:partners")
async def cb_partners(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    rows = db.partners()
    await safe_edit(
        cb, texts.admin_partners(rows, cfg.currency), keyboards.admin_partners(rows)
    )
    await cb.answer()


@router.callback_query(F.data == "a:padd")
async def cb_partner_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_partner)
    await safe_edit(cb, texts.ADMIN_ASK_PARTNER, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_partner, F.text)
async def got_partner(
    message: Message, state: FSMContext, db: Database, cfg: Config, bot: Bot
) -> None:
    found = db.find_user(message.text)
    if found is None:
        await message.answer(
            texts.ADMIN_USER_NOT_FOUND
            + "\n\n<i>Шояд ӯ ҳанӯз ботро накушодааст. Бигӯед, ки /start-ро пахш кунад.</i>",
            reply_markup=keyboards.admin_back(),
        )
        return
    await state.clear()
    db.add_partner(found.id, admin_id=message.from_user.id)
    await message.answer(texts.partner_added(found))
    await notify_user(bot, found.id, texts.PARTNER_WELCOME)
    rows = db.partners()
    await message.answer(
        texts.admin_partners(rows, cfg.currency), reply_markup=keyboards.admin_partners(rows)
    )


@router.callback_query(F.data.startswith("a:pdel:"))
async def cb_partner_remove(
    cb: CallbackQuery, db: Database, cfg: Config, bot: Bot
) -> None:
    user_id = int(cb.data.rsplit(":", 1)[1])
    if db.remove_partner(user_id):
        await notify_user(bot, user_id, texts.PARTNER_REMOVED)
    rows = db.partners()
    await safe_edit(
        cb, texts.admin_partners(rows, cfg.currency), keyboards.admin_partners(rows)
    )
    await cb.answer("🗑 Бекор шуд")


@router.callback_query(F.data.startswith("a:setpp:"))
async def cb_set_partner_price(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.rsplit(":", 1)[1]
    await state.set_state(Admin.waiting_partner_price)
    await state.update_data(price_code=code)
    await cb.message.answer(texts.ADMIN_ASK_PARTNER_PRICE, reply_markup=keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_partner_price, F.text)
async def got_partner_price(
    message: Message, state: FSMContext, db: Database, cfg: Config
) -> None:
    raw = message.text.strip().replace(",", ".")
    price = None if raw in ("0", "0.0", "0.00") else texts.to_diram(raw)
    if price is None and raw not in ("0", "0.0", "0.00"):
        await message.answer(texts.ADMIN_ASK_PARTNER_PRICE)
        return
    data = await state.get_data()
    code = data.get("price_code", "")
    row = db.product(code)
    if row is None:
        await state.clear()
        await message.answer(texts.UNKNOWN, reply_markup=keyboards.admin_back())
        return
    if price is not None and price >= row["price"]:
        await message.answer(
            "⚠️ Нархи шарикӣ аз нархи оддӣ "
            f"({texts.money(row['price'], cfg.currency)}) кам бошад.\n"
            "Рақами дигар нависед."
        )
        return

    db.set_partner_price(code, price)
    await state.clear()
    row = db.product(code)
    note = (
        f"акнун <b>{texts.money(price, cfg.currency)}</b>"
        if price
        else "бардошта шуд — шарик нархи оддиро медиҳад"
    )
    await message.answer(
        f"✅ Нархи шарикии <b>{texts.esc(row['title'])}</b> {note}",
        reply_markup=keyboards.admin_price_item(
            code, bool(row["active"]), bool(row["partner_price"])
        ),
    )


@router.callback_query(F.data.startswith("a:delpp:"))
async def cb_del_partner_price(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    code = cb.data.rsplit(":", 1)[1]
    db.set_partner_price(code, None)
    await cb_price_item(cb, db, cfg)


# ── эълон ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "a:bc")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Admin.waiting_broadcast)
    await safe_edit(cb, texts.ADMIN_ASK_BROADCAST, keyboards.admin_back())
    await cb.answer()


@router.message(Admin.waiting_broadcast, F.text)
async def got_broadcast(message: Message, state: FSMContext, db: Database, bot: Bot) -> None:
    await state.clear()
    text = message.html_text
    sent = failed = 0
    for user_id in db.all_user_ids():
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # то ба маҳдудияти Telegram нарасем
    await message.answer(
        texts.broadcast_result(sent, failed), reply_markup=keyboards.admin_home()
    )


# ── таъминкунанда (FireLoot) ──────────────────────────────────────────
@router.message(Command("balance", "hisob"))
async def cmd_supplier_balance(message: Message, cfg: Config, supplier) -> None:
    """Баланси таъминкунанда — то донем, ки барои чанд фармоиш пул ҳаст."""
    if not cfg.has_supplier:
        await message.answer(
            "ℹ️ Таъминкунанда хомӯш аст (реҷаи дастӣ).\n"
            "Барои фаъол кардан дар <code>.env</code>: "
            "<code>SHOP_SUPPLIER=fireloot</code> ва калиди API."
        )
        return
    waiting = await message.answer("⏳ Дар ҳоли пурсиши баланс...")
    data = await supplier.balance()
    if not data.get("ok"):
        await waiting.edit_text(f"❌ Хатогӣ: <code>{texts.esc(data.get('error'))}</code>")
        return
    stars = data.get("stars_balance")
    lines = [
        "💰 <b>Баланси таъминкунанда</b>\n",
        f"💵 Асосӣ: <b>{texts.esc(data.get('balance'))} {texts.esc(data.get('currency'))}</b>",
    ]
    if stars is not None:
        lines.append(f"⭐️ Stars: <b>{texts.esc(stars)}</b>")
    if data.get("telegram_active") is not None:
        lines.append(
            "📶 Telegram Stars: "
            + ("✅ фаъол" if data.get("telegram_active") else "🚫 хомӯш")
        )
    await waiting.edit_text("\n".join(lines))


@router.message(Command("sku"))
async def cmd_check_sku(message: Message, db: Database, cfg: Config, supplier) -> None:
    """Санҷиши SKU-ҳо бо каталоги воқеии таъминкунанда."""
    if not cfg.has_supplier:
        await message.answer("ℹ️ Таъминкунанда хомӯш аст — санҷиш лозим нест.")
        return
    waiting = await message.answer("⏳ Каталоги таъминкунанда гирифта мешавад...")
    live = await supplier.products()
    if not live:
        await waiting.edit_text(
            "⚠️ Каталогро гирифта натавонистам (калид ё шабака). SKU-ҳо санҷида нашуданд."
        )
        return

    missing = []
    for category in catalog.CATEGORIES:
        for row in db.products(category, only_active=False):
            sku = row["sku"]
            if row["kind"] == "game" and sku and sku not in live:
                missing.append(f"• {texts.esc(row['title'])} → <code>{texts.esc(sku)}</code>")

    if not missing:
        await waiting.edit_text(
            f"✅ Ҳамаи SKU-ҳо дурустанд.\nДар каталоги таъминкунанда: <b>{len(live)}</b> мол."
        )
        return
    await waiting.edit_text(
        f"❌ <b>Ин SKU-ҳо дар каталоги таъминкунанда нестанд ({len(missing)}):</b>\n\n"
        + "\n".join(missing[:30])
        + "\n\n<i>Нархро тағйир додан кифоя нест — SKU-ро дар "
          "<code>shop/catalog.py</code> дуруст кунед.</i>"
    )


@router.callback_query(F.data == "a:supplier")
async def cb_supplier(cb: CallbackQuery, cfg: Config, supplier) -> None:
    mode = "🔌 FireLoot (худкор)" if cfg.has_supplier else "✋ Дастӣ (API хомӯш)"
    text = (
        "🔌 <b>Таъминкунанда</b>\n\n"
        f"📶 Реҷа: <b>{mode}</b>\n"
        f"🌐 Суроға: <code>{texts.esc(cfg.supplier_url or '—')}</code>\n\n"
        "Фармонҳо:\n"
        "• /balance — баланси таъминкунанда\n"
        "• /sku — санҷиши SKU-ҳои каталог"
    )
    await safe_edit(cb, text, keyboards.admin_back())
    await cb.answer()


# ── санҷиши ранги тугмаҳо ─────────────────────────────────────────────
@router.message(Command("rang", "colors"))
async def cmd_colors(message: Message, bot: Bot) -> None:
    """Се тугмаи намуна мефиристад — то бо чашми худ бубинед, ранг ҳаст ё не."""
    import aiogram
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from .. import style

    probe = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Сабз (success)", callback_data="a:home",
                                  style=style.SUCCESS)],
            [InlineKeyboardButton(text="🔴 Сурх (danger)", callback_data="a:home",
                                  style=style.DANGER)],
            [InlineKeyboardButton(text="🔵 Кабуд (primary)", callback_data="a:home",
                                  style=style.PRIMARY)],
        ]
    )
    head = (
        "🎨 <b>Санҷиши ранги тугмаҳо</b>\n\n"
        f"🎨 Ранги тугмаҳо: {'✅ фаъол' if style.enabled() else '🚫 хомӯш'}\n"
        f"📦 aiogram {aiogram.__version__} · Bot API {aiogram.__api_version__}\n\n"
    )
    try:
        await bot.send_message(
            message.chat.id,
            head
            + "Тугмаҳои поён бояд се ранги гуногун дошта бошанд.\n\n"
              "Агар ҳамаашон як хел бошанд — Telegram-и шумо кӯҳна аст "
              "(ранг аз Bot API 10.3 сар мешавад), барномаро нав кунед.",
            reply_markup=probe,
        )
    except TelegramBadRequest as exc:
        await message.answer(
            head
            + "❌ <b>Telegram рангро қабул накард.</b>\n\n"
              f"Ҷавоби сервер:\n<code>{texts.esc(exc)}</code>\n\n"
              "Дар <code>.env</code> нависед <code>SHOP_BUTTON_COLORS=0</code> "
              "ва ботро аз нав оғоз кунед."
        )
