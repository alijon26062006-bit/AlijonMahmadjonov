"""Юзербот автоплатежа «Душанбе Сити»: слушает банковского бота в Telegram владельца.

    python -m donatix bank-login     первый вход (номер, код, облачный пароль) — руками в терминале
    python -m donatix bank-listen    служба donatix-bankbot: слушать уведомления и зачислять

Отдельный процесс от сайта: если его уронит отзыв сеанса или обрыв связи, сайт продолжает работать,
просто «Душанбе Сити» подтверждают руками по чеку.

Правила:
  * берём ТОЛЬКО сообщения от бота банка (DONATIX_BANK_BOT, по id или юзернейму). Всё остальное — личная
    переписка владельца: не читаем, не пишем в журнал;
  * только новые сообщения — история не читается (там старые оплаты);
  * по одному: очередь до 100 штук, переполнение — запись в журнал, а не падение;
  * обрыв — повтор через 5 с, потом вдвое дольше до 300 с; после 5 неудач подряд — одно письмо админу.
"""

from __future__ import annotations

import asyncio
import contextlib
import getpass
import logging
from pathlib import Path

from . import db, dcbank
from .config import Config

log = logging.getLogger("donatix.bankbot")

RETRY_MIN, RETRY_MAX, ALERT_AFTER, QUEUE = 5, 300, 5, 100


class SessionDead(Exception):
    """Файл сеанса есть, но Telegram его не признаёт — нужен новый вход."""


def session_path(config: Config) -> Path:
    if config.bank_session:
        path = Path(config.bank_session)
    else:
        path = Path(config.db_path).parent / "bankbot.session"
    return path if path.suffix == ".session" else path.with_name(path.name + ".session")


def wanted(bank_bot: str) -> tuple[set[int], set[str]]:
    """DONATIX_BANK_BOT: юзернейм и/или id через запятую — «dc_next_bot,1996047418»."""
    ids, names = set(), set()
    for part in (bank_bot or "").replace(";", ",").split(","):
        part = part.strip().lstrip("@")
        if part.lstrip("-").isdigit():
            ids.add(int(part))
        elif part:
            names.add(part.lower())
    return ids, names


def from_bank(message, ids, names, sender=None) -> bool:
    """Это точно бот банка? Совпал id или юзернейм (sender — подгруженный отправитель)."""
    if isinstance(ids, int):          # старый вызов: (message, id, name)
        ids, names = ({ids} if ids else set()), ({str(names).lower()} if names and not ids else set())
    if getattr(message, "sender_id", None) in ids:
        return True
    who = sender if sender is not None else getattr(message, "sender", None)
    name = (getattr(who, "username", "") or "").lower()
    return bool(name) and name in names


def accept(message, queue: asyncio.Queue, ids, names, sender=None) -> bool:
    """Положить уведомление банка в очередь. Чужое — мимо; личную переписку в журнал не пишем,
    а про другого БОТА пишем только его id и имя — чтобы было видно, если банк назван неверно."""
    if not from_bank(message, ids, names, sender):
        if getattr(sender, "bot", False):
            log.info("Сообщение от бота id=%s @%s — это не банк из DONATIX_BANK_BOT, пропускаю",
                     getattr(message, "sender_id", "?"), getattr(sender, "username", "") or "—")
        return False
    log.info("Новое уведомление банка")
    try:
        queue.put_nowait((message.id, message.message or ""))
    except asyncio.QueueFull:
        log.error("Очередь переполнена, уведомление %s пропущено", message.id)
        return False
    return True


def process(config: Config, message_id: int, text: str) -> dict:
    """Одно уведомление — своё соединение с базой (работает в потоке, не держит цикл событий)."""
    conn = db.connect(config.db_path)
    try:
        return dcbank.handle(conn, config, source=config.bank_bot, message_id=message_id, text=text)
    finally:
        if conn.in_transaction:   # не оставить висящий замок базы после ошибки
            conn.execute("ROLLBACK")
        conn.close()


async def _drain(queue: asyncio.Queue, config: Config) -> None:
    while True:
        message_id, text = await queue.get()
        try:
            result = await asyncio.to_thread(process, config, message_id, text)
            log.info("Уведомление %s: %s", message_id, result.get("status"))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — одно кривое уведомление не останавливает остальные
            log.exception("Обработка уведомления %s сорвалась", message_id)
        finally:
            queue.task_done()


