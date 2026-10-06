"""Подключение к Telegram и очередь уведомлений.

Юзербот входит в Telegram как человек — под вашим номером. Отсюда три
правила, которые здесь соблюдаются:

  1. Разбираются сообщения ровно от одного источника, заданного в
     BANK_BOT. Всё остальное — чужая переписка, и юзербот её не трогает.

  2. Только новые сообщения. История не читается: там лежат уже
     оплаченные заявки, и один проход по ней зачислил бы всё заново.

  3. Обработка строго по одному. Два уведомления одновременно могли бы
     занять одну и ту же заявку, поэтому они выстраиваются в очередь.

Падать юзербот не должен вообще: он крутится сутками, и интернет за это
время пропадает не раз. Поэтому обрыв связи — не ошибка, а ожидаемое
событие, после которого он ждёт и подключается снова.
"""
from __future__ import annotations

import asyncio
import contextlib
import re

from app import db
from app.config import settings
from app.userbot import processor
from app.userbot.log import get, setup

log = get()

#: Пауза перед новой попыткой подключения. Растёт, чтобы не долбить
#: Telegram, когда интернета нет совсем.
RETRY_MIN = 5
RETRY_MAX = 300

#: После скольких неудач подряд зовём владельца.
#:
#: Юзербот переподключается сам, и обрыв связи на минуту — обычное дело,
#: беспокоить из-за него незачем. Но сессию могут и отозвать («Завершить
#: все сеансы» в Telegram), и тогда он будет молча стучаться в закрытую
#: дверь сутками, пока владелец не заметит, что оплаты перестали
#: подтверждаться. Пять неудач подряд — это уже не связь.
ALERT_AFTER = 5

#: Сколько уведомлений держим в очереди. Больше — значит что-то совсем
#: не так, и лишние лучше потерять, чем съесть всю память.
QUEUE = 100


def source_name() -> str:
    """Кого слушаем. Юзернейм без собачки или числовой id."""
    return (settings.bank_bot or "").strip().lstrip("@")


def sources(raw: str | None = None) -> tuple[set[int], set[str]]:
    """BANK_BOT → (числовые id, юзернеймы).

    Пишут его по-разному: «dc_next_bot», «@dc_next_bot», «1996047418» или
    сразу «dc_next_bot,1996047418». Последний вариант раньше читался как
    один юзернейм с запятой — такого бота нет, и юзербот молча пропускал
    все уведомления банка, хотя был подключён и выглядел исправным.
    """
    ids, names = set(), set()
    text = settings.bank_bot if raw is None else raw
    for part in re.split(r"[\s,;]+", text or ""):
        part = part.strip().lstrip("@")
        if not part:
            continue
        if part.lstrip("-").isdigit():
            ids.add(int(part))
        else:
            names.add(part.lower())
    return ids, names


def _from_source(message, wanted_ids, wanted_names) -> bool:
    """Это точно наш банковский бот?

    Сверяем и по id, и по юзернейму: id надёжнее (юзернейм можно
    перехватить, если банк его освободит), но задать в настройках проще
    юзернейм. Совпасть должно хоть что-то.

    Для совместимости принимает и одиночные значения: id числом и имя
    строкой.
    """
    if isinstance(wanted_ids, int):
        wanted_ids = {wanted_ids} if wanted_ids else set()
    if isinstance(wanted_names, str):
        wanted_ids_extra, wanted_names = sources(wanted_names)
        wanted_ids = set(wanted_ids) | wanted_ids_extra
    sender_id = getattr(message, "sender_id", None)
    if sender_id is not None and sender_id in wanted_ids:
        return True
    if wanted_names:
        sender = getattr(message, "sender", None)
        name = (getattr(sender, "username", "") or "").lower()
        if name and name in wanted_names:
            return True
    return False


