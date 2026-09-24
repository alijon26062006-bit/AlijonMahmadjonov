"""Счёт у поставщика Donatix — прямо в боте, для админов.

Бот, запущенный через конструктор Donatix, покупает товары с баланса владельца
в Donatix. Здесь владелец видит этот баланс и пополняет его: выбирает способ
оплаты, вводит сумму в сомони, получает реквизиты, жмёт «Я оплатил» и
присылает чек. Чек уходит администратору Donatix, после подтверждения баланс
зачисляется сам.

Раздел включается, только когда задан DONATIX_URL (его ставит конструктор).
"""
from __future__ import annotations

import logging
import os
from html import escape as esc

import aiohttp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.services import access

log = logging.getLogger(__name__)
router = Router(name="donatix")
router.message.filter(F.from_user.func(lambda u: access.is_admin(u.id)))
router.callback_query.filter(F.from_user.func(lambda u: access.is_admin(u.id)))

TIMEOUT = aiohttp.ClientTimeout(total=30, connect=8)
MAX_RECEIPT = 10 * 1024 * 1024


class TopUp(StatesGroup):
    amount = State()    # ждём сумму в сомони
    receipt = State()   # ждём фото или PDF чека


def enabled() -> bool:
    return bool(os.environ.get("DONATIX_URL") and settings.fazer_api_key)


def _base() -> str:
    return os.environ.get("DONATIX_URL", "").rstrip("/")


class DonatixError(Exception):
    pass


async def _call(method: str, path: str, *, json: dict | None = None, data: aiohttp.FormData | None = None) -> dict:
    headers = {"X-API-Key": settings.fazer_api_key, "Accept": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT, headers=headers) as s:
            async with s.request(method, _base() + path, json=json, data=data) as r:
                try:
                    body = await r.json(content_type=None)
                except ValueError:
                    body = {}
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise DonatixError("Donatix сейчас не отвечает, попробуйте через минуту.") from exc
    if not isinstance(body, dict) or r.status >= 400 or body.get("ok") is False:
        raise DonatixError(str((body or {}).get("error") or f"Ошибка {r.status}"))
    return body


def _kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for row in rows:
        kb.row(*[InlineKeyboardButton(text=t, callback_data=d) for t, d in row])
    return kb.as_markup()


