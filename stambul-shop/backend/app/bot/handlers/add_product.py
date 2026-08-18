"""Заведение товара прямо в боте: фото → раздел → цена → публикация.

Почему в боте, а не только на сайте: владелец добавляет товар с телефона,
стоя над коробкой, и снимать фотографию, а потом искать её в галерее
браузера — лишние движения. В переписке это один разговор: прислал
снимки, ответил на пять вопросов, посмотрел готовую карточку, нажал
«Опубликовать».

Модель здесь помощник, а не начальник: она предлагает название, раздел и
описание и готовит фотографию для каталога, но публикует только человек.
"""
import asyncio
import contextlib
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.catalog.schemas import all_categories, get_category
from app.config import get_settings
from app.db.models import P_ACTIVE, ProductPhoto, User
from app.imaging.style import BACKGROUNDS
from app.services import (
    ai_vision, categories as categories_service, product_service,
    settings_store,
)

router = Router()

PER_PAGE = 8
MAX_PHOTOS = 8


class Add(StatesGroup):
    photos = State()
    category = State()
    new_category = State()
    title = State()
    price = State()
    qty = State()
    description = State()
    confirm = State()


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cancel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="❌ Отмена", callback_data="add:cancel")]


def _skip_row(what: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="Пропустить — предложит ИИ",
                                 callback_data=f"add:skip:{what}")]


# ─────────────────────────── Начало ───────────────────────────

@router.message(Command("add"))
@router.message(F.text == texts.MENU_ADD)
async def start_add(message: Message, state: FSMContext, user: User) -> None:
    if not user.is_admin:
        await message.answer("Товары добавляет только владелец магазина.")
        return
    await state.clear()
    await state.set_state(Add.photos)
    await state.update_data(photos=[])
    await message.answer(
        "<b>Новый товар</b>\n\n"
        "Пришлите фотографии — можно несколько сразу, до "
        f"{MAX_PHOTOS} штук.\n"
        "Первая станет главной в карточке.",
        reply_markup=_kb([_cancel_row()]))


@router.message(Add.photos, F.photo)
async def take_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"Уже {MAX_PHOTOS} фотографий, хватит.")
        return

    best = message.photo[-1]
    thumb = next((p for p in message.photo if (p.width or 0) >= 400), best)
    photos.append({"file_id": best.file_id,
                   "thumb_file_id": thumb.file_id,
                   "thumb_w": thumb.width,
                   "file_unique_id": best.file_unique_id,
                   "width": best.width, "height": best.height})
    await state.update_data(photos=photos)

    # Альбом прилетает несколькими сообщениями подряд: показываем кнопку
    # один раз, иначе чат забивается одинаковыми подсказками.
    if message.media_group_id and len(photos) > 1:
        return
    await message.answer(
        f"Принято: {len(photos)}. Пришлите ещё или нажмите «Дальше».",
        reply_markup=_kb([[InlineKeyboardButton(text="Дальше →",
                                                callback_data="add:photos_done")],
                          _cancel_row()]))


@router.callback_query(F.data == "add:photos_done", Add.photos)
async def photos_done(cb: CallbackQuery, state: FSMContext,
                      session: AsyncSession) -> None:
    data = await state.get_data()
    if not data.get("photos"):
        await cb.answer("Сначала пришлите хотя бы одну фотографию",
                        show_alert=True)
        return
    await cb.answer()
    await _ask_category(cb.message, state, session, page=0)


# ─────────────────────────── Раздел ───────────────────────────

async def _ask_category(message: Message, state: FSMContext,
                        session: AsyncSession, page: int) -> None:
    await categories_service.sync(session)
    items = all_categories()
    pages = max(1, -(-len(items) // PER_PAGE))
    page = max(0, min(page, pages - 1))
    chunk = items[page * PER_PAGE:(page + 1) * PER_PAGE]

    rows = [[InlineKeyboardButton(text=c.title, callback_data=f"add:cat:{c.slug}")]
            for c in chunk]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="←", callback_data=f"add:page:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="→", callback_data=f"add:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="➕ Свой раздел",
                                      callback_data="add:cat_new")])
    rows.append(_cancel_row())

    await state.set_state(Add.category)
    await message.answer("Выберите раздел. Если подходящего нет — заведите свой.",
                         reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("add:page:"), Add.category)