async def _drain(queue: asyncio.Queue, bot) -> None:
    """Разбирает очередь по одному уведомлению за раз.

    Своё соединение с базой: задача живёт всё время работы юзербота,
    а чужое соединение может закрыться под ней.
    """
    conn = await db.connect()
    try:
        while True:
            message_id, text = await queue.get()
            try:
                await processor.handle(
                    conn, bot, source=source_name(),
                    message_id=message_id, text=text,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — одно кривое
                # уведомление не должно останавливать остальные
                log.exception("[USERBOT] Обработка сорвалась: %s", exc)
            finally:
                # Соединение живёт часами. Транзакция, зависшая после
                # упавшей вставки, держала бы замок до следующей оплаты —
                # и всё это время бот не мог бы писать в базу.
                if await db.release(conn):
                    log.warning("[USERBOT] уведомление %s оставило "
                                "открытую транзакцию — снята", message_id)
                queue.task_done()
    finally:
        await conn.close()


async def _tell(bot, text: str) -> None:
    """Написать владельцам. Сообщение о поломке не должно ломать то, что
    ещё работает, — поэтому ошибки здесь глотаются."""
    from app.services.delivery import notify_admins

    try:
        await notify_admins(bot, text)
    except Exception as exc:  # noqa: BLE001
        log.warning("[USERBOT] не смог написать владельцу: %s", exc)


async def run(bot=None) -> None:
    """Запустить юзербота. Возвращается только по отмене задачи.

    bot — чем писать владельцу. Свой заводится сам; передают его снаружи
    только проверки, которым настоящий Telegram не нужен.
    """
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from telethon import TelegramClient, events

    setup(settings.log_level)

    if not settings.userbot_ready:
        log.error(
            "[USERBOT] Не хватает настроек. Нужны TG_API_ID, TG_API_HASH "
            "и BANK_BOT в .env. api_id и api_hash берутся на my.telegram.org."
        )
        return

    wanted_ids, wanted_names = sources()
    log.info("[USERBOT] Слушаю уведомления от: %s", source_name())

    settings.session_file.parent.mkdir(parents=True, exist_ok=True)
    own_bot = bot is None
    if own_bot:
        bot = Bot(settings.bot_token,
                  default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE)
    worker = asyncio.create_task(_drain(queue, bot))
    pause = RETRY_MIN
    misses = 0          # неудач подряд
    told = False        # владельцу уже сообщили о поломке

    try:
        while True:
            client = TelegramClient(
                str(settings.session_file), settings.tg_api_id,
                settings.tg_api_hash,
            )

            @client.on(events.NewMessage(incoming=True))
            async def on_message(event) -> None:      # noqa: ANN001
                # Всё, что не от банка, не читаем и не пишем никуда:
                # это чужая личная переписка.
                if not _from_source(event.message, wanted_ids, wanted_names):
                    return
                log.info("[USERBOT] New bank message")
                try:
                    queue.put_nowait((event.message.id, event.message.message or ""))
                except asyncio.QueueFull:
                    log.error("[USERBOT] Очередь переполнена, уведомление "
                              "%s пропущено", event.message.id)

            try:
                # Не client.start(): без живого сеанса он стал бы спрашивать
                # номер у службы, где никто не ответит («EOF when reading a
                # line»). Сеанс мёртв — так и говорим и ждём входа руками.
                await client.connect()
                if not await client.is_user_authorized():
                    raise RuntimeError("сеанс завершён в Telegram — нужен "
                                       "новый вход: stars-bot userbot login")
                me = await client.get_me()
                log.info("[USERBOT] Подключён как @%s", me.username or me.id)
                # id банка по юзернейму: по id узнавать надёжнее, а у
                # отправителя новых сообщений юзернейм бывает не подгружен.
                for name in sorted(wanted_names):
                    try:
                        entity = await client.get_entity(name)
                        wanted_ids.add(entity.id)
                        log.info("[USERBOT] Банк @%s → id %s", name, entity.id)
                    except Exception as exc:  # noqa: BLE001
                        log.warning("[USERBOT] Банк @%s не найден: %s", name, exc)
                if not wanted_ids and not wanted_names:
                    log.error("[USERBOT] BANK_BOT пуст — слушать некого")
                if told:
                    await _tell(bot, "✅ <b>Юзербот снова на связи</b>\n\n"
                                     "<i>Оплаты опять подтверждаются сами.</i>")
                pause, misses, told = RETRY_MIN, 0, False
                await client.run_until_disconnected()
                log.warning("[USERBOT] Связь с Telegram пропала")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — обрыв связи не ошибка
                log.warning("[USERBOT] Подключение сорвалось: %s", exc)
                misses += 1
                if misses >= ALERT_AFTER and not told:
                    told = True
                    await _tell(
                        bot,
                        "🔌 <b>Юзербот не может подключиться к Telegram</b>\n"
                        f"├ Попыток подряд: <b>{misses}</b>\n"
                        f"└ <code>{str(exc)[:200]}</code>\n\n"
                        "<blockquote>Оплаты сейчас <b>не подтверждаются "
                        "сами</b> — проверяйте заявки руками: "
                        "/panel → 📥 Заявки.\n\n"
                        "Частая причина — сеанс завершён в Telegram. "
                        "Тогда нужен новый вход: "
                        "<code>stars-bot userbot login</code></blockquote>",
                    )
            finally:
                with contextlib.suppress(Exception):
                    await client.disconnect()

            log.info("[USERBOT] Повтор через %s с", pause)
            await asyncio.sleep(pause)
            pause = min(pause * 2, RETRY_MAX)
    finally:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        if own_bot:
            with contextlib.suppress(Exception):
                await bot.session.close()
