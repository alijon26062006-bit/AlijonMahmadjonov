"""Покупка: игра → пакет → ID игрока → промокод → подтверждение → заказ.

Порядок шагов и правила те же, что в PHP-версии:
  * перед покупкой проверяется обязательная подписка на каналы;
  * промокод спрашивается один раз, до подтверждения, и пересчитывает сумму;
  * деньги списываются один раз, атомарно, уже с учётом скидки;
  * если заказ не удалось записать после списания — деньги возвращаются сразу;
  * после первой покупки пригласившему начисляется реферальный бонус.
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
from services import promo as promo_svc
from services import referral, subs
from texts import DEFAULT_LANG, t

router = Router()

SKIP_PROMO = {"-", "—", "нет", "не", "no", "skip", "0"}


class Buy(StatesGroup):
    player_id = State()
    server_id = State()
    promo = State()
    confirm = State()


async def _ulang(uid: int) -> str:
    user = await db.get_user(uid)
    return (user or {}).get("lang") or DEFAULT_LANG


async def _gate(target: Message, uid: int, lang: str) -> bool:
    """Пускать ли к покупке. Если нет — показываем каналы для подписки."""
    if await subs.ok(target.bot, uid):
        return True
    channels = await db.subs_list(True)
    await target.answer(subs.text(lang), reply_markup=subs.kb(channels, lang))
    return False


async def _show_games(target: Message, uid: int, lang: str) -> None:
    if not await _gate(target, uid, lang):
        return
    games = await db.games()
    if not games:
        await target.answer(t(lang, "no_games"))
        return
    await target.answer(t(lang, "choose_game"), reply_markup=kb.games_kb(games))


@router.message(_btn("menu_buy"))
async def btn_buy(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_games(msg, msg.from_user.id, await _lang(msg))


@router.callback_query(F.data == "buy")
async def cb_buy(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer()
    await _show_games(cb.message, cb.from_user.id, await _ulang(cb.from_user.id))


@router.callback_query(F.data.startswith("g:"))
async def cb_game(cb: CallbackQuery) -> None:
    gid = int(cb.data.split(":", 1)[1])
    lang = await _ulang(cb.from_user.id)
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
    await cb.message.edit_text(
        t(lang, "choose_pack", game=game.get("title") or game.get("name")),
        reply_markup=kb.packs_kb(packs, lang, cur),
    )


@router.callback_query(F.data.startswith("p:"))
async def cb_pack(cb: CallbackQuery, state: FSMContext) -> None:
    pid = int(cb.data.split(":", 1)[1])
    uid = cb.from_user.id
    lang = await _ulang(uid)

    pack = await db.pack(pid)
    if not pack:
        await cb.answer(t(lang, "err"), show_alert=True)
        return
    game = await db.game(pack["game_id"])
    if not game:
        await cb.answer(t(lang, "err"), show_alert=True)
        return

    # подписку проверяем и здесь: каталог мог быть открыт до отписки
    if not await subs.ok(cb.bot, uid):
        await cb.answer()
        channels = await db.subs_list(True)
        await cb.message.answer(subs.text(lang), reply_markup=subs.kb(channels, lang))
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
    lang = await _lang(msg)
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
    await _ask_promo(msg, state, lang)


@router.message(Buy.server_id)
async def got_server_id(msg: Message, state: FSMContext) -> None:
    lang = await _lang(msg)
    raw = (msg.text or "").strip()
    if not _valid_id(raw):
        await msg.answer(t(lang, "bad_id"))
        return
    await state.update_data(server_id=raw)
    await _ask_promo(msg, state, lang)


# ─────────────────────────── промокод ───────────────────────────

async def _ask_promo(msg: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Buy.promo)
    await msg.answer(t(lang, "promo_ask"))


@router.message(Buy.promo)
async def got_promo(msg: Message, state: FSMContext) -> None:
    uid = msg.from_user.id
    lang = await _lang(msg)
    cur = await db.currency()
    raw = (msg.text or "").strip()

    if raw.lower() in SKIP_PROMO:
        await msg.answer(t(lang, "promo_skip"))
        await _ask_confirm(msg, state, lang)
        return

    data = await state.get_data()
    pack = await db.pack(int(data.get("pid", 0)))
    if not pack:
        await state.clear()
        await msg.answer(t(lang, "err"))
        return

    price = Decimal(pack["price"] or 0)
    res = await promo_svc.check(raw, uid, price)
    if not res.ok:
        await msg.answer(
            t(lang, promo_svc.error_key(res.err),
              min=money(res.min_sum), cur=cur)
        )
        return   # остаёмся на шаге промокода, можно ввести другой или «-»

    await state.update_data(promo_id=int(res.promo["id"]),
                            promo_code=res.promo["code"],
                            promo_off=str(res.off))
    await msg.answer(t(lang, "promo_ok", code=res.promo["code"],
                       off=money(res.off), cur=cur))
    await _ask_confirm(msg, state, lang)


# ─────────────────────────── подтверждение ───────────────────────────

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
    price = Decimal(pack["price"] or 0)
    off = Decimal(data.get("promo_off", "0"))
    srv = data.get("server_id")
    srv_line = (f"\n{game.get('server_label') or 'Server'}: <code>{srv}</code>"
                if srv else "")

    body = t(lang, "confirm",
             game=game.get("title") or game.get("name"),
             pack=pack.get("title") or pack.get("name"),
             id_label=game.get("id_label") or "ID",
             pid=data["player_id"],
             server=srv_line,
             price=money(price),
             cur=cur,
             balance=money(bal))
    if off > 0:
        body += t(lang, "confirm_disc", off=money(off),
                  total=money(price - off), cur=cur)

    await state.set_state(Buy.confirm)
    await msg.answer(body, reply_markup=kb.confirm_kb(lang))


@router.callback_query(Buy.confirm, F.data == "no")
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    lang = await _ulang(cb.from_user.id)
    await state.clear()
    await cb.answer()
    await cb.message.edit_text(t(lang, "cancelled"))


@router.callback_query(Buy.confirm, F.data == "ok")
async def cb_confirm(cb: CallbackQuery, state: FSMContext) -> None:
    uid = cb.from_user.id
    lang = await _ulang(uid)
    cur = await db.currency()

    data = await state.get_data()
    await state.clear()          # повторное нажатие уже не спишет второй раз

    game = await db.game(int(data.get("gid", 0)))
    pack = await db.pack(int(data.get("pid", 0)))
    if not game or not pack or not data.get("player_id"):
        await cb.answer(t(lang, "err"), show_alert=True)
        return

    price = Decimal(pack["price"] or 0)
    off = Decimal(data.get("promo_off", "0"))
    if off > price:
        off = price
    total = price - off
    title = f"{game.get('name')} — {pack.get('name')}"

    new_bal = await db.charge(uid, total, title)
    if new_bal is None:
        bal = await db.balance(uid)
        await cb.answer()
        await cb.message.edit_text(
            t(lang, "not_enough", need=money(total), balance=money(bal), cur=cur),
            reply_markup=kb.topup_kb(lang),
        )
        return

    try:
        oid = await db.create_order(
            uid, game, pack, data["player_id"], data.get("server_id"), total)
    except Exception as e:
        log.exception("заказ не записался, возвращаю деньги: %s", e)
        await db.credit(uid, total, f"Возврат: {title}", kind="refund")
        await cb.answer(t(lang, "err"), show_alert=True)
        return

    # промокод засчитываем только когда заказ уже существует
    if data.get("promo_id") and off > 0:
        try:
            await promo_svc.apply({"id": data["promo_id"]}, uid, oid, off)
        except Exception as e:
            log.warning("промокод не отмечен для заказа #%s: %s", oid, e)

    await cb.answer()
    await cb.message.edit_text(
        t(lang, "order_created",
          oid=oid,
          game=game.get("title") or game.get("name"),
          pack=pack.get("title") or pack.get("name"),
          id_label=game.get("id_label") or "ID",
          pid=data["player_id"],
          price=money(total),
          cur=cur)
    )

    srv = data.get("server_id")
    await notify_admins(
        cb.bot,
        f"🎮 <b>Заказ #{oid}</b>\n"
        f"{game.get('name')} — {pack.get('name')}\n"
        f"{game.get('id_label') or 'ID'}: <code>{data['player_id']}</code>"
        + (f"\n{game.get('server_label') or 'Server'}: <code>{srv}</code>" if srv else "")
        + f"\nЦена: <b>{money(total)} {cur}</b>"
        + (f" (промокод {data.get('promo_code')}, −{money(off)})" if off > 0 else "")
        + f"\nОт: {cb.from_user.full_name} (<code>{uid}</code>)"
        + (f" @{cb.from_user.username}" if cb.from_user.username else ""),
        kb.admin_order_kb(oid),
    )

    # бонус пригласившему — за первую покупку, внутри всё защищено от повтора
    await referral.pay_for_first_order(cb.bot, uid)