async def category_page(cb: CallbackQuery, state: FSMContext,
                        session: AsyncSession) -> None:
    await cb.answer()
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await _ask_category(cb.message, state, session,
                        page=int(cb.data.rsplit(":", 1)[1]))


@router.callback_query(F.data.startswith("add:cat:"), Add.category)
async def category_chosen(cb: CallbackQuery, state: FSMContext) -> None:
    slug = cb.data.rsplit(":", 1)[1]
    category = get_category(slug)
    if category is None:
        await cb.answer("Такого раздела нет", show_alert=True)
        return
    await state.update_data(category=slug)
    await cb.answer()
    await _ask_title(cb.message, state, category.title)


@router.callback_query(F.data == "add:cat_new", Add.category)
async def category_new(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Add.new_category)
    await cb.answer()
    await cb.message.answer("Как назвать новый раздел? Например: «Спорттовары».",
                            reply_markup=_kb([_cancel_row()]))


@router.message(Add.new_category, F.text)
async def category_created(message: Message, state: FSMContext,
                           session: AsyncSession) -> None:
    try:
        category = await categories_service.create(session, message.text)
    except ValueError as error:
        await message.answer(str(error))
        return
    await state.update_data(category=category.slug)
    await message.answer(f"Раздел «{category.title}» создан.")
    await _ask_title(message, state, category.title)


# ─────────────────────────── Название, цена, количество ───────────────────

async def _ask_title(message: Message, state: FSMContext, category: str) -> None:
    await state.set_state(Add.title)
    await message.answer(
        f"Раздел: <b>{category}</b>\n\nКак называется товар?",
        reply_markup=_kb([_skip_row("title"), _cancel_row()]))


@router.message(Add.title, F.text)
async def take_title(message: Message, state: FSMContext) -> None:
    title = " ".join(message.text.split())[:160]
    if len(title) < 3:
        await message.answer("Слишком короткое название, напишите подробнее.")
        return
    await state.update_data(title=title)
    await _ask_price(message, state)


async def _ask_price(message: Message, state: FSMContext) -> None:
    await state.set_state(Add.price)
    sign = get_settings().currency_sign
    await message.answer(f"Цена в {sign}? Просто число, например 12990.",
                         reply_markup=_kb([_cancel_row()]))


@router.message(Add.price, F.text)
async def take_price(message: Message, state: FSMContext) -> None:
    raw = message.text.replace(" ", "").replace(",", ".")
    try:
        price = Decimal(raw)
    except InvalidOperation:
        await message.answer("Не понял цену. Напишите числом, например 12990.")
        return
    if price <= 0:
        await message.answer("Цена должна быть больше нуля.")
        return
    await state.update_data(price=str(price))
    await state.set_state(Add.qty)
    await message.answer("Сколько штук в наличии?",
                         reply_markup=_kb([_cancel_row()]))


