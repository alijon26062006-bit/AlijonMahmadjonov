"""Универсальный мастер подачи объявления.

Один набор хендлеров проходит ЛЮБУЮ категорию: шаги, валидация, клавиатуры
и предпросмотр строятся из схемы. Новая категория не требует правок здесь.
"""
import re
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from aiogram.utils.media_group import MediaGroupBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.db.models import City, District, Listing, User
from app.schemas_engine.fields import DIRECTIONS, CategorySchema, FieldSpec
from app.schemas_engine.registry import (
    OTHER, get_schema, option_label, categories_tree, render_title, resolve_options,
)
from app.services import identifiers, listing_service
from app.services.publisher import build_caption

router = Router()
PAGE = 8


class Wiz(StatesGroup):
    flow = State()


# ─────────────────────────── Клавиатуры ───────────────────────────

def nav_row(spec: FieldSpec | None, first: bool) -> list[InlineKeyboardButton]:
    row = []
    if not first:
        row.append(InlineKeyboardButton(text=texts.BTN_BACK, callback_data="w:b"))
    if spec is not None and not spec.required:
        row.append(InlineKeyboardButton(text=texts.BTN_SKIP, callback_data="w:s"))
    row.append(InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="w:x"))
    return row


def options_kb(options: list[tuple[str, str]], spec: FieldSpec, page: int,
               selected: list[str], first: bool,
               auto_value: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if auto_value:
        rows.append([InlineKeyboardButton(
            text=f"✅ {auto_value} (определено автоматически)", callback_data="w:auto")])
    start = page * PAGE
    for i, (value, label) in enumerate(options[start:start + PAGE], start=start):
        mark = "☑️ " if value in selected else ""
        cb = f"w:m:{i}" if spec.type == "enum_many" else f"w:o:{i}"
        rows.append([InlineKeyboardButton(text=f"{mark}{label}", callback_data=cb)])
    if len(options) > PAGE:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="‹", callback_data=f"w:p:{page-1}"))
        nav.append(InlineKeyboardButton(
            text=f"{page+1}/{(len(options)-1)//PAGE+1}", callback_data="w:none"))
        if start + PAGE < len(options):
            nav.append(InlineKeyboardButton(text="›", callback_data=f"w:p:{page+1}"))
        rows.append(nav)
    if spec.type == "enum_many":
        rows.append([InlineKeyboardButton(text=texts.BTN_DONE, callback_data="w:md")])
    rows.append(nav_row(spec, first))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text_kb(spec: FieldSpec, first: bool,
            auto_value: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if auto_value:
        rows.append([InlineKeyboardButton(
            text=f"✅ {auto_value} (определено автоматически)", callback_data="w:auto")])
    rows.append(nav_row(spec, first))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─────────────────────────── Показ шага ───────────────────────────

async def show_step(bot: Bot, chat_id: int, state: FSMContext,
                    session: AsyncSession) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    idx: int = data["idx"]
    fields = schema.fields
    values: dict = data["values"]

    # пропускаем поля, скрытые условной видимостью
    while idx < len(fields) and not schema.visible(fields[idx], values):
        idx += 1
    if idx >= len(fields):
        await state.update_data(idx=idx)
        await show_preview(bot, chat_id, state, session)
        return
    await state.update_data(idx=idx, page=0, multi=values.get(fields[idx].key) or [])

    spec = fields[idx]
    first = not data.get("hist")
    step_no = f"Шаг {idx + 1} из {len(fields)}"
    title = f"<b>{spec.label}</b>"
    hint = f"\n<i>{spec.hint}</i>" if spec.hint else ""
    auto_val = None
    if (a := values.get("_auto", {}).get(spec.key)) is not None:
        auto_val = str(a)

    if spec.type in ("enum_one", "enum_many"):
        options = await resolve_options(session, spec, values)
        if not options:                                   # пустой справочник — пропуск
            await state.update_data(idx=idx + 1)
            await show_step(bot, chat_id, state, session)
            return
        kb = options_kb(options, spec, 0, list(values.get(spec.key) or []), first)
        await _render(bot, chat_id, state, f"{step_no}\n{title}{hint}", kb)
    elif spec.type == "bool":
        options = [("true", "Да"), ("false", "Нет")]
        kb = options_kb(options, spec, 0, [], first)
        await _render(bot, chat_id, state, f"{step_no}\n{title}{hint}", kb)
    elif spec.type == "geo":
        await state.update_data(anchor=None)
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=texts.BTN_SHARE_LOCATION, request_location=True)],
            [KeyboardButton(text=texts.BTN_SKIP), KeyboardButton(text=texts.BTN_CANCEL)],
        ], resize_keyboard=True, one_time_keyboard=True)
        await bot.send_message(chat_id, f"{step_no}\n{title}\n{texts.SEND_LOCATION}",
                               reply_markup=kb)
    elif spec.type == "photos":
        await state.update_data(anchor=None)
        n = len(values.get("photos") or [])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=texts.BTN_DONE, callback_data="w:pd")],
            nav_row(None, first),
        ])
        await bot.send_message(
            chat_id, f"{step_no}\n{title}{hint}\n\n"
                     + texts.PHOTOS_COUNTER.format(n=n, max=10),
            reply_markup=kb)
    else:                                                 # текстовый ввод
        kb = text_kb(spec, first, auto_val)
        await _render(bot, chat_id, state, f"{step_no}\n{title}{hint}", kb)