async def _show(target: Message | CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    """Нажатие кнопки правит тот же экран; новое сообщение — только если править нечего."""
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            return
        except TelegramBadRequest as exc:
            if "not modified" in str(exc):
                return  # экран и так такой — второе сообщение не шлём
            if "no text" not in str(exc) and "can't be edited" not in str(exc):
                raise
        target = target.message  # у экрана с фото нет текста — пришлём новый
    await target.answer(text, reply_markup=kb, disable_web_page_preview=True)


STATUS = {"pending": "⏳ проверяется", "paid": "✅ зачислено", "rejected": "❌ отклонено", "cancelled": "отменено"}


# ── Главный экран ────────────────────────────────────────────


@router.message(Command("donatix"))
@router.callback_query(F.data == "dx:home")
async def home(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not enabled():
        await _show(event, "Счёт Donatix не подключён.")
        return
    try:
        bal = await _call("GET", "/api/v2/balance")
        pays = await _call("GET", "/api/v1/payments")
    except DonatixError as exc:
        await _show(event, f"🏦 <b>Счёт Donatix</b>\n\n{esc(str(exc))}", _kb([("🔄 Обновить", "dx:home")]))
        if isinstance(event, CallbackQuery):
            await event.answer()
        return
    lines = [f"🏦 <b>Счёт Donatix</b>\n\nБаланс: <b>${esc(str(bal.get('balance')))}</b>",
             "С него оплачиваются заказы ваших клиентов. Когда баланс кончится, заказы остановятся."]
    recent = pays.get("items", [])[:5]
    if recent:
        lines.append("\n<b>Последние пополнения</b>")
        for p in recent:
            lines.append(f"#{p['id']} · {esc(p['pay_amount'])} {esc(p['pay_currency'])} · {STATUS.get(p['status'], p['status'])}")
    await _show(event, "\n".join(lines), _kb([("💳 Пополнить счёт", "dx:methods")], [("🔄 Обновить", "dx:home")],
                                              [("‹ В панель", "pn:home")]))
    if isinstance(event, CallbackQuery):
        await event.answer()


# ── Пополнение ───────────────────────────────────────────────


@router.callback_query(F.data == "dx:methods")
async def methods(call: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await _call("GET", "/api/v1/payments/methods")
    except DonatixError as exc:
        await call.answer(str(exc)[:190], show_alert=True)
        return
    ms = data.get("methods") or []
    if not ms:
        await _show(call, "Способы оплаты ещё не настроены. Напишите администратору Donatix.",
                    _kb([("‹ Назад", "dx:home")]))
        await call.answer()
        return
    await state.update_data(dx_min=data.get("min_tjs"), dx_rate=data.get("tjs_rate"))
    rows = [[(f"{m['title']} · {m['currency']}", f"dx:m:{m['code']}")] for m in ms]
    rows.append([("‹ Назад", "dx:home")])
    await _show(call, f"💳 <b>Пополнение счёта Donatix</b>\n\nВыберите способ оплаты.\n"
                      f"Минимум — <b>{esc(str(data.get('min_tjs')))} сомони</b>.", _kb(*rows))
    await call.answer()


@router.callback_query(F.data.startswith("dx:m:"))
async def pick_method(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(dx_method=call.data[5:])
    await state.set_state(TopUp.amount)
    data = await state.get_data()
    await _show(call, f"Сколько сомони хотите пополнить?\nНапишите число, минимум <b>{esc(str(data.get('dx_min')))}</b>.",
                _kb([("‹ Отмена", "dx:home")]))
    await call.answer()


@router.message(TopUp.amount, F.text)
async def got_amount(message: Message, state: FSMContext) -> None:
    amount = message.text.replace(",", ".").replace(" ", "").strip()
    data = await state.get_data()
    try:
        res = await _call("POST", "/api/v1/payments", json={"method": data.get("dx_method", ""), "amount_tjs": amount})
    except DonatixError as exc:
        await message.answer(f"⚠️ {esc(str(exc))}\n\nВведите сумму ещё раз.", reply_markup=_kb([("‹ Отмена", "dx:home")]))
        return
    p = res["payment"]
    await state.update_data(dx_payment=p["id"])
    await state.set_state(None)
    await message.answer(
        f"🧾 <b>Заявка #{p['id']}</b> · {esc(p['method_title'])}\n\n"
        f"Переведите ровно <b>{esc(p['pay_amount'])} {esc(p['pay_currency'])}</b>\n"
        f"Будет зачислено: <b>${esc(p['amount_usd'])}</b>\n\n"
        f"<b>Реквизиты:</b>\n<code>{esc(p['details'])}</code>\n\n"
        "После перевода нажмите «Я оплатил» и пришлите чек.",
        reply_markup=_kb([("✅ Я оплатил", f"dx:paid:{p['id']}")], [("‹ Отмена", "dx:home")]),
    )


@router.callback_query(F.data.startswith("dx:paid:"))
async def paid(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(dx_payment=int(call.data.split(":")[2]))
    await state.set_state(TopUp.receipt)
    await _show(call, "📎 Пришлите чек — фото или PDF-файл перевода.", _kb([("‹ Отмена", "dx:home")]))
    await call.answer()


@router.message(TopUp.receipt, F.photo | F.document)
async def got_receipt(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    pid = data.get("dx_payment")
    if message.photo:
        file, name, ctype = message.photo[-1], "receipt.jpg", "image/jpeg"
    else:
        doc = message.document
        ctype = doc.mime_type or ""
        if ctype not in ("image/jpeg", "image/png", "image/webp", "application/pdf"):
            await message.answer("Нужен чек фото (JPG/PNG) или PDF.")
            return
        file, name = doc, doc.file_name or "receipt"
    if (file.file_size or 0) > MAX_RECEIPT:
        await message.answer("Файл больше 10 МБ — пришлите фото чека.")
        return
    buf = await bot.download(file)
    form = aiohttp.FormData()
    form.add_field("file", buf.read(), filename=name, content_type=ctype)
    try:
        await _call("POST", f"/api/v1/payments/{pid}/receipt", data=form)
    except DonatixError as exc:
        await message.answer(f"⚠️ Чек не отправлен: {esc(str(exc))}")
        return
    await state.clear()
    await message.answer("✅ Чек отправлен администратору Donatix. Как только оплату подтвердят, "
                         "баланс пополнится — проверить можно в /donatix.",
                         reply_markup=_kb([("🏦 Счёт Donatix", "dx:home")]))


@router.message(TopUp.receipt)
async def receipt_wrong(message: Message) -> None:
    await message.answer("Пришлите чек фото или файлом PDF. Отменить — /donatix.")


async def bootstrap(conn, provider) -> None:
    """Первый запуск бота из конструктора: курс доллара и все игры — сами."""
    import asyncio

    from app import runtime
    from app.services import autogames, suppliers
    from app.services import games as gsvc

    await asyncio.sleep(3)
    try:
        if runtime.usd_rate() <= 0:
            rate = (await _call("GET", "/api/v1/payments/methods")).get("tjs_rate")
            if rate:
                await runtime.set_value(conn, "usd_rate_diram", str(round(float(rate) * 100)))
                log.info("Donatix: курс доллара %s сомони", rate)
        from app import db
        if not await db.list_games(conn):
            catalog = await gsvc.full_catalog(suppliers.for_games(provider))
            added, enabled = await autogames.import_all(conn, catalog)
            log.info("Donatix: добавлено игр %s, включено %s", added, enabled)
    except Exception:  # noqa: BLE001 — бот работает и без этого, владелец добавит вручную
        log.exception("Donatix: первичная настройка не удалась")
