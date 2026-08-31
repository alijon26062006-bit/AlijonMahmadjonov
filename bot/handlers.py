"""Обработчики Telegram: голос, текст, фото, кнопки, команды."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.chat_action import ChatActionSender

from . import admin, db, keyboards, reports
from .access import is_admin
from .brain import Brain
from .config import Config
from .stt import Transcriber
from .tools import TurnResult

log = logging.getLogger(__name__)
router = Router()

HELP_TEXT = """\
Я запоминаю твои деньги и накладные. Говори голосом или пиши текстом — как удобно.

Записать:
 • «Сегодня отправил Абубакру три тысячи сомони»
 • «Оплатил за товар сумки, четыре места, 500 тысяч тенге»
 • «Дал Салиму в долг 2000 сомони, вернёт через 10 дней»

Спросить:
 • «Какие деньги я отправил Абубакру?»
 • «Какого числа я отправил деньги Абубакру?»
 • «Сколько я оплатил за сумки?»

Накладные:
 • Пришли фото → скажи «это накладная от женской обуви»
 • Потом: «Отправь накладную от женской обуви»

Отчёт:
 • «Отправь отчёт с 1 августа по сегодня»

Команды: /help — эта справка, /otchet — отчёт за текущий месяц,
/istoriya Абубакр — вся история по человеку, /imya — сменить своё имя.

Твои записи видишь только ты.\
"""

# Кого бот ждёт с уточнением после нажатия «Исправить». owner_id → transaction_id.
_pending_edits: dict[int, int] = {}


# ── регистрация ────────────────────────────────────────────────────────────

MIN_NAME, MAX_NAME = 2, 64

ASK_NAME = "Привет! Как тебя зовут?"
BAD_NAME = (
    f"Имя должно быть от {MIN_NAME} до {MAX_NAME} символов, без ссылок. "
    "Напиши, пожалуйста, ещё раз."
)


def clean_name(raw: str) -> str | None:
    """Принять имя или вернуть None. Имя попадёт в панель админа — мусор не нужен."""
    name = " ".join((raw or "").split())
    if not MIN_NAME <= len(name) <= MAX_NAME:
        return None
    lowered = name.lower()
    if any(bad in lowered for bad in ("http://", "https://", "t.me/", "<", ">")):
        return None
    return name


# ── общая отправка результата ──────────────────────────────────────────────

TG_TEXT_LIMIT = 4096
TG_CAPTION_LIMIT = 1024


def split_message(text: str, limit: int = TG_TEXT_LIMIT) -> list[str]:
    """Разбить длинный ответ на куски: Telegram не принимает больше 4096 символов.

    История операций за год легко перевалит за лимит, а Telegram в ответ просто
    вернёт ошибку — пользователь останется без ответа. Режем по строкам,
    чтобы не рвать записи посередине.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # одна строка длиннее лимита — режем жёстко
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


async def _deliver(
    message: Message, conn: sqlite3.Connection, owner_id: int, result: TurnResult
) -> None:
    """Отправить ответ, карточки сохранённых записей, фото и PDF."""

    if result.reply:
        first_tx = result.saved_transaction_ids[0] if len(result.saved_transaction_ids) == 1 else None
        chunks = split_message(result.reply)
        for index, chunk in enumerate(chunks):
            # Кнопки — только под последним куском, иначе они потеряются в середине.
            last = index == len(chunks) - 1
            await message.answer(
                chunk,
                reply_markup=(
                    keyboards.transaction_keyboard(first_tx) if last and first_tx else None
                ),
            )

    # Если операций несколько — кнопки для каждой отдельным сообщением.
    if len(result.saved_transaction_ids) > 1:
        for tx_id in result.saved_transaction_ids:
            row = db.get_transaction(conn, owner_id, tx_id)
            if row:
                await message.answer(
                    _tx_line(row), reply_markup=keyboards.transaction_keyboard(tx_id)
                )

    for doc_id in result.documents_to_send:
        doc = db.get_document(conn, owner_id, doc_id)
        if not doc:
            continue
        caption = (doc.get("description") or "Документ")[:TG_CAPTION_LIMIT]
        try:
            await message.answer_photo(doc["tg_file_id"], caption=caption)
        except Exception:
            # file_id мог протухнуть — шлём копию с диска.
            path = Path(doc["file_path"])
            if path.is_file():
                await message.answer_photo(FSInputFile(path), caption=caption)
            else:
                log.warning("Фото %s потеряно: %s", doc_id, path)
                await message.answer(f"Файл для «{caption}» не найден на диске.")

    for report_path in result.reports_to_send:
        if report_path.is_file():
            await message.answer_document(
                FSInputFile(report_path, filename=report_path.name),
                caption="Отчёт",
            )


