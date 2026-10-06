"""Первый вход в Telegram: stars-bot userbot login (или python -m app.userbot.login)

Запускается руками, в терминале сервера. Telegram пришлёт код в ваш же
Telegram — его надо ввести здесь. После этого рядом появится файл сеанса,
и юзербот будет входить сам.

Файл сеанса равен доступу к вашему Telegram. Он лежит в data/, которая
исключена из git, и делиться им нельзя ни с кем.

Почему не client.start(): после неверного кода и обрыва связи он теряет
phone_code_hash, и следующий, уже верный код Telegram не принимает —
вход падает с трейсбеком. Поэтому шаги ведём сами: запросили код,
запомнили его хэш и подаём его в каждый sign_in, сколько бы попыток и
переподключений ни понадобилось.
"""
from __future__ import annotations

import asyncio
import getpass
import re
import time
from pathlib import Path
from typing import Callable

from app.config import settings
from app.userbot.log import setup

log = setup(settings.log_level)

#: Сколько раз можно ошибиться в коде и сколько раз попросить новый.
WRONG_CODES = 3
NEW_CODES = 3
PASSWORDS = 3

TIPS = (
    "📩 Код отправлен в ваш Telegram (чат «Telegram» с синей галочкой).\n"
    "   • Берите САМЫЙ ПОСЛЕДНИЙ код.\n"
    "   • Набирайте его руками. Не пересылайте и не вставляйте код ни в один чат\n"
    "     Telegram — Telegram увидит это и код сгорит."
)


class LoginFailed(Exception):
    """Войти не вышло. Текст — понятное человеку объяснение."""


def clean(value: str) -> str:
    """Номер и код без пробелов, дефисов и скобок: «+992 90-123 45 67» → «+992901234567»."""
    return re.sub(r"[\s\-()]", "", value or "")


def retire(session: Path) -> Path:
    """Отложить мёртвый файл сеанса: не удалять, а переименовать в .old.

    Удалять нельзя — вдруг сеанс мёртв не навсегда и он ещё понадобится
    разобраться, что случилось. Рядом лежащий журнал SQLite тоже уносим,
    иначе Telethon подхватил бы его к новому файлу.
    """
    old = session.with_name(session.name + ".old")
    if old.exists():
        old = session.with_name(f"{session.name}.{int(time.time())}.old")
    session.rename(old)
    journal = session.with_name(session.name + "-journal")
    if journal.exists():
        journal.rename(old.with_name(old.name + "-journal"))
    return old


async def _alive(client) -> None:
    """Перед каждым шагом — живо ли соединение. Нет — подключиться заново.

    Хэш кода при этом не теряется: он хранится у нас, а не в соединении.
    """
    if not client.is_connected():
        await client.connect()