async def _render(bot: Bot, chat_id: int, state: FSMContext,
                  text: str, kb: InlineKeyboardMarkup) -> None:
    """Редактирует якорное сообщение мастера, чтобы не засорять чат."""
    data = await state.get_data()
    anchor = data.get("anchor")
    if anchor:
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=anchor,
                                        reply_markup=kb)
            return
        except Exception:
            pass
    msg = await bot.send_message(chat_id, text, reply_markup=kb)
    await state.update_data(anchor=msg.message_id)


async def save_and_next(bot: Bot, chat_id: int, state: FSMContext,
                        session: AsyncSession, value) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    idx = data["idx"]
    values = data["values"]
    spec = schema.fields[idx]
    values[spec.key] = value

    if data.get("edit_return"):
        await state.update_data(values=values, edit_return=False,
                                idx=len(schema.fields))
        await show_preview(bot, chat_id, state, session)
        return

    hist = data.get("hist", [])
    hist.append(idx)
    await state.update_data(values=values, hist=hist, idx=idx + 1, other_for=None)
    await show_step(bot, chat_id, state, session)


# ─────────────────────── Старт мастера ───────────────────────

@router.message(F.text == texts.MENU_POST)
@router.message(Command("add"))
async def start_wizard(message: Message, state: FSMContext) -> None:
    await state.clear()
    rows = [[InlineKeyboardButton(text=f"{d.emoji} {d.title}",
                                  callback_data=f"w:dir:{d.slug}")]
            for d in DIRECTIONS]
    rows.append([InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="w:x")])
    await message.answer(texts.CHOOSE_DIRECTION,
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("w:dir:"))
async def pick_direction(cb: CallbackQuery, state: FSMContext) -> None:
    slug = cb.data.split(":")[2]
    tree = next((d for d in categories_tree() if d["slug"] == slug), None)
    if not tree:
        await cb.answer()
        return
    rows = [[InlineKeyboardButton(text=f"{c['emoji']} {c['title']}",
                                  callback_data=f"w:cat:{c['slug']}")]
            for c in tree["categories"]]
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK, callback_data="w:dirs"),
                 InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="w:x")])
    await cb.message.edit_text(
        texts.CHOOSE_CATEGORY.format(emoji=tree["emoji"], title=tree["title"]),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data == "w:dirs")
async def back_to_directions(cb: CallbackQuery, state: FSMContext) -> None:
    rows = [[InlineKeyboardButton(text=f"{d.emoji} {d.title}",
                                  callback_data=f"w:dir:{d.slug}")]
            for d in DIRECTIONS]
    rows.append([InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="w:x")])
    await cb.message.edit_text(texts.CHOOSE_DIRECTION,
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("w:cat:"))
async def pick_category(cb: CallbackQuery, state: FSMContext,
                        session: AsyncSession, bot: Bot) -> None:
    slug = cb.data.split(":")[2]
    if not get_schema(slug):
        await cb.answer()
        return
    await state.set_state(Wiz.flow)
    await state.set_data({"slug": slug, "idx": 0, "values": {}, "hist": [],
                          "anchor": cb.message.message_id})
    await cb.answer()
    await show_step(bot, cb.message.chat.id, state, session)