def _tx_line(row: dict[str, Any]) -> str:
    amount = reports.fmt_money(row.get("amount"), row.get("currency"))
    parts = [reports.fmt_date(row.get("happened_on") or row["created_at"])]
    if row.get("counterparty"):
        parts.append(row["counterparty"])
    parts.append(amount)
    if row.get("item"):
        parts.append(f"за «{row['item']}»")
    return " · ".join(parts)


async def _process(
    message: Message,
    text: str,
    *,
    source: str,
    brain: Brain,
    conn: sqlite3.Connection,
    owner_id: int,
) -> None:
    editing_id = _pending_edits.pop(owner_id, None)

    # Пишем в журнал ДО обращения к Claude: если модель упадёт, сказанное не пропадёт.
    db.log_message(conn, owner_id, "user", text)

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            result = await brain.handle(
                owner_id, text, source=source, editing_transaction_id=editing_id
            )
    except Exception:
        log.exception("Ошибка при обработке сообщения")
        await message.answer(
            "Не смог обработать — что-то сломалось на моей стороне. "
            "Твои слова я записал, повтори через минуту."
        )
        return

    db.log_message(conn, owner_id, "assistant", result.reply)
    await _deliver(message, conn, owner_id, result)


# ── команды ────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(
    message: Message, conn: sqlite3.Connection, user: dict[str, Any], sender: Any
) -> None:
    if user["status"] == "active":
        name = user.get("name")
        greeting = f"С возвращением, {name}. " if name else "Привет. "
        await message.answer(greeting + HELP_TEXT)
        return

    # Приглашён, но ещё не представился — спрашиваем имя и запоминаем это в базе,
    # чтобы перезапуск бота не оставил человека в подвешенном состоянии.
    db.start_registration(conn, user["id"], getattr(sender, "username", None))
    suggested = getattr(sender, "first_name", None)
    text = ASK_NAME
    if suggested:
        text += f"\n\nМожно просто написать: {suggested}"
    await message.answer(text)


