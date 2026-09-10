"""Покупка: игра → пакет → ID игрока → подтверждение → списание → заказ.

Деньги списываются один раз, в момент подтверждения, атомарно.
Если создать заказ после списания не удалось — деньги возвращаются сразу.
"""
from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import db
import keyboards as kb
from handlers.common import log, money, notify_admins
from handlers.user import _btn, _lang
from texts import DEFAULT_LANG, t

router = Router()


class Buy(StatesGroup):
    player_id = State()
    server_id = State()
    confirm = State()


async def _show_games(target: Message, lang: str) -> None:
    games = await db.games()
    if not games:
        await target.answer(t(lang, "no_games"))
        return
    await target.answer(t(lang, "choose_game"), reply_markup=kb.games_kb(games))


@router.message(_btn("menu_buy"))
async def btn_buy(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_games(msg, await _lang(msg))


@router.callback_query(F.data == "buy")
async def cb_buy(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    user = await db.get_user(cb.from_user.id)
    await _show_games(cb.message, (user or {}).get("lang") or DEFAULT_LANG)


@router.callback_query(F.data.startswith("g:"))
async def cb_game(cb: CallbackQuery, state: FSMContext) -> None:
    gid = int(cb.data.split(":", 1)[1])
    user = await db.get_user(cb.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    cur = await db.currency()

    game = await db.game(gid)
    if not game:
        await cb.answer(t(lang, "err"), show_alert=True)
        return
    packs = await db.packs(gid)
    if not packs:
        await cb.answer(t(lang, "no_packs"), show_alert=True)
        return

    await cb.answer()
    label = game.get("title") or game.get("name")
    await cb.message.edit_text(
        t(lang, "choose_pack", game=label),
        reply_markup=kb.packs_kb(packs, lang, cur),
    )


@router.callback_query(F.data.startswith("p:"))
async def cb_pack(cb: CallbackQuery, state: FSMContext) -> None:
    pid = int(cb.data.split(":", 1)[1])
    user = await db.get_user(cb.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG

    pack = await db.pack(pid)
    if not pack:
        await cb.answer(t(lang, "err"), show_alert=True)
        return
    game = await db.game(pack["game_id"])
    if not game:
        await cb.answer(t(lang, "err"), show_alert=True)
        return

    await state.update_data(gid=game["id"], pid=pack["id"])
    await state.set_state(Buy.player_id)
    await cb.answer()

    hint = f"\n\n<i>{game['hint']}</i>" if game.get("hint") else ""
    await cb.message.answer(
        t(lang, "enter_id",
          game=game.get("title") or game.get("name"),
          pack=pack.get("title") or pack.get("name"),
          label=game.get("id_label") or "ID") + hint
    )


def _valid_id(raw: str) -> bool:
    v = (raw or "").strip()
    return 2 <= len(v) <= 64 and not v.startswith("/")


@router.message(Buy.player_id)
async def got_player_id(msg: Message, state: FSMContext) -> None:
    user = await db.get_user(msg.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    raw = (msg.text or "").strip()
    if not _valid_id(raw):
        await msg.answer(t(lang, "bad_id"))
        return

    data = await state.get_data()
    game = await db.game(int(data["gid"]))
    if not game:
        await state.clear()
        await msg.answer(t(lang, "err"))
        return

    await state.update_data(player_id=raw)
    if game.get("need_server"):
        await state.set_state(Buy.server_id)
        await msg.answer(t(lang, "enter_server",
                           label=game.get("server_label") or "Server"))
        return
    await _ask_confirm(msg, state, lang)


@router.message(Buy.server_id)
async def got_server_id(msg: Message, state: FSMContext) -> None:
    user = await db.get_user(msg.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    raw = (msg.text or "").strip()
    if not _valid_id(raw):
        await msg.answer(t(lang, "bad_id"))
        return
    await state.update_data(server_id=raw)
    await _ask_confirm(msg, state, lang)


async def _ask_confirm(msg: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    game = await db.game(int(data["gid"]))
    pack = await db.pack(int(data["pid"]))
    if not game or not pack:
        await state.clear()
        await msg.answer(t(lang, "err"))
        return

    cur = await db.currency()
    bal = await db.balance(msg.from_user.id)
    srv = data.get("server_id")
    srv_line = (f"\n{game.get('server_label') or 'Server'}: <code>{srv}</code>"
                if srv else "")

    await state.set_state(Buy.confirm)
    await msg.answer(
        t(lang, "confirm",
          game=game.get("title") or game.get("name"),
          pack=pack.get("title") or pack.get("name"),
          id_label=game.get("id_label") or "ID",
          pid=data["player_id"],
          server=srv_line,
          price=money(pack["price"]),
          cur=cur,
          balance=money(bal)),
        reply_markup=kb.confirm_kb(lang),
    )


@router.callback_query(Buy.confirm, F.data == "no")
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(cb.from_user.id)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    await state.clear()
    await cb.answer()
    await cb.message.edit_text(t(lang, "cancelled"))


@router.callback_query(Buy.confirm, F.data == "ok")
async def cb_confirm(cb: CallbackQuery, state: FSMContext) -> None:
    uid = cb.from_user.id
    user = await db.get_user(uid)
    lang = (user or {}).get("lang") or DEFAULT_LANG
    cur = await db.currency()

    data = await state.get_data()
    await state.clear()          # чтобы повторное нажатие не списало дважды

    game = await db.game(int(data.get("gid", 0)))
    pack = await db.pack(int(data.get("pid", 0)))
    if not game or not pack or not data.get("player_id"):
        await cb.answer(t(lang, "err"), show_alert=True)
        return

    price = Decimal(pack["price"] or 0)
    title = f"{game.get('name')} — {pack.get('name')}"

    new_bal = await db.charge(uid, price, title)
    if new_bal is None:
        bal = await db.balance(uid)
        await cb.answer()
        await cb.message.edit_text(
            t(lang, "not_enough", need=money(price), balance=money(bal), cur=cur),
            reply_markup=kb.topup_kb(lang),
        )
        return

    try:
        oid = await db.create_order(
            uid, game, pack, data["player_id"], data.get("server_id"), price)
    except Exception as e:
        # заказ не записался — деньги сразу назад, пользователь не теряет ничего
        log.exception("не удалось создать заказ, возвращаю деньги: %s", e)
        await db.credit(uid, price, f"Возврат: {title}", kind="refund")
        await cb.answer(t(lang, "err"), show_alert=True)
        return

    await cb.answer()
    await cb.message.edit_text(
        t(lang, "order_created",
          oid=oid,
          game=game.get("title") or game.get("name"),
          pack=pack.get("title") or pack.get("name"),
          id_label=game.get("id_label") or "ID",
          pid=data["player_id"],
          price=money(price),
          cur=cur)
    )

    srv = data.get("server_id")
    await notify_admins(
        cb.bot,
        f"🎮 <b>Заказ #{oid}</b>\n"
        f"{game.get('name')} — {pack.get('name')}\n"
        f"{game.get('id_label') or 'ID'}: <code>{data['player_id']}</code>"
        + (f"\n{game.get('server_label') or 'Server'}: <code>{srv}</code>" if srv else "")
        + f"\nЦена: <b>{money(price)} {cur}</b>\n"
        f"От: {cb.from_user.full_name} (<code>{uid}</code>)"
        + (f" @{cb.from_user.username}" if cb.from_user.username else ""),
        kb.admin_order_kb(oid),
    )