# ─────────────────────── Callback'и шагов ───────────────────────

@router.callback_query(Wiz.flow, F.data == "w:none")
async def noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(Wiz.flow, F.data.startswith("w:p:"))
async def paginate(cb: CallbackQuery, state: FSMContext,
                   session: AsyncSession) -> None:
    page = int(cb.data.split(":")[2])
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    options = await resolve_options(session, spec, data["values"])
    kb = options_kb(options, spec, page, list(data.get("multi") or []),
                    not data.get("hist"))
    await state.update_data(page=page)
    try:
        await cb.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


@router.callback_query(Wiz.flow, F.data.startswith("w:o:"))
async def pick_option(cb: CallbackQuery, state: FSMContext,
                      session: AsyncSession, bot: Bot) -> None:
    i = int(cb.data.split(":")[2])
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    if spec.type == "bool":
        await cb.answer()
        await save_and_next(bot, cb.message.chat.id, state, session, i == 0)
        return
    options = await resolve_options(session, spec, data["values"])
    if i >= len(options):
        await cb.answer("Кнопка устарела", show_alert=True)
        return
    value = options[i][0]
    await cb.answer()
    if value == OTHER:
        await state.update_data(other_for=spec.key)
        await _render(bot, cb.message.chat.id, state,
                      f"<b>{spec.label}</b>\nНапишите свой вариант текстом:",
                      text_kb(spec, not data.get("hist")))
        return
    await save_and_next(bot, cb.message.chat.id, state, session, value)


@router.callback_query(Wiz.flow, F.data.startswith("w:m:"))
async def toggle_multi(cb: CallbackQuery, state: FSMContext,
                       session: AsyncSession) -> None:
    i = int(cb.data.split(":")[2])
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    options = await resolve_options(session, spec, data["values"])
    if i >= len(options):
        await cb.answer()
        return
    value = options[i][0]
    multi = list(data.get("multi") or [])
    multi.remove(value) if value in multi else multi.append(value)
    await state.update_data(multi=multi)
    kb = options_kb(options, spec, data.get("page", 0), multi, not data.get("hist"))
    try:
        await cb.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