@router.message(Command("imya"))
async def cmd_rename(message: Message, conn: sqlite3.Connection, user: dict[str, Any]) -> None:
    name = clean_name((message.text or "").partition(" ")[2])
    if not name:
        await message.answer("Напиши так: /imya Алиджон")
        return
    db.rename_user(conn, user["id"], name)
    await message.answer(f"Теперь я зову тебя {name}.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("otchet"))
async def cmd_report(message: Message, brain: Brain, conn: sqlite3.Connection,
                     user: dict[str, Any]) -> None:
    today = date.today()
    first = today.replace(day=1)
    await _process(
        message,
        f"Сделай PDF-отчёт за период с {first.isoformat()} по {today.isoformat()}.",
        source="text", brain=brain, conn=conn, owner_id=user["id"],
    )


@router.message(Command("istoriya"))
async def cmd_history(message: Message, brain: Brain, conn: sqlite3.Connection,
                      user: dict[str, Any]) -> None:
    name = (message.text or "").partition(" ")[2].strip()
    if not name:
        await message.answer("Напиши так: /istoriya Абубакр")
        return
    await _process(
        message, f"Покажи всю историю операций с человеком: {name}",
        source="text", brain=brain, conn=conn, owner_id=user["id"],
    )


# ── голос ──────────────────────────────────────────────────────────────────

@router.message(F.voice | F.audio)
async def on_voice(
    message: Message, config: Config, brain: Brain, conn: sqlite3.Connection,
    stt: Transcriber, user: dict[str, Any]
) -> None:

    media = message.voice or message.audio
    duration = getattr(media, "duration", 0) or 0
    if duration > config.max_voice_seconds:
        await message.answer(
            f"Слишком длинное сообщение ({duration} сек). "
            f"Разбей на части покороче — до {config.max_voice_seconds} секунд."
        )
        return

    try:
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            buffer = await message.bot.download(media.file_id)
            audio = buffer.read()
            filename = getattr(media, "file_name", None) or "voice.ogg"
            text = await stt.transcribe(audio, filename=filename)
    except Exception:
        log.exception("Не удалось распознать голос")
        await message.answer("Не смог распознать голос. Попробуй записать ещё раз.")
        return

    if not text:
        await message.answer("Ничего не расслышал. Скажи, пожалуйста, ещё раз.")
        return

    await message.answer(f"🎙 {text}")
    await _process(message, text, source="voice", brain=brain, conn=conn, owner_id=user["id"])


# ── фото ───────────────────────────────────────────────────────────────────

@router.message(F.photo)
async def on_photo(
    message: Message, config: Config, brain: Brain, conn: sqlite3.Connection,
    user: dict[str, Any]
) -> None:

    photo = message.photo[-1]  # самое большое разрешение
    owner_id = user["id"]
    config.photos_dir.mkdir(parents=True, exist_ok=True)
    path = config.photos_dir / f"{owner_id}_{photo.file_unique_id}.jpg"

    try:
        await message.bot.download(photo.file_id, destination=path)
    except Exception:
        log.exception("Не удалось скачать фото")
        await message.answer("Не смог сохранить фото. Пришли ещё раз.")
        return

    doc_id = db.add_document(
        conn, owner_id, tg_file_id=photo.file_id, file_path=str(path)
    )
    log.info("Фото сохранено: id=%s → %s", doc_id, path)

    caption = (message.caption or "").strip()
    if caption:
        await _process(message, caption, source="text", brain=brain, conn=conn, owner_id=user["id"])
    else:
        await message.answer(
            "Фото сохранил. Скажи голосом или напиши, что это — например: "
            "«это накладная от женской обуви»."
        )


# ── кнопки ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith(keyboards.EDIT_PREFIX))
async def on_edit(query: CallbackQuery, conn: sqlite3.Connection, user: dict[str, Any]) -> None:
    tx_id = int(query.data.removeprefix(keyboards.EDIT_PREFIX))
    _pending_edits[user["id"]] = tx_id
    await query.answer()
    await query.message.answer(
        "Скажи или напиши, что исправить — например: «там было не 500, а 400 тысяч»."
    )


@router.callback_query(F.data.startswith(keyboards.DELETE_PREFIX))
async def on_delete(query: CallbackQuery, conn: sqlite3.Connection, user: dict[str, Any]) -> None:
    tx_id = int(query.data.removeprefix(keyboards.DELETE_PREFIX))
    ok = db.delete_transaction(conn, user["id"], tx_id)
    await query.answer("Удалил" if ok else "Не нашёл")
    if ok:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass  # сообщение слишком старое для правки — не беда
        await query.message.answer("Удалил эту запись.")


# ── обычный текст (регистрируется последним) ───────────────────────────────

@router.message(F.text)
async def on_text(
    message: Message,
    brain: Brain,
    conn: sqlite3.Connection,
    user: dict[str, Any],
    bot_username: str | None = None,
) -> None:
    # 1. Человек представляется — это его первое сообщение после Старта.
    if user["status"] == "awaiting_name":
        name = clean_name(message.text)
        if not name:
            await message.answer(BAD_NAME)
            return
        db.register_user(conn, user["id"], name)
        await message.answer(f"Приятно познакомиться, {name}.\n\n" + HELP_TEXT)
        return

    # 2. Владелец вводит id нового человека после кнопки «Добавить по ID».
    if is_admin(user) and await admin.handle_new_id(message, conn, user, bot_username):
        return

    await _process(message, message.text.strip(), source="text", brain=brain,
                   conn=conn, owner_id=user["id"])
