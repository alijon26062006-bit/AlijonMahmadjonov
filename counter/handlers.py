"""Вся логика общения с человеком.

Сообщения шлём обычным текстом, без разметки: тогда никакое имя
(со скобками, кавычками или «<») не может сломать вывод.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from . import db, keyboards as kb, reports
from .config import Config
from .numbers import SCALE, Found, format_amount, parse_numbers
from .stt import Recognizer, VoiceError

log = logging.getLogger(__name__)
router = Router(name="counter")

HELP = (
    "Как пользоваться\n"
    "\n"
    "1. Нажми «➕ Человек» и напиши имя. Так заводятся все, кому считаем.\n"
    "2. Нажми на имя внизу — оно станет с галочкой ✅. Это тот, кому пишем сейчас.\n"
    "3. Отправляй голосовые: «семь шестьсот», «пять четыреста». Бот сложит сам.\n"
    "   Можно и просто написать цифрами: 7600.\n"
    "4. Ошибся — под каждой записью есть «✏️ Исправить» и «🗑 Удалить».\n"
    "5. «📊 Отчёт» — пришлёт Excel или PDF: каждая запись по отдельности\n"
    "   и общая сумма в конце.\n"
    "\n"
    "Бот слышит только числа, слова он пропускает.\n"
    "Работает без интернета и без платных ключей.\n"
    "\n"
    "Команды: /start /help /people /list /report /new /undo /cancel"
)


# ── Мелкие помощники ───────────────────────────────────────────────────────
def chat_title(message: Message) -> str:
    chat = message.chat
    return (chat.title or chat.full_name or "Счёт товара")[:80]


def keyboard_for(conn: sqlite3.Connection, chat_id: int):
    chat = db.ensure_chat(conn, chat_id)
    return kb.main_keyboard(db.list_workers(conn, chat_id), chat["active_worker_id"])


def local_time(config: Config, value: str | None) -> str:
    moment = db.parse_time(value)
    return moment.astimezone(config.tz).strftime("%H:%M") if moment else "—"


def local_datetime(config: Config, value: str | None) -> str:
    moment = db.parse_time(value)
    return moment.astimezone(config.tz).strftime("%d.%m.%Y %H:%M") if moment else "—"


def entry_card(conn: sqlite3.Connection, config: Config, entry: sqlite3.Row, note: str = "") -> str:
    worker = db.get_worker(conn, entry["worker_id"])
    count, total = db.worker_stats(conn, entry["worker_id"], entry["session_id"])
    all_count, all_total = db.grand_total(conn, entry["chat_id"], entry["session_id"])
    unit = config.unit_name

    head = "🗑 Удалено" if entry["deleted"] else (note or "✅ Записал")
    lines = [
        f"{head}   ·   {worker['name'] if worker else '—'}",
        f"{'−' if entry['deleted'] else '+'} {format_amount(entry['amount'])} {unit}"
        + (f"   ·   услышал: «{entry['raw_text']}»" if entry["raw_text"] else ""),
        "",
        f"👤 У него: {format_amount(total)} {unit}   ({count} зап.)",
        f"📦 Всего в смене: {format_amount(all_total)} {unit}   ({all_count} зап.)",
    ]
    return "\n".join(lines)


async def send_entry(message: Message, conn, config: Config, entry: sqlite3.Row, note: str = "") -> None:
    await message.answer(
        entry_card(conn, config, entry, note),
        reply_markup=kb.entry_keyboard(entry["id"], bool(entry["deleted"])),
    )


def stash(conn, chat_id: int, raw: str, values: list[Found], kind: str = "choice") -> None:
    db.set_pending(
        conn,
        chat_id,
        kind,
        json.dumps({"raw": raw, "values": [f.value for f in values]}, ensure_ascii=False),
    )


def take_stash(conn, chat_id: int) -> dict | None:
    kind, payload = db.get_pending(conn, chat_id)
    if kind != "choice" or not payload:
        return None
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return None


# ── Ядро: записать число ───────────────────────────────────────────────────
async def store(
    message: Message,
    conn,
    config: Config,
    worker: sqlite3.Row,
    value: int,
    raw: str,
    source: str,
    author_id: int | None,
) -> None:
    session = db.current_session(conn, message.chat.id, config.tz)
    entry = db.add_entry(
        conn,
        chat_id=message.chat.id,
        session_id=session["id"],
        worker_id=worker["id"],
        amount=value,
        raw_text=raw,
        source=source,
        author_id=author_id,
    )
    db.set_pending(conn, message.chat.id, None)
    await send_entry(message, conn, config, entry)


async def offer_numbers(
    message: Message, conn, config: Config, values: list[Found], raw: str, source: str
) -> None:
    """Число распознано — решаем, кому и сколько записать."""
    chat_id = message.chat.id
    workers = db.list_workers(conn, chat_id)
    worker = db.active_worker(conn, chat_id)

    if not workers:
        stash(conn, chat_id, raw, values)
        await message.answer(
            "Пока не заведён ни один человек — некому записывать.\n"
            "Нажми «➕ Человек» и напиши имя, потом повтори число.",
            reply_markup=keyboard_for(conn, chat_id),
        )
        return

    if worker is None:
        stash(conn, chat_id, raw, values)
        labels = ", ".join(format_amount(found.value) for found in values)
        await message.answer(
            f"Услышал: {labels}\nКому записать?",
            reply_markup=kb.choose_worker_keyboard(
                workers, "0" if len(values) == 1 else "ask"
            ),
        )
        return

    if len(values) > 1:
        stash(conn, chat_id, raw, values)
        await message.answer(
            f"Услышал сразу несколько чисел: {', '.join(format_amount(f.value) for f in values)}\n"
            f"Какое записать {worker['name']}?",
            reply_markup=kb.choose_number_keyboard(
                [format_amount(found.value) for found in values], worker["id"]
            ),
        )
        return

    await store_checked(message, conn, config, worker, values[0].value, raw, source)


async def store_checked(
    message: Message, conn, config: Config, worker: sqlite3.Row, value: int, raw: str, source: str
) -> None:
    """Проверки на глупости — и запись."""
    chat_id = message.chat.id
    if value <= 0:
        db.set_pending(conn, chat_id, None)
        await message.answer(
            f"Число получилось {format_amount(value)} — так не бывает. Скажи ещё раз.",
            reply_markup=kb.manual_input_keyboard(),
        )
        return

    if value > config.max_amount * SCALE:
        stash(conn, chat_id, raw, [Found(value, raw)])
        await message.answer(
            f"Слишком большое число: {format_amount(value)} {config.unit_name}.\n"
            "Может, я ослышался? Подтверди или скажи заново.",
            reply_markup=kb.confirm_keyboard(worker["id"], value, format_amount(value)),
        )
        return

    twin = db.recent_duplicate(conn, worker["id"], value, config.duplicate_window_seconds)
    if twin is not None:
        stash(conn, chat_id, raw, [Found(value, raw)])
        await message.answer(
            f"Такое же число ({format_amount(value)}) уже записано {worker['name']} "
            f"минуту назад в {local_time(config, twin['created_at'])}.\n"
            "Это правда ещё одна коробка или случайно два раза?",
            reply_markup=kb.confirm_keyboard(worker["id"], value, format_amount(value)),
        )
        return

    await store(message, conn, config, worker, value, raw, source, message.from_user.id if message.from_user else None)


# ── Команды и кнопки меню ──────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, conn, config: Config) -> None:
    db.ensure_chat(conn, message.chat.id, chat_title(message))
    session = db.current_session(conn, message.chat.id, config.tz)
    db.set_pending(conn, message.chat.id, None)
    workers = db.list_workers(conn, message.chat.id)
    hello = (
        "Привет! Я считаю товар голосом.\n"
        f"Смена: {session['title']}\n\n"
    )
    hello += (
        "Начни с кнопки «➕ Человек» — заведи тех, кому считаем."
        if not workers
        else "Выбери человека внизу и присылай голосовые с числами."
    )
    await message.answer(hello + "\n\n" + HELP, reply_markup=keyboard_for(conn, message.chat.id))


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message, conn, config: Config) -> None:
    await message.answer(HELP, reply_markup=keyboard_for(conn, message.chat.id))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, conn, config: Config) -> None:
    db.set_pending(conn, message.chat.id, None)
    await message.answer("Отменил. Можно дальше.", reply_markup=keyboard_for(conn, message.chat.id))


@router.message(Command("add"))
async def cmd_add(message: Message, conn, config: Config) -> None:
    name = (message.text or "").partition(" ")[2].strip()
    if not name:
        db.set_pending(conn, message.chat.id, "add_worker")
        await message.answer("Напиши имя человека одним сообщением.")
        return
    await add_worker_named(message, conn, config, name)


@router.message(F.text == kb.BTN_ADD_WORKER)
async def btn_add_worker(message: Message, conn, config: Config) -> None:
    db.set_pending(conn, message.chat.id, "add_worker")
    await message.answer("Напиши имя человека одним сообщением. Например: Иброхим")


async def add_worker_named(message: Message, conn, config: Config, name: str) -> None:
    worker, status = db.add_worker(conn, message.chat.id, name)
    db.set_pending(conn, message.chat.id, None)
    if status == "bad_name":
        db.set_pending(conn, message.chat.id, "add_worker")
        await message.answer("Пустое имя. Напиши ещё раз, например: Иброхим")
        return

    if worker is not None:
        db.set_active_worker(conn, message.chat.id, worker["id"])
    texts = {
        "created": f"Добавил: {worker['name']}. Теперь пишу ему.",
        "restored": f"Вернул в список: {worker['name']}. Теперь пишу ему.",
        "exists": f"{worker['name']} уже есть в списке. Теперь пишу ему.",
    }
    await message.answer(texts[status], reply_markup=keyboard_for(conn, message.chat.id))


@router.message(Command("people", "workers"))
@router.message(F.text == kb.BTN_WORKERS)
async def cmd_people(message: Message, conn, config: Config) -> None:
    workers = db.list_workers(conn, message.chat.id)
    if not workers:
        db.set_pending(conn, message.chat.id, "add_worker")
        await message.answer("Список пуст. Напиши имя первого человека.")
        return
    session = db.current_session(conn, message.chat.id, config.tz)
    lines = ["👥 Люди в смене:", ""]
    for worker in workers:
        count, total = db.worker_stats(conn, worker["id"], session["id"])
        lines.append(f"{worker['name']} — {format_amount(total)} {config.unit_name} ({count} зап.)")
    await message.answer("\n".join(lines), reply_markup=kb.workers_keyboard(workers))


@router.message(Command("list"))
@router.message(F.text == kb.BTN_LIST)
async def cmd_list(message: Message, conn, config: Config) -> None:
    await message.answer(session_report_text(conn, config, message.chat.id),
                         reply_markup=keyboard_for(conn, message.chat.id))


def session_report_text(conn, config: Config, chat_id: int) -> str:
    session = db.current_session(conn, chat_id, config.tz)
    rows = db.summary(conn, chat_id, session["id"])
    unit = config.unit_name
    lines = [f"📋 {session['title']}", ""]
    any_entries = False
    for row in rows:
        if row["count"] == 0:
            lines.append(f"👤 {row['name']} — пусто")
            continue
        any_entries = True
        lines.append(f"👤 {row['name']} — {format_amount(row['total'])} {unit} ({row['count']} зап.)")
        items = db.entries(conn, chat_id, session["id"], worker_id=row["worker_id"])
        shown = items[-12:]
        if len(items) > len(shown):
            lines.append(f"    … ещё {len(items) - len(shown)} раньше")
        lines.append("    " + "  ".join(format_amount(item["amount"]) for item in shown))
    count, total = db.grand_total(conn, chat_id, session["id"])
    lines.append("")
    lines.append(f"📦 ВСЕГО: {format_amount(total)} {unit}   ·   {count} записей")
    if not any_entries:
        lines.append("")
        lines.append("Пока ничего не записано. Отправь голосовое с числом.")
    return "\n".join(lines)


@router.message(Command("report"))
@router.message(F.text == kb.BTN_REPORT)
async def cmd_report(message: Message, conn, config: Config) -> None:
    await message.answer(
        session_report_text(conn, config, message.chat.id) + "\n\nКакой файл прислать?",
        reply_markup=kb.report_keyboard(),
    )


@router.message(Command("new"))
@router.message(F.text == kb.BTN_NEW_SESSION)
async def cmd_new_session(message: Message, conn, config: Config) -> None:
    count, total = db.grand_total(conn, message.chat.id, db.current_session(conn, message.chat.id, config.tz)["id"])
    await message.answer(
        f"Закрыть смену и начать новую?\n"
        f"Сейчас в ней {format_amount(total)} {config.unit_name} ({count} зап.).\n"
        "Старые записи никуда не денутся — они останутся в отчёте «за всё время».",
        reply_markup=kb.confirm_new_session_keyboard(),
    )


@router.message(Command("undo"))
@router.message(F.text == kb.BTN_UNDO)
async def cmd_undo(message: Message, conn, config: Config) -> None:
    session = db.current_session(conn, message.chat.id, config.tz)
    entry = db.last_entry(conn, message.chat.id, session["id"])
    if entry is None:
        await message.answer("В этой смене ещё нечего отменять.",
                             reply_markup=keyboard_for(conn, message.chat.id))
        return
    db.set_deleted(conn, entry["id"], True)
    await send_entry(message, conn, config, db.get_entry(conn, entry["id"]), note="↩️ Отменил последнюю запись")


# ── Переключение человека кнопкой ──────────────────────────────────────────
@router.message(F.text.func(lambda text: kb.worker_button_name(text or "") is not None))
async def switch_worker(message: Message, conn, config: Config) -> None:
    name = kb.worker_button_name(message.text or "") or ""
    key = db.name_key(name)
    worker = next(
        (w for w in db.list_workers(conn, message.chat.id) if db.name_key(w["name"]) == key), None
    )
    if worker is None:
        await message.answer(
            f"Не нашёл человека «{name}». Обнови список кнопкой «👥 Люди».",
            reply_markup=keyboard_for(conn, message.chat.id),
        )
        return
    db.set_active_worker(conn, message.chat.id, worker["id"])
    db.set_pending(conn, message.chat.id, None)
    session = db.current_session(conn, message.chat.id, config.tz)
    count, total = db.worker_stats(conn, worker["id"], session["id"])
    await message.answer(
        f"📍 Пишу: {worker['name']}\n"
        f"Сейчас у него {format_amount(total)} {config.unit_name} ({count} зап.)\n"
        "Присылай голосовые с числами.",
        reply_markup=keyboard_for(conn, message.chat.id),
    )


# ── Голос ──────────────────────────────────────────────────────────────────
@router.message(F.voice | F.audio | F.video_note)
async def on_voice(message: Message, bot: Bot, conn, config: Config, recognizer: Recognizer) -> None:
    media = message.voice or message.audio or message.video_note
    duration = getattr(media, "duration", 0) or 0
    if duration > config.max_voice_seconds:
        await message.answer(
            f"Голосовое длинное ({duration} сек). Говори одно число за раз — так точнее."
        )
        return

    if not recognizer.ready:
        await recognizer.prepare()
    if not recognizer.ready:
        await message.answer(
            "Голосовой движок не готов.\n" + (recognizer.problem or "") +
            "\n\nПока можно писать числа цифрами — я всё запишу.",
            reply_markup=keyboard_for(conn, message.chat.id),
        )
        return

    waiting = await message.answer("🎧 Слушаю…")
    try:
        buffer = io.BytesIO()
        await bot.download(media, destination=buffer)
        text = await recognizer.recognize_async(buffer.getvalue())
    except VoiceError as exc:
        await waiting.delete()
        await message.answer(str(exc), reply_markup=kb.manual_input_keyboard())
        return
    except Exception:
        log.exception("Голосовое не обработалось")
        await waiting.delete()
        await message.answer(
            "Не смог разобрать это голосовое. Запиши ещё раз или напиши число цифрами.",
            reply_markup=kb.manual_input_keyboard(),
        )
        return
    await waiting.delete()

    kind, payload = db.get_pending(conn, message.chat.id)
    if kind and kind.startswith("edit:"):
        await apply_edit(message, conn, config, kind.split(":", 1)[1], text, "voice")
        return

    values = parse_numbers(text)
    if not values:
        heard = f"Услышал: «{text}»\n" if text else ""
        await message.answer(
            heard + "Числа не разобрал. Скажи только число, например: «семь шестьсот».\n"
            "Или напиши цифрами.",
            reply_markup=kb.manual_input_keyboard(),
        )
        return

    await offer_numbers(message, conn, config, values, text, "voice")


# ── Текст ──────────────────────────────────────────────────────────────────
@router.message(F.text)
async def on_text(message: Message, conn, config: Config) -> None:
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    kind, _ = db.get_pending(conn, message.chat.id)

    if kind == "add_worker":
        await add_worker_named(message, conn, config, text)
        return

    if kind and kind.startswith("rename:"):
        worker_id = int(kind.split(":", 1)[1])
        status = db.rename_worker(conn, worker_id, text)
        db.set_pending(conn, message.chat.id, None)
        answers = {
            "ok": f"Готово. Теперь это {db.clean_name(text)}.",
            "exists": "Такое имя уже занято. Попробуй другое: нажми «👥 Люди».",
            "bad_name": "Пустое имя, ничего не поменял.",
            "missing": "Этого человека уже нет в списке.",
        }
        await message.answer(answers[status], reply_markup=keyboard_for(conn, message.chat.id))
        return

    if kind and kind.startswith("edit:"):
        await apply_edit(message, conn, config, kind.split(":", 1)[1], text, "text")
        return

    values = parse_numbers(text)
    if not values:
        await message.answer(
            "Это не число. Напиши цифрами (7600) или скажи голосом.\n"
            "Меню — кнопками внизу, подсказка — «❓ Помощь».",
            reply_markup=keyboard_for(conn, message.chat.id),
        )
        return

    await offer_numbers(message, conn, config, values, text, "text")


async def apply_edit(message: Message, conn, config: Config, entry_id: str, text: str, source: str) -> None:
    entry = db.get_entry(conn, int(entry_id)) if entry_id.isdigit() else None
    if entry is None:
        db.set_pending(conn, message.chat.id, None)
        await message.answer("Эта запись куда-то делась. Ничего не менял.")
        return

    values = parse_numbers(text)
    if len(values) != 1:
        hint = "Не разобрал число." if not values else "Услышал несколько чисел."
        await message.answer(f"{hint} Скажи или напиши одно число — на что исправить.")
        return

    value = values[0].value
    if value <= 0:
        await message.answer("Число должно быть больше нуля. Скажи ещё раз.")
        return

    db.update_entry(conn, entry["id"], value, text)
    db.set_pending(conn, message.chat.id, None)
    await send_entry(message, conn, config, db.get_entry(conn, entry["id"]), note="✏️ Исправил")


# ── Нажатия на кнопки под сообщениями ──────────────────────────────────────
@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, conn, config: Config) -> None:
    chat_id = callback.message.chat.id if callback.message else None
    if chat_id is not None:
        db.set_pending(conn, chat_id, None)
    await callback.answer("Отменил")
    if callback.message:
        await safe_edit_markup(callback.message)


async def safe_edit_markup(message: Message, markup=None) -> None:
    """Убрать (или заменить) кнопки, не падая, если Телеграм против."""
    try:
        await message.edit_reply_markup(reply_markup=markup)
    except Exception as exc:  # noqa: BLE001 — сообщение старое или уже без кнопок
        log.debug("Кнопки не поменялись: %s", exc)


@router.callback_query(F.data == "manual")
async def cb_manual(callback: CallbackQuery, conn, config: Config) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer("Напиши число цифрами, например: 7600")


@router.callback_query(F.data.startswith("e:"))
async def cb_entry(callback: CallbackQuery, conn, config: Config) -> None:
    _, action, raw_id = (callback.data or "").split(":", 2)
    if not raw_id.isdigit():
        await callback.answer("Не понял кнопку")
        return
    entry = db.get_entry(conn, int(raw_id))
    message = callback.message
    if entry is None or message is None:
        await callback.answer("Запись не найдена")
        return

    if action == "edit":
        db.set_pending(conn, message.chat.id, f"edit:{entry['id']}")
        await callback.answer("Жду новое число")
        worker = db.get_worker(conn, entry["worker_id"])
        await message.answer(
            f"Что записать вместо {format_amount(entry['amount'])} "
            f"({worker['name'] if worker else '—'})?\n"
            "Скажи голосом или напиши цифрами. Отменить — /cancel"
        )
        return

    if action in ("del", "res"):
        deleted = action == "del"
        db.set_deleted(conn, entry["id"], deleted)
        fresh = db.get_entry(conn, entry["id"])
        await callback.answer("Удалил" if deleted else "Вернул")
        try:
            await message.edit_text(
                entry_card(conn, config, fresh, note="↩️ Вернул" if not deleted else ""),
                reply_markup=kb.entry_keyboard(entry["id"], deleted),
            )
        except Exception:  # noqa: BLE001 — не вышло исправить старое, шлём новое
            await send_entry(message, conn, config, fresh)


@router.callback_query(F.data.startswith("add:"))
async def cb_add(callback: CallbackQuery, conn, config: Config) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return
    _, raw_worker, index = (callback.data or "").split(":", 2)
    worker = db.get_worker(conn, int(raw_worker)) if raw_worker.isdigit() else None
    stashed = take_stash(conn, message.chat.id)
    if worker is None or not stashed:
        await callback.answer("Кнопка устарела — скажи число заново", show_alert=True)
        await safe_edit_markup(message)
        return

    values: list[int] = [int(v) for v in stashed.get("values", [])]
    raw = str(stashed.get("raw", ""))

    if index == "ask":
        # Человека выбрали — теперь спросим, какое из услышанных чисел писать.
        db.set_active_worker(conn, message.chat.id, worker["id"])
        await callback.answer()
        await safe_edit_markup(message)
        await message.answer(
            f"Какое число записать {worker['name']}?",
            reply_markup=kb.choose_number_keyboard(
                [format_amount(value) for value in values], worker["id"]
            ),
        )
        return

    if index == "all":
        chosen = values
    elif index.isdigit() and int(index) < len(values):
        chosen = [values[int(index)]]
    else:
        chosen = []

    if not chosen:
        await callback.answer("Нечего записывать")
        return

    db.set_active_worker(conn, message.chat.id, worker["id"])
    db.set_pending(conn, message.chat.id, None)
    await callback.answer("Записал")
    await safe_edit_markup(message)
    for value in chosen:
        await store(message, conn, config, worker, value, raw, "voice",
                    callback.from_user.id if callback.from_user else None)


@router.callback_query(F.data.startswith("force:"))
async def cb_force(callback: CallbackQuery, conn, config: Config) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return
    _, raw_worker, raw_value = (callback.data or "").split(":", 2)
    worker = db.get_worker(conn, int(raw_worker)) if raw_worker.isdigit() else None
    if worker is None or not raw_value.lstrip("-").isdigit():
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    stashed = take_stash(conn, message.chat.id) or {}
    db.set_pending(conn, message.chat.id, None)
    await callback.answer("Записал")
    await safe_edit_markup(message)
    await store(message, conn, config, worker, int(raw_value), str(stashed.get("raw", "")),
                "voice", callback.from_user.id if callback.from_user else None)


@router.callback_query(F.data.startswith("w:"))
async def cb_worker(callback: CallbackQuery, conn, config: Config) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    action = parts[1]
    worker_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    chat_id = message.chat.id

    if action == "add":
        db.set_pending(conn, chat_id, "add_worker")
        await callback.answer()
        await message.answer("Напиши имя человека одним сообщением.")
        return

    if action == "list":
        workers = db.list_workers(conn, chat_id)
        await callback.answer()
        await safe_edit_markup(message, kb.workers_keyboard(workers))
        return

    worker = db.get_worker(conn, worker_id)
    if worker is None:
        await callback.answer("Человек не найден", show_alert=True)
        return

    if action == "menu":
        count, total = db.worker_stats(conn, worker["id"], db.current_session(conn, chat_id, config.tz)["id"])
        await callback.answer()
        try:
            await message.edit_text(
                f"👤 {worker['name']}\n"
                f"В этой смене: {format_amount(total)} {config.unit_name} ({count} зап.)",
                reply_markup=kb.worker_menu_keyboard(worker["id"]),
            )
        except Exception:  # noqa: BLE001
            await message.answer(f"👤 {worker['name']}", reply_markup=kb.worker_menu_keyboard(worker["id"]))
        return

    if action == "set":
        db.set_active_worker(conn, chat_id, worker["id"])
        await callback.answer(f"Пишу: {worker['name']}")
        await message.answer(f"📍 Пишу: {worker['name']}", reply_markup=keyboard_for(conn, chat_id))
        return

    if action == "ren":
        db.set_pending(conn, chat_id, f"rename:{worker['id']}")
        await callback.answer()
        await message.answer(f"Как теперь звать «{worker['name']}»? Напиши новое имя.")
        return

    if action == "arch":
        db.archive_worker(conn, worker["id"])
        await callback.answer("Убрал из списка")
        await message.answer(
            f"{worker['name']} убран из списка. Записи остались в отчётах — "
            "если добавить его снова с тем же именем, всё вернётся.",
            reply_markup=keyboard_for(conn, chat_id),
        )


@router.callback_query(F.data.startswith("s:new"))
async def cb_new_session(callback: CallbackQuery, conn, config: Config) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return
    if (callback.data or "") == "s:new":
        await callback.answer()
        await message.answer(
            "Закрыть смену и начать новую?", reply_markup=kb.confirm_new_session_keyboard()
        )
        return

    session = db.start_session(conn, message.chat.id, tz=config.tz)
    db.set_pending(conn, message.chat.id, None)
    await callback.answer("Новая смена")
    await safe_edit_markup(message)
    await message.answer(
        f"🔄 Начал новую смену: {session['title']}\n"
        "Счёт у всех с нуля. Прошлые записи целы — они в отчёте «за всё время».",
        reply_markup=keyboard_for(conn, message.chat.id),
    )


# ── Отчёты ─────────────────────────────────────────────────────────────────
def collect_report(conn, config: Config, chat_id: int, scope: str) -> reports.ReportData:
    chat = db.ensure_chat(conn, chat_id)
    session = db.current_session(conn, chat_id, config.tz)
    session_id = session["id"] if scope == "now" else None

    if scope == "now":
        title = session["title"]
        period = f"начало {local_datetime(config, session['started_at'])}"
    else:
        title = "За всё время"
        first = conn.execute(
            "SELECT created_at FROM entries WHERE chat_id=? AND deleted=0 ORDER BY id LIMIT 1",
            (chat_id,),
        ).fetchone()
        period = f"с {local_datetime(config, first['created_at'])}" if first else "записей пока нет"

    rows = [row for row in db.summary(conn, chat_id, session_id)]
    items = db.entries(conn, chat_id, session_id)
    return reports.ReportData(
        chat_title=chat["title"] or "Счёт товара",
        session_title=title,
        period=period,
        unit=config.unit_name,
        rows=rows,
        entries=[
            {
                "n": number,
                "name": item["worker_name"],
                "amount": item["amount"],
                "time": local_datetime(config, item["created_at"]),
                "note": item["raw_text"] + (" (исправлено)" if item["edited"] else ""),
            }
            for number, item in enumerate(items, start=1)
        ],
        generated_at=datetime.now(config.tz),
    )


@router.callback_query(F.data.startswith("rep:"))
async def cb_report(callback: CallbackQuery, conn, config: Config) -> None:
    message = callback.message
    if message is None:
        await callback.answer()
        return
    parts = (callback.data or "").split(":")
    scope = parts[1] if len(parts) > 1 else "now"
    kind = parts[2] if len(parts) > 2 else "xlsx"

    await callback.answer("Готовлю файл…")
    data = collect_report(conn, config, message.chat.id, scope)
    if not data.entries:
        await message.answer("Записей нет — отчёт получится пустой. Сначала запиши хоть одно число.")
        return

    wanted = ["xlsx", "pdf"] if kind == "both" else [kind]
    for one in wanted:
        try:
            if one == "xlsx":
                blob = await asyncio.to_thread(reports.build_xlsx, data)
                filename, caption = data.file_stem + ".xlsx", "📗 Excel"
            else:
                blob = await asyncio.to_thread(reports.build_pdf, data)
                filename, caption = data.file_stem + ".pdf", "📕 PDF"
        except Exception:  # noqa: BLE001
            log.exception("Отчёт %s не собрался", one)
            await message.answer(
                f"Не получилось сделать {one.upper()}. Данные целы — попробуй другой формат."
            )
            continue

        await message.answer_document(
            BufferedInputFile(blob, filename=filename),
            caption=(
                f"{caption} · {data.session_title}\n"
                f"Всего: {format_amount(data.total)} {config.unit_name} · {data.count} записей"
            ),
        )