@router.callback_query(Wiz.flow, F.data == "w:md")
async def multi_done(cb: CallbackQuery, state: FSMContext,
                     session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    multi = list(data.get("multi") or [])
    if spec.required and not multi:
        await cb.answer("Выберите хотя бы один вариант", show_alert=True)
        return
    await cb.answer()
    await save_and_next(bot, cb.message.chat.id, state, session, multi or None)


@router.callback_query(Wiz.flow, F.data == "w:auto")
async def accept_auto(cb: CallbackQuery, state: FSMContext,
                      session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    value = data["values"].get("_auto", {}).get(spec.key)
    await cb.answer()
    if value is None:
        return
    await save_and_next(bot, cb.message.chat.id, state, session, value)


@router.callback_query(Wiz.flow, F.data == "w:s")
async def skip_step(cb: CallbackQuery, state: FSMContext,
                    session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    if spec.required:
        await cb.answer("Это поле обязательно", show_alert=True)
        return
    await cb.answer()
    await save_and_next(bot, cb.message.chat.id, state, session, None)


@router.callback_query(Wiz.flow, F.data == "w:b")
async def go_back(cb: CallbackQuery, state: FSMContext,
                  session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    hist = data.get("hist", [])
    await cb.answer()
    if not hist:
        await cancel_flow(cb.message, state, edit=True)
        return
    idx = hist.pop()
    await state.update_data(hist=hist, idx=idx, edit_return=False)
    await show_step(bot, cb.message.chat.id, state, session)


@router.callback_query(F.data == "w:x")
async def cancel_cb(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await cancel_flow(cb.message, state, edit=True)


@router.message(Command("cancel"))
@router.message(F.text == texts.BTN_CANCEL)
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOT_IN_WIZARD)
        return
    await cancel_flow(message, state, edit=False)


async def cancel_flow(message: Message, state: FSMContext, edit: bool) -> None:
    await state.clear()
    from app.bot.handlers.start import main_menu_kb
    if edit:
        try:
            await message.edit_text(texts.CANCELLED)
        except Exception:
            pass
        await message.answer("Главное меню:", reply_markup=main_menu_kb())
    else:
        await message.answer(texts.CANCELLED, reply_markup=main_menu_kb())


# ─────────────────────── Ввод: текст, фото, гео, контакт ───────────────────────

URL_RE = re.compile(r"(https?://\S+|t\.me/\S+|@\w{4,})", re.I)


def parse_text(spec: FieldSpec, raw: str) -> tuple[bool, object | str]:
    """(ok, значение) либо (False, текст ошибки)."""
    raw = raw.strip()
    if spec.type == "int":
        digits = re.sub(r"[  ]", "", raw)
        if not re.fullmatch(r"-?\d+", digits):
            return False, "Введите число, например: 120"
        v = int(digits)
    elif spec.type == "decimal":
        norm = re.sub(r"[  ]", "", raw).replace(",", ".")
        try:
            v = float(norm)
        except ValueError:
            return False, "Введите число, например: 2.5"
    elif spec.type == "money":
        currency = "USD" if "$" in raw else "TJS"
        digits = re.sub(r"[^\d.]", "", raw.replace(",", "."))
        try:
            amount = Decimal(digits)
        except InvalidOperation:
            return False, "Введите цену числом, например: 45000 или 4200$"
        if amount <= 0 or amount > Decimal("1000000000000"):
            return False, "Цена вне допустимого диапазона"
        return True, {"amount": str(amount), "currency": currency}
    elif spec.type in ("string", "text"):
        v = URL_RE.sub("", raw).strip()
        if spec.max_len and len(v) > spec.max_len:
            return False, f"Слишком длинно — максимум {spec.max_len} символов, сейчас {len(v)}"
        if spec.min and len(v) < int(spec.min):
            return False, f"Слишком коротко — минимум {int(spec.min)} символов"
        if not v and spec.required:
            return False, "Отправьте текст"
        return True, v
    elif spec.type == "identifier":
        ok, normalized, err, auto = identifiers.validate(spec.identifier or "serial", raw)
        if not ok:
            return False, err or "Номер не распознан"
        return True, {"value": normalized, "auto": auto}
    else:
        return False, "Используйте кнопки выше"

    if spec.min is not None and v < spec.min:
        return False, f"Минимум — {spec.min:g}"
    if spec.max is not None and v > spec.max:
        return False, f"Максимум — {spec.max:g}"
    return True, v


@router.message(Wiz.flow, F.photo)
async def on_photos(message: Message, state: FSMContext, session: AsyncSession,
                    bot: Bot, album: list[Message] | None = None) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]
    if spec.type != "photos":
        await message.answer("Сейчас нужно ответить на вопрос выше 👆")
        return
    values = data["values"]
    photos: list[dict] = list(values.get("photos") or [])
    seen = {p["file_unique_id"] for p in photos}
    overflow = False
    for m in (album or [message]):
        if not m.photo:
            continue
        best, thumb = m.photo[-1], m.photo[0]
        if best.file_unique_id in seen:
            continue
        if len(photos) >= 10:
            overflow = True
            break
        photos.append({"file_id": best.file_id, "thumb_file_id": thumb.file_id,
                       "file_unique_id": best.file_unique_id,
                       "width": best.width, "height": best.height})
        seen.add(best.file_unique_id)
    values["photos"] = photos
    await state.update_data(values=values)
    note = texts.PHOTOS_LIMIT.format(max=10) + "\n" if overflow else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_DONE, callback_data="w:pd")],
        nav_row(None, False),
    ])
    await message.answer(note + texts.PHOTOS_COUNTER.format(n=len(photos), max=10),
                         reply_markup=kb)


@router.message(Wiz.flow, F.document)
async def on_document(message: Message) -> None:
    await message.answer(texts.PHOTOS_AS_FILE)