@router.message(Add.qty, F.text)
async def take_qty(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("Напишите количество числом, например 5.")
        return
    await state.update_data(qty=int(raw))
    await state.set_state(Add.description)
    await message.answer(
        "Опишите товар своими словами — или пропустите, и описание "
        "предложит ИИ.",
        reply_markup=_kb([_skip_row("description"), _cancel_row()]))


@router.message(Add.description, F.text)
async def take_description(message: Message, state: FSMContext,
                           session: AsyncSession) -> None:
    await state.update_data(description=message.text.strip()[:2000])
    await _prepare(message, state, session)


@router.callback_query(F.data.startswith("add:skip:"))
async def skip_field(cb: CallbackQuery, state: FSMContext,
                     session: AsyncSession) -> None:
    what = cb.data.rsplit(":", 1)[1]
    await cb.answer()
    if what == "title":
        await state.update_data(title="")
        await _ask_price(cb.message, state)
    else:
        await state.update_data(description="")
        await _prepare(cb.message, state, session)




# ─────────────────────────── Полоса выполнения ───────────────────────────

BAR_CELLS = 12


class Progress:
    """Живая полоса в одном сообщении.

    Проценты честные: они привязаны к шагам, которые действительно
    завершились, а не к таймеру. Но между шагами бывает по десять-двадцать
    секунд тишины, и человеку в этот момент кажется, что всё зависло —
    поэтому рядом тикают секунды, и сообщение обновляется само.
    """

    def __init__(self, message: Message) -> None:
        self._message = message
        self._percent = 0
        self._label = "Начинаю"
        self._started = 0.0
        self._beat: asyncio.Task | None = None

    async def start(self) -> None:
        self._started = asyncio.get_running_loop().time()
        await self._draw()
        self._beat = asyncio.create_task(self._tick())

    async def set(self, percent: int, label: str) -> None:
        self._percent = max(self._percent, min(100, percent))
        self._label = label
        await self._draw()

    async def finish(self) -> None:
        if self._beat:
            self._beat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._beat
        with contextlib.suppress(Exception):
            await self._message.delete()

    async def _tick(self) -> None:
        # раз в четыре секунды: чаще Telegram начинает придерживать правки
        while True:
            await asyncio.sleep(4)
            await self._draw()

    def _seconds(self) -> int:
        return int(asyncio.get_running_loop().time() - self._started)

    async def _draw(self) -> None:
        filled = round(BAR_CELLS * self._percent / 100)
        bar = "▰" * filled + "▱" * (BAR_CELLS - filled)
        text = (f"<b>Готовлю карточку</b>\n\n"
                f"{bar}  {self._percent}%\n"
                f"{self._label} · {self._seconds()} с")
        with contextlib.suppress(Exception):
            await self._message.edit_text(text)


# ─────────────────────── Подготовка: фон и разбор ───────────────────────

async def _prepare(message: Message, state: FSMContext,
                   session: AsyncSession) -> None:
    """Готовит фотографию для каталога и просит у модели черновик карточки.

    Обе части необязательные: не настроен ключ или отвалилась сеть — товар
    всё равно можно опубликовать, просто без подсказок и с исходным снимком.
    """
    data = await state.get_data()
    photos = data.get("photos", [])
    note = await message.answer("Готовлю карточку…")
    bar = Progress(note)
    await bar.start()
    try:
        await _run(bar, message, state, session, photos, data)
    except Exception as error:                       # сеть, Telegram, что угодно
        await bar.finish()
        await message.answer(
            f"Не получилось подготовить карточку: {error}\n\n"
            "Товар не потерян — нажмите «Дальше», и попробуем ещё раз.",
            reply_markup=_kb([[InlineKeyboardButton(
                text="Попробовать ещё раз", callback_data="add:retry")],
                _cancel_row()]))


@router.callback_query(F.data == "add:retry")
async def retry_prepare(cb: CallbackQuery, state: FSMContext,
                        session: AsyncSession) -> None:
    await cb.answer()
    await _prepare(cb.message, state, session)


async def _run(bar, message: Message, state: FSMContext,
               session: AsyncSession, photos: list, data: dict) -> None:
    from app.api.deps import get_redis
    from app.imaging.pipeline import compose
    from app.services.telegram_files import get_photo_bytes

    redis = get_redis()
    originals: list[bytes] = []
    for index, photo in enumerate(photos, 1):
        await bar.set(5 + int(10 * index / max(len(photos), 1)),
                      f"Забираю фотографию {index} из {len(photos)}")
        raw = await get_photo_bytes(redis, photo["file_id"],
                                    photo["file_unique_id"])
        originals.append(raw or b"")

    # фон определяем по первому снимку и держим общим для всей серии,
    # иначе вид спереди окажется на светлом, а вид сбоку на сером
    processed: list[dict | None] = []
    background = data.get("background") or None
    problems: list[str] = []
    total = max(len(originals), 1)
    for index, raw in enumerate(originals):
        share = 15 + int(60 * index / total)
        await bar.set(share, f"Убираю фон · фото {index + 1} из {total}")
        if not raw:
            processed.append(None)
            continue
        try:
            result = await asyncio.to_thread(compose, raw, background=background)
            background = background or result.background
            await bar.set(share + int(30 / total), "Сохраняю обработанное фото")
            stored = await _upload(result.data)
            processed.append(stored)
        except Exception as error:
            processed.append(None)
            problems.append(f"фото {index + 1}: {error}")

    draft = {}
    ai_error = ""
    key, model = await settings_store.openai(session)
    if key and originals and originals[0]:
        await bar.set(80, "Смотрю, что на фотографии")
        try:
            draft = await ai_vision.analyze(originals[0], key, model)
        except ai_vision.VisionError as error:
            ai_error = str(error)
    elif not key:
        ai_error = "ключ OpenAI не задан в настройках"

    await bar.set(100, "Готово")
    await state.update_data(processed=processed, background=background,
                            draft=draft, ai_error=ai_error, problems=problems)
    await bar.finish()
    await _show_card(message, state, session)


async def _upload(data: bytes) -> dict:
    """Кладёт готовую картинку в чат-хранилище."""
    from app.bot.factory import create_bot

    s = get_settings()
    if not s.storage_chat_id:
        raise RuntimeError("не настроен чат-хранилище")
    bot = create_bot()
    try:
        message = await bot.send_photo(
            chat_id=s.storage_chat_id,
            photo=BufferedInputFile(data, filename="catalog.jpg"))
    finally:
        await bot.session.close()
    best = message.photo[-1]
    thumb = next((p for p in message.photo if (p.width or 0) >= 400), best)
    return {"file_id": best.file_id, "thumb_file_id": thumb.file_id,
            "thumb_w": thumb.width, "file_unique_id": best.file_unique_id}


# ─────────────────────────── Карточка и публикация ───────────────────────

def _money(value) -> str:
    return f"{round(float(value)):,}".replace(",", " ")


async def _show_card(message: Message, state: FSMContext,
                     session: AsyncSession) -> None:
    data = await state.get_data()
    draft = data.get("draft") or {}
    category = get_category(data.get("category", ""))
    title = data.get("title") or draft.get("title") or "—"
    description = data.get("description") or draft.get("description") or ""
    sign = get_settings().currency_sign

    lines = [f"<b>{title}</b>",
             f"Раздел: {category.title if category else '—'}",
             f"Цена: {_money(data.get('price', 0))} {sign}",
             f"В наличии: {data.get('qty', 0)} шт."]
    if description:
        lines += ["", description[:600]]

    hints = []
    if draft.get("title") and draft["title"] != data.get("title"):
        hints.append(f"название: «{draft['title']}»")
    if draft.get("category") and draft["category"] != data.get("category"):
        suggested = get_category(draft["category"])
        if suggested:
            hints.append(f"раздел: {suggested.title}")
    if draft.get("description") and not data.get("description"):
        hints.append("описание готово")
    if draft.get("color"):
        hints.append(f"цвет: {draft['color']}")
    if hints:
        lines += ["", "🤖 <i>ИИ предлагает — " + "; ".join(hints) + "</i>"]
    if draft.get("uncertain"):
        lines.append("<i>Не уверен: " + ", ".join(draft["uncertain"]) + "</i>")
    if data.get("ai_error"):
        lines += ["", f"<i>Разбор не сработал: {data['ai_error']}</i>"]
    if data.get("problems"):
        lines += ["", "<i>Фон не сделан — " + "; ".join(data["problems"])[:200]
                  + "</i>"]

    rows = []
    take = []
    if draft.get("title") and draft["title"] != data.get("title"):
        take.append(InlineKeyboardButton(text="Название ИИ",
                                         callback_data="add:take:title"))
    if draft.get("description") and draft["description"] != data.get("description"):
        take.append(InlineKeyboardButton(text="Описание ИИ",
                                         callback_data="add:take:description"))
    if draft.get("category") and draft["category"] != data.get("category"):
        take.append(InlineKeyboardButton(text="Раздел ИИ",
                                         callback_data="add:take:category"))
    for i in range(0, len(take), 2):
        rows.append(take[i:i + 2])

    rows.append([InlineKeyboardButton(
        text=f"🖼 Фон: {BACKGROUNDS[data['background']].title}"
             if data.get("background") in BACKGROUNDS else "🖼 Фон: исходный",
        callback_data="add:bg")])
    rows.append([InlineKeyboardButton(text="✅ Опубликовать",
                                      callback_data="add:publish")])
    rows.append(_cancel_row())

    await state.set_state(Add.confirm)
    caption = "\n".join(lines)[:1024]
    shot = next((p for p in (data.get("processed") or []) if p), None)
    if shot:
        await message.answer_photo(shot["file_id"], caption=caption,
                                   reply_markup=_kb(rows))
    else:
        await message.answer(caption, reply_markup=_kb(rows))


@router.callback_query(F.data.startswith("add:take:"), Add.confirm)
async def take_suggestion(cb: CallbackQuery, state: FSMContext,
                          session: AsyncSession) -> None:
    what = cb.data.rsplit(":", 1)[1]
    data = await state.get_data()
    draft = data.get("draft") or {}
    if draft.get(what):
        await state.update_data(**{what: draft[what]})
    await cb.answer("Взял")
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await _show_card(cb.message, state, session)


@router.callback_query(F.data == "add:bg", Add.confirm)
async def cycle_background(cb: CallbackQuery, state: FSMContext,
                           session: AsyncSession) -> None:
    """Перебор фонов по кругу. Каждый раз пересобираем кадр заново."""
    order = list(BACKGROUNDS)
    data = await state.get_data()
    current = data.get("background")
    nxt = order[(order.index(current) + 1) % len(order)] if current in order \
        else order[0]
    await state.update_data(background=nxt)
    await cb.answer("Пересобираю фон…")
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await _prepare(cb.message, state, session)


@router.callback_query(F.data == "add:publish", Add.confirm)
async def publish(cb: CallbackQuery, state: FSMContext,
                  session: AsyncSession, user: User) -> None:
    if not user.is_admin:
        await cb.answer("Только владелец", show_alert=True)
        return
    data = await state.get_data()
    draft = data.get("draft") or {}
    title = data.get("title") or draft.get("title") or ""
    description = data.get("description") or draft.get("description") or ""
    category = data.get("category") or draft.get("category") or ""

    if not get_category(category):
        await cb.answer("Раздел потерялся, начните заново", show_alert=True)
        return

    await cb.answer("Публикую…")
    attrs = {}
    for key in ("color", "material", "season", "style"):
        if draft.get(key):
            attrs[key] = draft[key]

    try:
        product = await product_service.create(
            session, category_slug=category, title=title,
            description=description, brand=draft.get("brand") or None,
            attrs=attrs)
        await product_service.set_variants(session, product, [{
            "size": "", "color": draft.get("color", ""),
            "price": data["price"], "stock": int(data.get("qty", 0)),
        }])
    except product_service.ShopError as error:
        await cb.message.answer(f"Не вышло: {error}")
        return

    for position, (photo, done) in enumerate(
            zip(data.get("photos", []), data.get("processed", []))):
        session.add(ProductPhoto(
            product_id=product.id, position=position,
            file_id=photo["file_id"], thumb_file_id=photo.get("thumb_file_id"),
            thumb_w=photo.get("thumb_w"),
            file_unique_id=photo["file_unique_id"],
            width=photo.get("width"), height=photo.get("height"),
            proc_file_id=(done or {}).get("file_id"),
            proc_thumb_file_id=(done or {}).get("thumb_file_id"),
            proc_thumb_w=(done or {}).get("thumb_w"),
            proc_file_unique_id=(done or {}).get("file_unique_id"),
            use_processed=bool(done),
            background=data.get("background") if done else None,
            processing="ready" if done else "none"))
    await session.commit()

    fresh = await product_service.load(session, product.id)
    await product_service.refresh(session, fresh)

    await state.clear()
    link = f"{get_settings().site_url.rstrip('/')}/p/{product.public_id}"
    status = "в продаже" if fresh.status == P_ACTIVE else "черновик"
    await cb.message.answer(
        f"✅ <b>{title}</b> — {status}\n{link}\n\n"
        "Размеры и цвета можно добавить на сайте: Управление → Товары.",
        reply_markup=_kb([[InlineKeyboardButton(text="➕ Ещё товар",
                                                callback_data="add:more")]]))


@router.callback_query(F.data == "add:more")
async def add_more(cb: CallbackQuery, state: FSMContext, user: User) -> None:
    await cb.answer()
    await start_add(cb.message, state, user)


@router.callback_query(F.data == "add:cancel")
async def cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.answer("Отменил")
    with contextlib.suppress(Exception):
        await cb.message.delete()
    await cb.message.answer("Добавление отменено.")
