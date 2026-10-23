"""Конструктор: пайваст кардани боти шарик, панели соҳиб ва танзимоти боти шарик."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.filters import BaseFilter

from .. import catalog, keyboards, pricelist, tenants as tenants_mod, wholesale
from ..config import Config
from ..db import Database
from ..i18n import texts
from ..states import Admin, Constructor
from .admin import IsAdmin
from .common import current_user, safe_edit, send_long

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")


class InMain(BaseFilter):
    """Танҳо дар боти асосӣ (на дар боти шарик)."""

    async def __call__(self, event: TelegramObject, cfg: Config) -> bool:
        return not cfg.is_tenant


class InTenant(BaseFilter):
    async def __call__(self, event: TelegramObject, cfg: Config) -> bool:
        return cfg.is_tenant


async def fetch_me(token: str):
    """Санҷиши токен дар Telegram. Дар тестҳо иваз карда мешавад."""
    probe = Bot(token=token)
    try:
        return await probe.get_me()
    finally:
        await probe.session.close()


# ══ Шарик дар боти асосӣ ═════════════════════════════════════════════
partner_router = Router(name="constructor_partner")
partner_router.message.filter(InMain())
partner_router.callback_query.filter(InMain())


def _platform_full(db: Database) -> bool:
    return len(db.tenants()) >= tenants_mod.max_bots_total(db)


def _limits(db: Database, cfg: Config, user_id: int) -> tuple[bool, int]:
    """(дастрасӣ дорад?, чанд бот метавонад)."""
    if cfg.is_admin(user_id):
        return True, tenants_mod.max_bots_total(db)
    access = db.constructor_access(user_id)
    return (access is not None), (access["max_bots"] if access else 0)


async def _home(cb_or_msg, db: Database, cfg: Config, user_id: int, *, edit: bool) -> None:
    allowed, limit = _limits(db, cfg, user_id)
    rows = db.tenants(user_id)
    user = db.user(user_id)
    total_ok = len(db.tenants()) < tenants_mod.max_bots_total(db)
    can_add = allowed and len(rows) < limit and total_ok and tenants_mod.constructor_open(db)
    text = texts.constructor_home(rows, user.balance if user else 0, total_ok, limit, cfg.currency)
    markup = keyboards.constructor_home(rows, can_add)
    if edit:
        await safe_edit(cb_or_msg, text, markup)
    else:
        await cb_or_msg.answer(text, reply_markup=markup)


@partner_router.callback_query(F.data == "c:home")
async def cb_c_home(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    current_user(cb, db)
    allowed, _ = _limits(db, cfg, cb.from_user.id)
    if not tenants_mod.constructor_open(db):
        await cb.answer(texts.CONSTRUCTOR_CLOSED, show_alert=True)
        return
    if not allowed and not db.tenants(cb.from_user.id):
        await cb.answer(texts.CONSTRUCTOR_NO_ACCESS.replace("\n", " "), show_alert=True)
        return
    await _home(cb, db, cfg, cb.from_user.id, edit=True)
    await cb.answer()


@partner_router.callback_query(F.data == "c:new")
async def cb_c_new(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    allowed, limit = _limits(db, cfg, cb.from_user.id)
    if not tenants_mod.constructor_open(db) or not allowed:
        await cb.answer(texts.CONSTRUCTOR_NO_ACCESS.replace("\n", " "), show_alert=True)
        return
    if len(db.tenants(cb.from_user.id)) >= limit or _platform_full(db):
        await cb.answer(texts.BOT_LIMIT.replace("❌ ", ""), show_alert=True)
        return
    await state.set_state(Constructor.waiting_token)
    await safe_edit(cb, texts.ASK_BOT_TOKEN, keyboards.constructor_cancel())
    await cb.answer()


async def _forget(message: Message) -> None:
    """Токенро дар чат намегузорем — ҳатто агар нодуруст бошад."""
    try:
        await message.delete()
    except Exception:
        pass


async def _check_token(message: Message, token: str):
    if not TOKEN_RE.match(token):
        await message.answer(texts.BAD_TOKEN, reply_markup=keyboards.constructor_cancel())
        return None
    try:
        return await fetch_me(token)
    except Exception as exc:
        log.info("Токени шарик рад шуд: %s", exc)
        await message.answer(texts.TOKEN_REJECTED, reply_markup=keyboards.constructor_cancel())
        return None


@partner_router.message(Constructor.waiting_token, F.text)
async def got_token(message: Message, state: FSMContext, db: Database, cfg: Config,
                    bot: Bot, tenants=None) -> None:
    token = message.text.strip()
    if TOKEN_RE.match(token):
        await _forget(message)
    me = await _check_token(message, token)
    if me is None:
        return
    allowed, limit = _limits(db, cfg, message.from_user.id)
    if (not allowed or not tenants_mod.constructor_open(db) or _platform_full(db)
            or len(db.tenants(message.from_user.id)) >= limit):
        await state.clear()
        await message.answer(texts.BOT_LIMIT)
        return
    if me.id == bot.id:
        await message.answer(texts.BOT_IS_MAIN, reply_markup=keyboards.constructor_cancel())
        return
    if db.tenant_by_bot(me.id) is not None:
        await message.answer(texts.BOT_ALREADY_ADDED, reply_markup=keyboards.constructor_cancel())
        return

    await state.clear()
    try:
        tenant_id = db.add_tenant(message.from_user.id, me.id, me.username or "",
                                  me.first_name or "", token)
    except sqlite3.IntegrityError:        # ҳамзамон ду бор фиристода шуд
        await message.answer(texts.BOT_ALREADY_ADDED)
        return
    if tenants is not None:
        await tenants.start(db.tenant(tenant_id))
    await message.answer(texts.bot_created(me.username or ""))
    await _home(message, db, cfg, message.from_user.id, edit=False)


def _own_tenant(db: Database, user_id: int, raw: str):
    try:
        row = db.tenant(int(raw))
    except ValueError:
        return None
    return row if row is not None and row["owner_id"] == user_id else None


@partner_router.callback_query(F.data.startswith("c:bot:"))
async def cb_c_bot(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    await _show_bot(cb, db, cfg, cb.data.rsplit(":", 1)[1])


async def _show_bot(cb: CallbackQuery, db: Database, cfg: Config, raw_id) -> None:
    # Объектҳои aiogram тағйирнопазиранд (cb.data = ... хато медиҳад) — рақамро алоҳида медиҳем.
    row = _own_tenant(db, cb.from_user.id, str(raw_id))
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    user = db.user(cb.from_user.id)
    await safe_edit(
        cb, texts.tenant_screen(row, db.tenant_sales(row["id"]), user.balance if user else 0,
                                cfg.currency),
        keyboards.tenant_manage(row),
    )
    await cb.answer()


@partner_router.callback_query(F.data.startswith("c:pause:") | F.data.startswith("c:resume:"))
async def cb_c_pause(cb: CallbackQuery, db: Database, cfg: Config, tenants=None) -> None:
    row = _own_tenant(db, cb.from_user.id, cb.data.rsplit(":", 1)[1])
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    pause = cb.data.startswith("c:pause:")
    if pause and row["status"] == "active":
        db.set_tenant(row["id"], status="paused")
        if tenants is not None:
            await tenants.stop(row["id"])
    elif not pause and row["status"] == "paused":
        db.set_tenant(row["id"], status="active")
        if tenants is not None:
            await tenants.start(db.tenant(row["id"]))
    await cb_c_bot(cb, db, cfg)


@partner_router.callback_query(F.data.startswith("c:token:"))
async def cb_c_token(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    row = _own_tenant(db, cb.from_user.id, cb.data.rsplit(":", 1)[1])
    if row is None or row["status"] == "blocked":
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    await state.set_state(Constructor.waiting_new_token)
    await state.update_data(tenant_id=row["id"])
    await safe_edit(cb, texts.ASK_BOT_TOKEN, keyboards.constructor_cancel())
    await cb.answer()


@partner_router.message(Constructor.waiting_new_token, F.text)
async def got_new_token(message: Message, state: FSMContext, db: Database, cfg: Config,
                        tenants=None) -> None:
    data = await state.get_data()
    row = _own_tenant(db, message.from_user.id, str(data.get("tenant_id", "")))
    if row is None:
        await state.clear()
        return
    token = message.text.strip()
    if TOKEN_RE.match(token):
        await _forget(message)
    me = await _check_token(message, token)
    if me is None:
        return
    if me.id != row["bot_id"]:
        await message.answer(
            "❌ Ин токени боти дигар аст. Дар @BotFather токени ҳамин ботро гиред.",
            reply_markup=keyboards.constructor_cancel(),
        )
        return
    await state.clear()
    new_status = "active" if row["status"] in ("disabled", "active") else row["status"]
    db.set_tenant(row["id"], token=token, status=new_status, note="",
                  username=me.username or row["username"])
    if tenants is not None:
        await tenants.stop(row["id"])
        if new_status == "active":
            await tenants.start(db.tenant(row["id"]))
    await message.answer(f"✅ Токен нав шуд. @{me.username} боз кор мекунад.")
    await _home(message, db, cfg, message.from_user.id, edit=False)


@partner_router.callback_query(F.data.startswith("c:lang:"))
async def cb_c_lang(cb: CallbackQuery, db: Database) -> None:
    row = _own_tenant(db, cb.from_user.id, cb.data.rsplit(":", 1)[1])
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    await safe_edit(cb, "🌐 Забони боти шумо / Язык вашего бота:",
                    keyboards.language_menu(f"c:setlang:{row['id']}:", f"c:bot:{row['id']}"))
    await cb.answer()


@partner_router.callback_query(F.data.startswith("c:setlang:"))
async def cb_c_setlang(cb: CallbackQuery, db: Database, cfg: Config, tenants=None) -> None:
    parts = cb.data.split(":")
    raw_id, lang = (parts[2], parts[3]) if len(parts) == 4 else ("", "")
    row = _own_tenant(db, cb.from_user.id, raw_id)
    if row is None or lang not in ("tj", "ru"):
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    db.set_tenant(row["id"], lang=lang)
    if tenants is not None:
        tenants.refresh(row["id"])
    await _show_bot(cb, db, cfg, row["id"])


# ══ Соҳиби платформа ═════════════════════════════════════════════════
owner_router = Router(name="constructor_owner")
owner_router.message.filter(IsAdmin(), InMain())
owner_router.callback_query.filter(IsAdmin(), InMain())


async def _owner_home(cb: CallbackQuery, db: Database) -> None:
    rows = db.tenants()
    await safe_edit(
        cb,
        texts.admin_constructor(
            tenants_mod.constructor_open(db), len(rows),
            sum(1 for r in rows if r["status"] == "active"), len(db.constructor_partners()),
            wholesale.wholesale_markup(db), tenants_mod.max_bots_total(db),
        ),
        keyboards.admin_constructor(tenants_mod.constructor_open(db)),
    )


@owner_router.callback_query(F.data == "o:home")
async def cb_o_home(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await _owner_home(cb, db)
    await cb.answer()


@owner_router.callback_query(F.data == "o:toggle")
async def cb_o_toggle(cb: CallbackQuery, db: Database, tenants=None) -> None:
    now_open = tenants_mod.constructor_open(db)
    db.set_setting(tenants_mod.CONSTRUCTOR_ON_KEY, "0" if now_open else "1")
    if tenants is not None:
        if now_open:
            await tenants.pause_all()
        else:
            await tenants.start_all()
    await _owner_home(cb, db)
    await cb.answer("🚫 Хомӯш" if now_open else "✅ Фаъол")


@owner_router.callback_query(F.data.in_({"o:markup", "o:max", "o:grant"}))
async def cb_o_ask(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    states = {
        "o:markup": (Admin.waiting_c_markup,
                     f"{texts.ADMIN_ASK_C_MARKUP}\n\nҲозир: <b>+{wholesale.wholesale_markup(db):g}%</b>"),
        "o:max": (Admin.waiting_max_bots,
                  f"{texts.ADMIN_ASK_MAX_BOTS}\n\nҲозир: <b>{tenants_mod.max_bots_total(db)}</b>"),
        "o:grant": (Admin.waiting_access, texts.ADMIN_ASK_ACCESS),
    }
    target, text = states[cb.data]
    await state.set_state(target)
    await safe_edit(cb, text, keyboards.admin_back())
    await cb.answer()


@owner_router.message(Admin.waiting_c_markup, F.text)
async def got_c_markup(message: Message, state: FSMContext, db: Database, tenants=None) -> None:
    raw = message.text.strip().replace("%", "").replace(",", ".").replace("+", "")
    try:
        value = float(raw)
    except ValueError:
        value = -1
    if not 0 <= value <= 500:
        await message.answer("❌ Фоиз нодуруст аст. Намуна: <code>10</code>")
        return
    await state.clear()
    db.set_setting(wholesale.WHOLESALE_MARKUP_KEY, f"{value:g}")
    if tenants is not None:
        tenants.reprice_all()
    await message.answer(f"✅ Наценкаи яклухт: <b>+{value:g}%</b>",
                         reply_markup=keyboards.admin_constructor(tenants_mod.constructor_open(db)))


@owner_router.message(Admin.waiting_max_bots, F.text)
async def got_max_bots(message: Message, state: FSMContext, db: Database) -> None:
    raw = message.text.strip()
    if not raw.isdigit() or not 0 <= int(raw) <= 10000:
        await message.answer("❌ Рақам нависед. Намуна: <code>50</code>")
        return
    await state.clear()
    db.set_setting(tenants_mod.MAX_BOTS_KEY, raw)
    await message.answer(f"✅ Ҳадди ботҳо: <b>{raw}</b>",
                         reply_markup=keyboards.admin_constructor(tenants_mod.constructor_open(db)))


@owner_router.callback_query(F.data == "o:partners")
async def cb_o_partners(cb: CallbackQuery, state: FSMContext, db: Database, cfg: Config) -> None:
    await state.clear()
    rows = db.constructor_partners()
    await safe_edit(cb, texts.admin_c_partners(rows, cfg.currency), keyboards.admin_c_partners(rows))
    await cb.answer()


@owner_router.message(Admin.waiting_access, F.text)
async def got_access(message: Message, state: FSMContext, db: Database, cfg: Config,
                     bot: Bot) -> None:
    parts = message.text.split()
    found = db.find_user(parts[0]) if parts else None
    max_bots = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    if found is None:
        await message.answer(
            texts.ADMIN_USER_NOT_FOUND
            + "\n\n<i>Бигӯед, ки аввал боти асосиро /start кунад.</i>",
            reply_markup=keyboards.admin_back(),
        )
        return
    await state.clear()
    db.grant_constructor(found.id, max(1, min(max_bots, 100)), message.from_user.id)
    try:
        await bot.send_message(
            found.id,
            "🤖 <b>Ба шумо конструктор кушода шуд!</b>\n\n"
            "Акнун метавонед боти худро созед: /start → «🤖 Боти худро созед».",
        )
    except Exception:
        pass
    rows = db.constructor_partners()
    await message.answer(texts.admin_c_partners(rows, cfg.currency),
                         reply_markup=keyboards.admin_c_partners(rows))


@owner_router.callback_query(F.data.startswith("o:revoke:"))
async def cb_o_revoke(cb: CallbackQuery, db: Database, cfg: Config, tenants=None) -> None:
    raw = cb.data.rsplit(":", 1)[1]
    if not raw.isdigit():
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    user_id = int(raw)
    db.revoke_constructor(user_id)
    # Бе дастрасӣ ботҳояш ҳам хомӯш мешаванд (маълумоташон нест намешавад).
    for row in db.tenants(user_id):
        db.set_tenant(row["id"], status="blocked", note="access_revoked")
        if tenants is not None:
            await tenants.stop(row["id"])
    rows = db.constructor_partners()
    await safe_edit(cb, texts.admin_c_partners(rows, cfg.currency), keyboards.admin_c_partners(rows))
    await cb.answer("🗑")


@owner_router.callback_query(F.data == "o:bots")
async def cb_o_bots(cb: CallbackQuery, db: Database) -> None:
    rows = db.tenants()
    await safe_edit(cb, texts.admin_tenants(rows), keyboards.admin_tenants(rows))
    await cb.answer()


@owner_router.callback_query(F.data.startswith("o:block:") | F.data.startswith("o:unblock:"))
async def cb_o_block(cb: CallbackQuery, db: Database, tenants=None) -> None:
    block = cb.data.startswith("o:block:")
    raw = cb.data.rsplit(":", 1)[1]
    row = db.tenant(int(raw)) if raw.isdigit() else None
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    if block:
        db.set_tenant(row["id"], status="blocked", note="owner")
        if tenants is not None:
            await tenants.stop(row["id"])
    else:
        db.set_tenant(row["id"], status="active", note="")
        if tenants is not None:
            await tenants.start(db.tenant(row["id"]))
    await cb_o_bots(cb, db)


def _tenant_of(raw: str, db: Database):
    return db.tenant(int(raw)) if raw.isdigit() else None


@owner_router.callback_query(F.data.startswith("o:del:"))
async def cb_o_delete(cb: CallbackQuery, db: Database, cfg: Config, tenants=None) -> None:
    row = _tenant_of(cb.data.rsplit(":", 1)[1], db)
    if row is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    tdb = tenants.tenant_db(row["bot_id"]) if tenants is not None else None
    await safe_edit(
        cb,
        texts.tenant_delete_confirm(row, tdb.stats() if tdb else None,
                                    db.tenant_sales(row["id"]), cfg.currency),
        keyboards.tenant_delete_confirm(row["id"]),
    )
    await cb.answer()


@owner_router.callback_query(F.data.startswith("o:delok:"))
async def cb_o_delete_ok(cb: CallbackQuery, db: Database, cfg: Config, bot: Bot,
                         tenants=None) -> None:
    from aiogram.types import FSInputFile

    row = _tenant_of(cb.data.rsplit(":", 1)[1], db)
    if row is None:                      # аллакай нест шуд (пахши дуюм)
        await cb_o_bots(cb, db)
        return
    backup = None
    if tenants is not None:
        try:
            backup = await tenants.remove(row, Path(cfg.db_path).parent / "deleted")
        except tenants_mod.TenantBusy:
            await cb.answer(texts.TENANT_BUSY, show_alert=True)
            return
    else:
        db.delete_tenant(row["id"])
    name = row["username"] or str(row["bot_id"])
    if backup is not None:
        # Нусха танҳо ба соҳиб дар Telegram — дар сервер чизе намемонад.
        try:
            await bot.send_document(
                cb.from_user.id, FSInputFile(backup),
                caption=f"📦 Нусхаи базаи @{texts.esc(name)} — пеш аз нест кардан.",
            )
        except Exception as exc:
            log.warning("Нусхаи базаи @%s фиристода нашуд: %s", name, exc)
        finally:
            backup.unlink(missing_ok=True)
    try:
        await bot.send_message(row["owner_id"], texts.tenant_deleted_partner(name))
    except Exception:
        pass
    rows = db.tenants()
    await safe_edit(cb, texts.admin_tenants(rows), keyboards.admin_tenants(rows))
    await cb.answer(texts.tenant_deleted(name), show_alert=True)     # як ҷавоб ба тугма


# ══ Боти шарик: танзимоти махсус ═════════════════════════════════════
tenant_router = Router(name="constructor_tenant")
tenant_router.message.filter(IsAdmin(), InTenant())
tenant_router.callback_query.filter(IsAdmin(), InTenant())

#: Бахшҳои соҳиби платформа — дар боти шарик пинҳон.
OWNER_ONLY = ("a:supplier", "a:addgame", "a:costs", "a:rate", "a:markup",
              "a:apitoggle", "a:apimarkup", "a:addfam:")


@tenant_router.callback_query(F.data.func(lambda d: any(d == k or (k.endswith(":") and d.startswith(k))
                                                        for k in OWNER_ONLY)))
async def cb_owner_only(cb: CallbackQuery) -> None:
    await cb.answer("Ин бахш танҳо барои соҳиби платформа.", show_alert=True)


#: Оператор танҳо фармоишҳо, пардохтҳо, харидорон ва шарҳҳоро мебинад.
OPERATOR_ALLOWED = ("a:home", "a:orders", "a:odone", "a:orej", "a:topups", "a:tok", "a:trej",
                    "a:users", "a:find", "a:stats", "a:revok", "a:revno", "a:block", "a:unblock")


class IsOperator(BaseFilter):
    """Админи боти шарик, ки соҳиб нест."""

    async def __call__(self, event: TelegramObject, cfg: Config) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and cfg.is_admin(user.id) and not cfg.is_owner(user.id))


def _operator_forbidden(data: str | None) -> bool:
    if not data or not data.startswith("a:"):
        return False
    return not any(data == k or data.startswith(k + ":") for k in OPERATOR_ALLOWED)


@tenant_router.callback_query(IsOperator(), F.data.func(_operator_forbidden))
async def cb_operator_forbidden(cb: CallbackQuery) -> None:
    await cb.answer("Ин бахш танҳо барои соҳиби бот.", show_alert=True)


@tenant_router.callback_query(F.data == "a:wlist")
async def cb_t_wholesale_list(cb: CallbackQuery, db: Database) -> None:
    cats = [c for c in catalog.CATEGORIES if db.products(c, only_active=False)]
    await safe_edit(cb, texts.WHOLESALE_LIST_HEAD, keyboards.wholesale_categories(cats))
    await cb.answer()


@tenant_router.callback_query(F.data.startswith("a:wlist:"))
async def cb_t_wholesale_category(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    category = cb.data.rsplit(":", 1)[1]
    if category not in catalog.CATEGORY_INFO:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    rows = db.products(category, only_active=False)
    lines = texts.wholesale_lines(category, rows, cfg.currency)
    await send_long(cb, pricelist.chunks(lines), keyboards.wholesale_back())
    await cb.answer()


@tenant_router.message(Command("sku", "rang", "colors"))
async def cmd_owner_only(message: Message) -> None:
    await message.answer("Ин фармон танҳо барои соҳиби платформа.")


@tenant_router.message(Command("balance", "hisob"))
async def cmd_wholesale_balance(message: Message, cfg: Config, supplier) -> None:
    data = await supplier.balance()
    await message.answer(f"💳 Ҳисоби яклухт: <b>{data.get('balance')} сомонӣ</b>")


@tenant_router.callback_query(F.data.in_({"a:pmarkup", "a:lowbal", "a:support", "a:opadd"}))
async def cb_t_ask(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    current = {
        "a:pmarkup": (Admin.waiting_partner_markup,
                      f"{texts.ADMIN_ASK_PARTNER_MARKUP}\n\nҲозир: <b>+{wholesale.partner_markup(db):g}%</b>"),
        "a:lowbal": (Admin.waiting_low_balance, texts.ADMIN_ASK_LOW_BALANCE),
        "a:support": (Admin.waiting_support, texts.ADMIN_ASK_SUPPORT),
        "a:opadd": (Admin.waiting_operator, texts.ADMIN_ASK_OPERATOR),
    }
    target, text = current[cb.data]
    await state.set_state(target)
    await safe_edit(cb, text, keyboards.admin_back())
    await cb.answer()


@tenant_router.message(Admin.waiting_partner_markup, F.text)
async def got_partner_markup(message: Message, state: FSMContext, db: Database, tenants=None) -> None:
    raw = message.text.strip().replace("%", "").replace(",", ".").replace("+", "")
    try:
        value = float(raw)
    except ValueError:
        value = -1
    if not 0 <= value <= 500:
        await message.answer("❌ Фоиз нодуруст аст. Намуна: <code>15</code>")
        return
    await state.clear()
    db.set_setting(wholesale.PARTNER_MARKUP_KEY, f"{value:g}")
    if tenants is not None:
        wholesale.reprice_tenant(tenants.platform.db, db)
    await message.answer(
        f"✅ Наценка: <b>+{value:g}%</b>\n<i>Нархҳо аз нав ҳисоб шуданд.</i>",
        reply_markup=keyboards.admin_settings(),
    )


@tenant_router.message(Admin.waiting_low_balance, F.text)
async def got_low_balance(message: Message, state: FSMContext, db: Database) -> None:
    amount = texts.to_diram(message.text)
    if amount is None:
        await message.answer("❌ Маблағ нодуруст. Намуна: <code>50</code>")
        return
    await state.clear()
    db.set_setting(wholesale.LOW_BALANCE_KEY, str(amount))
    await message.answer(f"✅ Огоҳӣ аз <b>{texts.money(amount)}</b>",
                         reply_markup=keyboards.admin_settings())


@tenant_router.message(Admin.waiting_support, F.text)
async def got_support(message: Message, state: FSMContext, db: Database, tenant=None,
                      tenants=None) -> None:
    raw = message.text.strip().lstrip("@")
    if raw in ("-", "—"):
        raw = ""
    elif not re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", raw):
        await message.answer("❌ Username нодуруст. Намуна: <code>my_support</code>")
        return
    await state.clear()
    db.set_setting(tenants_mod.SUPPORT_KEY, raw)
    if tenants is not None and tenant is not None:
        tenants.refresh(tenant.id)
    await message.answer(f"✅ Дастгирӣ: {('@' + raw) if raw else '—'}",
                         reply_markup=keyboards.admin_settings())


@tenant_router.callback_query(F.data == "a:ops")
async def cb_t_ops(cb: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    ops = tenants_mod.operators_of(db)
    await safe_edit(
        cb,
        "👥 <b>Операторон</b>\n\nОператорон ҳамон панели админро мебинанд: фармоишҳо, "
        "пардохтҳо, харидорон.\n\n" + ("\n".join(f"• <code>{o}</code>" for o in ops) or "Ҳоло нест."),
        keyboards.operators_menu(ops),
    )
    await cb.answer()


@tenant_router.message(Admin.waiting_operator, F.text)
async def got_operator(message: Message, state: FSMContext, db: Database, tenant=None,
                       tenants=None) -> None:
    found = db.find_user(message.text)
    if found is None:
        await message.answer(texts.ADMIN_USER_NOT_FOUND + "\n\n<i>Ӯ бояд аввал ботро /start кунад.</i>")
        return
    await state.clear()
    ops = tuple(dict.fromkeys((*tenants_mod.operators_of(db), found.id)))
    db.set_setting(tenants_mod.OPERATORS_KEY, ",".join(map(str, ops)))
    if tenants is not None and tenant is not None:
        tenants.refresh(tenant.id)
    await message.answer(f"✅ Оператор илова шуд: <code>{found.id}</code>",
                         reply_markup=keyboards.operators_menu(ops))


@tenant_router.callback_query(F.data.startswith("a:opdel:"))
async def cb_t_opdel(cb: CallbackQuery, state: FSMContext, db: Database, tenant=None,
                     tenants=None) -> None:
    raw = cb.data.rsplit(":", 1)[1]
    if not raw.lstrip("-").isdigit():
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    gone = int(raw)
    ops = tuple(o for o in tenants_mod.operators_of(db) if o != gone)
    db.set_setting(tenants_mod.OPERATORS_KEY, ",".join(map(str, ops)))
    if tenants is not None and tenant is not None:
        tenants.refresh(tenant.id)
    await cb_t_ops(cb, state, db)


@tenant_router.callback_query(F.data == "a:lang")
async def cb_t_lang(cb: CallbackQuery) -> None:
    await safe_edit(cb, "🌐 Забони бот / Язык бота:", keyboards.language_menu("a:setlang:", "a:settings"))
    await cb.answer()


@tenant_router.callback_query(F.data.startswith("a:setlang:"))
async def cb_t_setlang(cb: CallbackQuery, db: Database, tenant=None, tenants=None) -> None:
    lang = cb.data.rsplit(":", 1)[1]
    if lang not in ("tj", "ru") or tenant is None or tenants is None:
        await cb.answer(texts.UNKNOWN, show_alert=True)
        return
    tenants.platform.db.set_tenant(tenant.id, lang=lang)
    tenants.refresh(tenant.id)
    await cb.answer("✅")
    await safe_edit(cb, "✅ Забон иваз шуд / Язык изменён. /start", keyboards.admin_settings())


@tenant_router.callback_query(F.data.startswith("a:unlock:"))
async def cb_t_unlock(cb: CallbackQuery, db: Database, cfg: Config, tenants=None) -> None:
    from .admin import cb_price_item

    code = cb.data.rsplit(":", 1)[1]
    db.unlock_price(code)
    if tenants is not None:
        wholesale.reprice_tenant(tenants.platform.db, db)
    await cb_price_item(cb, db, cfg)          # рамзи мол охирин қисми cb.data аст