async def run(config: Config, client_factory=None) -> None:
    """Слушать банк. Возвращается только по отмене."""
    from .worker import notify_admin

    if not dcbank.ready(config):
        log.error("Нет DONATIX_TG_API_ID, DONATIX_TG_API_HASH или DONATIX_BANK_BOT в .env — слушать нечего.")
        return
    if client_factory is None:
        from telethon import TelegramClient

        def client_factory():
            return TelegramClient(str(session_path(config)), config.tg_api_id, config.tg_api_hash)

    from telethon import events

    ids, names = wanted(config.bank_bot)
    log.info("Слушаю уведомления от: %s", config.bank_bot)
    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE)
    worker = asyncio.create_task(_drain(queue, config))
    pause, misses, told = RETRY_MIN, 0, False
    try:
        while True:
            client = client_factory()

            @client.on(events.NewMessage(incoming=True))
            async def on_message(event) -> None:  # noqa: ANN001
                if not event.is_private:
                    return
                sender = None
                if getattr(event.message, "sender_id", None) not in ids:
                    with contextlib.suppress(Exception):   # юзернейм — только у подгруженного отправителя
                        sender = await event.get_sender()
                accept(event.message, queue, ids, names, sender)

            try:
                await client.connect()
                if not await client.is_user_authorized():
                    raise SessionDead("сеанс завершён в Telegram — нужен новый вход")
                me = await client.get_me()
                log.info("Подключён как @%s", getattr(me, "username", None) or getattr(me, "id", "?"))
                for nm in names:   # узнать id банка по юзернейму — по id надёжнее
                    with contextlib.suppress(Exception):
                        ent = await client.get_entity(nm)
                        ids.add(ent.id)
                        log.info("Банк @%s → id %s", nm, ent.id)
                if told:
                    notify_admin(config, "✅ Автоплатёж «Душанбе Сити» снова на связи — оплаты подтверждаются сами.")
                pause, misses, told = RETRY_MIN, 0, False
                await client.run_until_disconnected()
                log.warning("Связь с Telegram пропала")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — обрыв связи не ошибка
                log.warning("Подключение сорвалось: %s", exc)
                misses += 1
                if misses >= ALERT_AFTER and not told:
                    told = True
                    notify_admin(config, "🔌 Юзербот «Душанбе Сити» не может подключиться к Telegram "
                                         f"({misses} попыток подряд: {str(exc)[:150]}). Оплаты сейчас НЕ "
                                         "подтверждаются сами — проверяйте заявки руками. Частая причина — сеанс "
                                         "завершён в Telegram, нужен новый вход: python -m donatix bank-login")
            finally:
                with contextlib.suppress(Exception):
                    await client.disconnect()
            log.info("Повтор через %s с", pause)
            await asyncio.sleep(pause)
            pause = min(pause * 2, RETRY_MAX)
    finally:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker


async def login(config: Config) -> int:
    """Первый вход руками. Код — самый последний, набирать руками (пересланный код сгорает)."""
    from telethon import TelegramClient

    from .tgsession import LoginFailed, login as do_login

    if not (config.tg_api_id and config.tg_api_hash):
        print("❌ Нет DONATIX_TG_API_ID или DONATIX_TG_API_HASH в .env (берутся на https://my.telegram.org).")
        return 1
    session = session_path(config)
    session.parent.mkdir(parents=True, exist_ok=True)
    client = None
    try:
        client = await do_login(lambda: TelegramClient(str(session), config.tg_api_id, config.tg_api_hash),
                                session, input, getpass.getpass)
        me = await client.get_me()
        print(f"\n✅ Вошли как @{me.username or me.id} ({me.first_name}). Файл сеанса: {session}")
        print("   Никому не передавайте этот файл — это доступ к вашему Telegram.")
        _, names = wanted(config.bank_bot)
        for nm in sorted(names) or ["dc_next_bot"]:
            try:
                entity = await client.get_entity(nm)
                print(f"✅ Банковский бот @{nm}: id={entity.id}")
            except Exception as exc:  # noqa: BLE001 — подсказка, не работа
                print(f"⚠️ Не нашёл @{nm}: {exc}. Нужна переписка с этим ботом в этом аккаунте.")
        return 0
    except LoginFailed as exc:
        print(f"\n❌ {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\n⏹ Вход отменён.")
    except Exception as exc:  # noqa: BLE001 — человеку нужен смысл, а не трейсбек
        print(f"\n❌ Войти не получилось: {exc}\n   Проверьте интернет и запустите вход снова.")
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                await client.disconnect()
    return 1
