"""Старт, язык, главное меню, баланс, пополнение, история заказов."""
from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import config
import db
import keyboards as kb
from handlers.common import money, notify_admins, parse_amount
from services import referral, subs
from texts import DEFAULT_LANG, t, status_text

router = Router()

MIN_TOPUP = Decimal("1")


class TopUp(StatesGroup):
    amount = State()
    receipt = State()


async def show_menu(msg: Message, lang: str, uid: int) -> None:
    user = await db.get_user(uid)
    cur = await db.currency()
    await msg.answer(
        t(lang, "greet",
          name=(user or {}).get("name") or "",
          balance=money((user or {}).get("balance")),
          cur=cur),
        reply_markup=kb.main_menu(lang),
    )


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext,
                    command: CommandObject | None = None) -> None:
    await state.clear()
    u = msg.from_user
    user, is_new = await db.ensure_user(
        u.id, u.username,
        " ".join(x for x in (u.first_name, u.last_name) if x) or None,
    )
    if user.get("blocked"):
        await msg.answer(t(user.get("lang"), "blocked"))
        return

    # /start 123456789 — пришёл по реферальной ссылке
    if is_new and command and command.args:
        await referral.remember_inviter(u.id, command.args)
    # у новичка спрашиваем язык один раз, дальше — сразу меню
    if is_new:
        await msg.answer(t(DEFAULT_LANG, "choose_lang"), reply_markup=kb.langs_kb())
        return
    await show_menu(msg, user["lang"], u.id)


@router.callback_query(F.data.startswith("lang:"))
async def pick_lang(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.split(":", 1)[1]
    await db.set_lang(cb.from_user.id, code)
    await state.clear()
    await cb.answer(t(code, "lang_saved"))
    try:
        await cb.message.delete()
    except Exception:
        pass
    await show_menu(cb.message, code, cb.from_user.id)


@router.message(Command("lang"))
async def cmd_lang(msg: Message) -> None:
    lang = await _lang(msg)
    await msg.answer(t(lang, "choose_lang"), reply_markup=kb.langs_kb())


async def _lang(msg: Message) -> str:
    user = await db.get_user(msg.from_user.id)
    return (user or {}).get("lang") or DEFAULT_LANG


def _btn(key: str):
    """Фильтр по тексту кнопки меню на любом из языков."""
    from texts import _TABLE
    variants = {tbl.get(key) for tbl in _TABLE.values() if tbl.get(key)}
    return F.text.in_(variants)


@router.message(_btn("menu_lang"))
async def btn_lang(msg: Message) -> None:
    await cmd_lang(msg)


@router.message(_btn("menu_support"))
async def btn_support(msg: Message) -> None:
    lang = await _lang(msg)
    support = await db.setting("support", "")
    await msg.answer(t(lang, "support", support=support or "—"))


@router.message(_btn("menu_orders"))
async def btn_orders(msg: Message) -> None:
    lang = await _lang(msg)
    cur = await db.currency()
    rows = await db.user_orders(msg.from_user.id, 10)
    if not rows:
        await msg.answer(t(lang, "orders_empty"))
        return
    lines = [t(lang, "orders_title"), ""]
    for o in rows:
        lines.append(
            f"#{o['id']} · {o['game_name']} — {o['pack_name']}\n"
            f"    <code>{o['player_id']}</code> · {money(o['price'])} {cur} · "
            f"{status_text(lang, o['status'])}"
        )
    await msg.answer("\n".join(lines))


# ─────────────────────────── баланс ───────────────────────────

@router.message(_btn("menu_balance"))
async def btn_balance(msg: Message) -> None:
    lang = await _lang(msg)
    cur = await db.currency()
    bal = await db.balance(msg.from_user.id)
    await msg.answer(
        t(lang, "balance", balance=money(bal), cur=cur),
        reply_markup=kb.topup_kb(lang),
    )


@router.callback_query(F.data == "topup")
async def topup_start(cb: CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(cb.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    await state.set_state(TopUp.amount)
    await cb.answer()
    await cb.message.answer(t(lang, "topup_amount"))


@router.message(TopUp.amount)
async def topup_amount(msg: Message, state: FSMContext) -> None:
    user = await db.get_user(msg.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    cur = await db.currency()

    amount = parse_amount(msg.text or "")
    if amount is None:
        await msg.answer(t(lang, "topup_bad"))
        return
    if amount < MIN_TOPUP:
        await msg.answer(t(lang, "topup_min", min=money(MIN_TOPUP), cur=cur))
        return

    reqs = await db.requisites()
    if not reqs:
        await state.clear()
        await msg.answer(t(lang, "topup_no_reqs"))
        return

    block = "\n\n".join(
        f"<b>{r['bank']}</b>\n<code>{r['number']}</code>\n{r['owner'] or ''}".strip()
        for r in reqs
    )
    await state.update_data(amount=str(amount), req_id=reqs[0]["id"])
    await state.set_state(TopUp.receipt)
    await msg.answer(t(lang, "topup_reqs", amount=money(amount), cur=cur, reqs=block))


@router.message(TopUp.receipt, F.photo)
async def topup_receipt(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    user = await db.get_user(msg.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    cur = await db.currency()
    amount = Decimal(data.get("amount", "0"))

    file_id = msg.photo[-1].file_id
    tid = await db.create_topup(msg.from_user.id, amount, data.get("req_id"), file_id)

    await msg.answer(t(lang, "topup_created", tid=tid))
    await notify_admins(
        msg.bot,
        f"💰 <b>Пополнение #{tid}</b>\n"
        f"Сумма: <b>{money(amount)} {cur}</b>\n"
        f"От: {msg.from_user.full_name} (<code>{msg.from_user.id}</code>)"
        + (f" @{msg.from_user.username}" if msg.from_user.username else ""),
        kb.admin_topup_kb(tid),
    )
    for admin_id in config.ADMINS:
        try:
            await msg.bot.send_photo(admin_id, file_id, caption=f"Чек к #{tid}")
        except Exception:
            pass


@router.message(TopUp.receipt)
async def topup_need_photo(msg: Message) -> None:
    user = await db.get_user(msg.from_user.id)
    await msg.answer(t((user or {}).get("lang"), "topup_wait_photo"))


# ─────────────────────────── друзья ───────────────────────────

@router.message(_btn("menu_ref"))
async def btn_ref(msg: Message) -> None:
    lang = await _lang(msg)
    await msg.answer(await referral.invite_text(msg.bot, msg.from_user.id, lang))


# ─────────────────────────── обязательная подписка ───────────────────────────

@router.callback_query(F.data == "subchk")
async def check_sub(cb: CallbackQuery) -> None:
    """«Я подписался» — проверяем заново, кэш сбрасываем."""
    uid = cb.from_user.id
    user = await db.get_user(uid)
    lang = (user or {}).get("lang") or DEFAULT_LANG

    subs.drop_cache(uid)
    if await subs.ok(cb.bot, uid):
        await cb.answer(t(lang, "sub_thanks"))
        try:
            await cb.message.delete()
        except Exception:
            pass
        await show_menu(cb.message, lang, uid)
        return

    await cb.answer(t(lang, "sub_still"), show_alert=True)
