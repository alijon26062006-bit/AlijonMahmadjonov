"""Реферальная программа.

Бонус платится пригласившему один раз — за первую покупку приглашённого.
Право на выплату «бронируется» условным UPDATE ref_paid=1, поэтому два
одновременных заказа не начислят бонус дважды.
"""
from __future__ import annotations

from decimal import Decimal

from aiogram import Bot

import db
from handlers.common import log, money
from texts import t

DEFAULT_BONUS = Decimal("0.50")


async def bonus_amount() -> Decimal:
    raw = await db.setting("ref_bonus", str(DEFAULT_BONUS))
    try:
        return Decimal(str(raw).replace(",", "."))
    except Exception:
        return DEFAULT_BONUS


async def remember_inviter(uid: int, payload: str) -> None:
    """Разобрать /start <payload> и записать пригласившего, если он валиден."""
    digits = "".join(ch for ch in (payload or "") if ch.isdigit())
    if not digits:
        return
    try:
        inviter = int(digits)
    except ValueError:
        return
    if inviter <= 0 or inviter == uid:
        return
    try:
        await db.set_ref_by(uid, inviter)
    except Exception as e:
        log.warning("не записал пригласившего для %s: %s", uid, e)


async def pay_for_first_order(bot: Bot, uid: int) -> None:
    """Начислить бонус пригласившему после первой покупки uid."""
    try:
        bonus = await bonus_amount()
        if bonus <= 0:
            return
        inviter = await db.claim_ref_bonus(uid)
        if inviter is None:
            return

        buyer = await db.get_user(uid) or {}
        who = (buyer.get("name") or "").strip() or "Друг"
        stats = await db.pay_ref_bonus(inviter, bonus, who, uid)

        lang = (await db.get_user(inviter) or {}).get("lang")
        cur = await db.currency()
        try:
            await bot.send_message(
                inviter,
                t(lang, "ref_paid",
                  who=who, bonus=money(bonus), cur=cur,
                  balance=money(stats.get("balance")),
                  friends=int(stats.get("ref_cnt") or 0)),
            )
        except Exception as e:
            log.warning("бонус начислен, но %s не уведомлён: %s", inviter, e)
    except Exception as e:
        # деньги за заказ уже списаны — падать здесь нельзя
        log.exception("выплата реферального бонуса не прошла: %s", e)


async def invite_text(bot: Bot, uid: int, lang: str) -> str:
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"
    stats = await db.ref_stats(uid)
    cur = await db.currency()
    return t(lang, "ref_info",
             link=link,
             bonus=money(await bonus_amount()),
             cur=cur,
             friends=int(stats.get("ref_cnt") or 0),
             earned=money(stats.get("ref_sum")))