@router.callback_query(Wiz.flow, F.data == "w:pd")
async def photos_done(cb: CallbackQuery, state: FSMContext,
                      session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    if not (data["values"].get("photos")):
        await cb.answer(texts.PHOTOS_NEED_ONE, show_alert=True)
        return
    await cb.answer()
    await save_and_next(bot, cb.message.chat.id, state, session,
                        data["values"]["photos"])


@router.message(Wiz.flow, F.location)
async def on_location(message: Message, state: FSMContext, session: AsyncSession,
                      bot: Bot) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    if schema.fields[data["idx"]].type != "geo":
        return
    values = data["values"]
    values["lat"] = message.location.latitude
    values["lon"] = message.location.longitude
    await state.update_data(values=values)
    await message.answer("📍 Точка сохранена", reply_markup=ReplyKeyboardRemove())
    await save_and_next(bot, message.chat.id, state, session, True)


@router.message(Wiz.flow, F.contact)
async def on_contact(message: Message, state: FSMContext, session: AsyncSession,
                     bot: Bot, user: User) -> None:
    phone = message.contact.phone_number
    if phone and not phone.startswith("+"):
        phone = "+" + phone
    user.phone = phone
    await session.commit()
    data = await state.get_data()
    values = data["values"]
    values["contact_phone"] = phone
    await state.update_data(values=values, await_phone=False)
    await message.answer("📞 Номер сохранён", reply_markup=ReplyKeyboardRemove())
    await show_preview(bot, message.chat.id, state, session)


@router.message(Wiz.flow, F.text)
async def on_text(message: Message, state: FSMContext, session: AsyncSession,
                  bot: Bot) -> None:
    if message.text == texts.BTN_SKIP:
        data = await state.get_data()
        schema = get_schema(data["slug"])
        spec = schema.fields[data["idx"]]
        if spec.required:
            await message.answer("Это поле обязательно")
            return
        await message.answer("Пропущено", reply_markup=ReplyKeyboardRemove())
        await save_and_next(bot, message.chat.id, state, session, None)
        return

    data = await state.get_data()
    schema = get_schema(data["slug"])
    spec = schema.fields[data["idx"]]

    # ручной ввод после «Другое»
    if data.get("other_for") == spec.key:
        value = message.text.strip()[:80]
        if len(value) < 1:
            await message.answer("Отправьте текст")
            return
        await save_and_next(bot, message.chat.id, state, session, value)
        return

    if spec.type in ("enum_one", "enum_many", "bool", "photos", "geo"):
        if spec.type == "geo":
            await message.answer(texts.SEND_LOCATION)
        else:
            await message.answer("Используйте кнопки выше 👆")
        return

    ok, result = parse_text(spec, message.text)
    if not ok:
        await message.answer(f"⚠️ {result}\n\nПопробуйте ещё раз:")
        return

    values = data["values"]
    if spec.type == "money":
        values["currency"] = result["currency"]
        await state.update_data(values=values)
        await save_and_next(bot, message.chat.id, state, session, result["amount"])
        return
    if spec.type == "identifier":
        auto = result["auto"]
        merged = values.get("_auto", {})
        merged.update({k: v for k, v in auto.items() if k not in ("tac", "brand_hint")})
        values["_auto"] = merged
        await state.update_data(values=values)
        note = ""
        if auto.get("brand_hint"):
            note = "\n" + texts.VALUE_SAVED_AUTO.format(v=auto["brand_hint"])
        if auto.get("year"):
            note += "\n" + texts.VALUE_SAVED_AUTO.format(v=f"год {auto['year']}")
        if note:
            await message.answer("✅ Номер принят" + note)
        await save_and_next(bot, message.chat.id, state, session, result["value"])
        return
    await save_and_next(bot, message.chat.id, state, session, result)


# ─────────────────────── Предпросмотр и отправка ───────────────────────

async def show_preview(bot: Bot, chat_id: int, state: FSMContext,
                       session: AsyncSession) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    values = data["values"]

    # телефон нужен, а его нет — спросим до предпросмотра
    if values.get("contact_mode") in ("phone", "both") and not values.get("contact_phone"):
        from sqlalchemy import select
        from app.db.models import User as U
        # телефон мог быть сохранён ранее
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text=texts.BTN_SHARE_CONTACT, request_contact=True)],
            [KeyboardButton(text=texts.BTN_CANCEL)],
        ], resize_keyboard=True, one_time_keyboard=True)
        await state.update_data(await_phone=True, anchor=None)
        await bot.send_message(chat_id, texts.SEND_CONTACT, reply_markup=kb)
        return

    listing = _draft_listing(schema, values)
    city = await session.get(City, listing.city_id) if listing.city_id else None
    district = await session.get(District, listing.district_id) if listing.district_id else None
    caption = build_caption(listing, schema,
                            city.name if city else None,
                            district.name if district else None)

    photos = values.get("photos") or []
    if photos:
        builder = MediaGroupBuilder()
        for i, p in enumerate(photos[:10]):
            builder.add_photo(media=p["file_id"],
                              caption=caption if i == 0 else None,
                              parse_mode="HTML" if i == 0 else None)
        await bot.send_media_group(chat_id, media=builder.build())

    editable = [(i, f) for i, f in enumerate(schema.fields)
                if f.type not in ("photos", "geo") and schema.visible(f, values)]
    kb_rows = [[InlineKeyboardButton(text=texts.BTN_SUBMIT, callback_data="w:sub")],
               [InlineKeyboardButton(text=texts.BTN_EDIT, callback_data="w:elist"),
                InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="w:x")]]
    msg = await bot.send_message(chat_id, texts.PREVIEW_HEADER,
                                 reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await state.update_data(anchor=msg.message_id,
                            editable=[i for i, _ in editable])


def _draft_listing(schema: CategorySchema, values: dict) -> Listing:
    """Несохранённый Listing для предпросмотра — тем же кодом, что и канал."""
    labels = {f.key: option_label(f, values.get(f.key))
              for f in schema.fields if values.get(f.key) is not None}
    price = Decimal(str(values.get("price") or 0))
    listing = Listing(
        title=render_title(schema, values, labels),
        description=str(values.get("description") or ""),
        price=price, currency=str(values.get("currency", "TJS")),
        price_usd=price, is_negotiable=bool(values.get("is_negotiable")),
        city_id=int(values["city_id"]) if values.get("city_id") else None,
        district_id=int(values["district_id"]) if values.get("district_id") else None,
        address=values.get("address"),
        attrs={k: v for k, v in values.items() if not k.startswith("_")},
    )
    return listing


@router.callback_query(Wiz.flow, F.data == "w:elist")
async def edit_list(cb: CallbackQuery, state: FSMContext,
                    session: AsyncSession) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    values = data["values"]
    rows = []
    for i in data.get("editable", [])[:24]:
        spec = schema.fields[i]
        current = option_label(spec, values.get(spec.key)) or "—"
        rows.append([InlineKeyboardButton(
            text=f"{spec.label}: {current[:24]}", callback_data=f"w:e:{i}")])
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK, callback_data="w:ep")])
    try:
        await cb.message.edit_text("Что изменить?",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        pass
    await cb.answer()


@router.callback_query(Wiz.flow, F.data == "w:ep")
async def back_to_preview(cb: CallbackQuery, state: FSMContext,
                          session: AsyncSession, bot: Bot) -> None:
    await cb.answer()
    await state.update_data(anchor=None)
    await show_preview(bot, cb.message.chat.id, state, session)


@router.callback_query(Wiz.flow, F.data.startswith("w:e:"))
async def edit_field(cb: CallbackQuery, state: FSMContext,
                     session: AsyncSession, bot: Bot) -> None:
    idx = int(cb.data.split(":")[2])
    await state.update_data(idx=idx, edit_return=True)
    await cb.answer()
    await show_step(bot, cb.message.chat.id, state, session)


@router.callback_query(Wiz.flow, F.data == "w:sub")
async def submit(cb: CallbackQuery, state: FSMContext, session: AsyncSession,
                 bot: Bot, user: User) -> None:
    data = await state.get_data()
    schema = get_schema(data["slug"])
    values = data["values"]
    try:
        listing = await listing_service.create_listing(
            session, user, schema, values, values.get("photos") or [])
    except listing_service.LimitExceeded as e:
        await cb.answer()
        await cb.message.edit_text(texts.LIMIT_REACHED.format(msg=e))
        await state.clear()
        return
    await cb.answer("Отправлено!")
    await state.clear()
    from app.bot.handlers.start import main_menu_kb
    await cb.message.edit_text(texts.SUBMITTED)
    await cb.message.answer("Что дальше?", reply_markup=main_menu_kb())

    from app.bot.handlers.moderation import send_to_moderation
    await send_to_moderation(bot, session, listing)