async def login(
    make_client: Callable[[], object],
    session: Path,
    ask: Callable[[str], str],
    ask_secret: Callable[[str], str],
    say: Callable[[str], None] = print,
) -> object:
    """Войти в Telegram. Возвращает подключённый клиент или бросает LoginFailed.

    ask / ask_secret / say подменяются в проверках — настоящий Telegram и
    живой человек у клавиатуры им не нужны.
    """
    from telethon.errors import (
        FloodWaitError,
        PasswordHashInvalidError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        PhoneNumberInvalidError,
        SessionPasswordNeededError,
    )

    def flood(exc) -> LoginFailed:
        minutes = max(1, (int(getattr(exc, "seconds", 0) or 0) + 59) // 60)
        return LoginFailed(f"Telegram просит подождать {minutes} мин. перед новой попыткой. "
                           "Подождите и запустите вход снова.")

    if session.exists():
        client = make_client()
        await client.connect()
        if await client.is_user_authorized():
            return client                                     # вход уже есть — ничего не делаем
        await client.disconnect()
        old = retire(session)
        say(f"⚠️ Старый сеанс больше не работает (его завершили в Telegram).\n"
            f"   Он отложен в {old.name}, входим заново.")

    client = make_client()
    await client.connect()

    phone, code_hash = "", ""
    for _ in range(3):
        phone = clean(ask("📱 Номер телефона этого Telegram (например +992901234567): "))
        if not re.fullmatch(r"\+?\d{9,15}", phone):
            say("❌ Это не похоже на номер. Нужны цифры, можно с + в начале.")
            continue
        if not phone.startswith("+"):
            phone = "+" + phone
        try:
            await _alive(client)
            sent = await client.send_code_request(phone)
        except PhoneNumberInvalidError:
            say("❌ Telegram не знает такой номер. Проверьте его и введите ещё раз.")
            continue
        except FloodWaitError as exc:
            raise flood(exc) from None
        code_hash = sent.phone_code_hash
        break
    if not code_hash:
        raise LoginFailed("Номер так и не подошёл. Запустите вход снова.")

    say(TIPS)
    wrong = fresh = 0
    while True:
        code = clean(ask("🔢 Код из Telegram: "))
        if not code.isdigit():
            say("❌ Код — это только цифры. Введите его ещё раз.")
            continue
        try:
            await _alive(client)
            await client.sign_in(phone=phone, code=code, phone_code_hash=code_hash)
            return client
        except PhoneCodeInvalidError:
            wrong += 1
            if wrong >= WRONG_CODES:
                raise LoginFailed("Код неверный три раза подряд. Запустите вход снова "
                                  "и возьмите самый последний код.") from None
            say(f"❌ Код неверный. Осталось попыток: {WRONG_CODES - wrong}.")
        except PhoneCodeExpiredError:
            fresh += 1
            if fresh > NEW_CODES:
                raise LoginFailed("Коды сгорают один за другим. Скорее всего, код пересылали "
                                  "или вставляли в чат. Запустите вход снова и наберите код руками.") from None
            say("⌛ Код устарел — запрашиваю новый.")
            try:
                await _alive(client)
                sent = await client.send_code_request(phone)
            except FloodWaitError as exc:
                raise flood(exc) from None
            code_hash, wrong = sent.phone_code_hash, 0
            say(TIPS)
        except SessionPasswordNeededError:
            break
        except FloodWaitError as exc:
            raise flood(exc) from None
        except (ConnectionError, OSError):
            say("📶 Связь с Telegram оборвалась. Переподключаюсь — введите тот же код ещё раз.")

    # Включена двухэтапная проверка — нужен облачный пароль.
    for left in range(PASSWORDS - 1, -1, -1):
        password = ask_secret("🔐 Облачный пароль Telegram (не виден при вводе): ")
        try:
            await _alive(client)
            await client.sign_in(password=password)
            return client
        except PasswordHashInvalidError:
            if not left:
                break
            say(f"❌ Пароль неверный. Осталось попыток: {left}.")
        except FloodWaitError as exc:
            raise flood(exc) from None
    raise LoginFailed("Облачный пароль неверный. Запустите вход снова.")


async def main() -> int:
    from telethon import TelegramClient

    if not (settings.tg_api_id and settings.tg_api_hash):
        print("❌ Нет TG_API_ID или TG_API_HASH в .env.\n"
              "   Возьмите их на https://my.telegram.org → API development tools")
        return 1

    session = settings.session_file
    if session.suffix != ".session":
        session = session.with_name(session.name + ".session")   # так его называет Telethon
    session.parent.mkdir(parents=True, exist_ok=True)

    def make_client():
        return TelegramClient(str(session), settings.tg_api_id, settings.tg_api_hash)

    client = None
    try:
        client = await login(make_client, session, input, getpass.getpass)
        me = await client.get_me()
        print(f"\n✅ Вошли как @{me.username or me.id} ({me.first_name})")
        print(f"   Файл сеанса: {session}")
        print("   Больше код вводить не потребуется. Никому не передавайте этот файл.\n")
        await _check_bank(client)
        return 0
    except LoginFailed as exc:
        print(f"\n❌ {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\n⏹ Вход отменён.")
    except Exception as exc:  # noqa: BLE001 — человеку нужен смысл, а не трейсбек
        log.debug("login", exc_info=True)
        print(f"\n❌ Войти не получилось: {exc}\n   Проверьте интернет и запустите вход снова.")
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
    return 1


async def _check_bank(client) -> None:
    from app.userbot.runner import wanted

    if not settings.bank_bot:
        print("⚠️ BANK_BOT в .env пуст — юзербот не будет знать, кого слушать.")
        return
    _, names = wanted(settings.bank_bot)
    for name in sorted(names):
        try:
            entity = await client.get_entity(name)
            print(f"✅ Банковский бот @{name}: id={entity.id}")
        except Exception as exc:  # noqa: BLE001 — это подсказка, не работа
            print(f"⚠️ Не нашёл @{name}: {exc}")
            print("   Проверьте, что переписка с этим ботом у вас есть.")

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
