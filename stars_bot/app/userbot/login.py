"""Первый вход в Telegram: python -m app.userbot.login

Запускается руками, в терминале. Telegram пришлёт код в ваш же Telegram —
его надо ввести здесь. После этого рядом появится файл сессии, и юзербот
будет входить сам.

Вход ведём сами, а не через client.start(): тот после неверного кода и
обрыва связи терял служебный хэш кода и падал с непонятной ошибкой
«phone_code_hash». Здесь хэш держим при себе, связь поднимаем заново, а
ошибки объясняем по-русски.

Файл сессии равен доступу к вашему Telegram. Он лежит в data/, которая
исключена из git, и делиться им нельзя ни с кем.
"""
from __future__ import annotations

import asyncio
import getpass
import re

from app.config import settings
from app.userbot.log import setup

log = setup(settings.log_level)

#: Сколько раз даём ввести код, прежде чем запросить новый.
CODE_TRIES = 3
#: Сколько раз запрашиваем новый код за один запуск.
SENDS = 3


def clean_phone(value: str) -> str:
    """+992 11 117-89-99 → +992111178999."""
    digits = re.sub(r"\D", "", value or "")
    return f"+{digits}" if digits else ""


def clean_code(value: str) -> str:
    """Код часто вводят с пробелами или дефисами: «53 544»."""
    return re.sub(r"\D", "", value or "")


async def _ensure(client) -> None:
    """Связь могла оборваться, пока человек искал код."""
    if not client.is_connected():
        await client.connect()


async def sign_in_flow(client, *, ask, ask_secret, say):
    """Войти: телефон → код → (облачный пароль). Возвращает пользователя.

    ask / ask_secret / say — ввод и вывод; снаружи подставляются input,
    getpass и print, в проверках — заготовки.
    """
    from telethon import errors

    await _ensure(client)
    if await client.is_user_authorized():
        return await client.get_me()

    phone = ""
    while not phone:
        phone = clean_phone(ask("Номер телефона аккаунта (например +992...): "))
        if len(phone) < 8:
            say("  ⚠️  Номер выглядит неправильно — нужен полный, с кодом страны.")
            phone = ""

    for attempt in range(SENDS):
        await _ensure(client)
        try:
            sent = await client.send_code_request(phone)
        except errors.FloodWaitError as exc:
            say(f"❌ Telegram просит подождать {exc.seconds} с перед новым кодом. "
                "Запустите вход позже.")
            return None
        except errors.PhoneNumberInvalidError:
            say("❌ Telegram не знает такой номер. Проверьте его и запустите снова.")
            return None
        except errors.PhoneNumberBannedError:
            say("❌ Этот номер заблокирован в Telegram.")
            return None
        code_hash = sent.phone_code_hash

        say("\n📩 Код отправлен. Он придёт в Telegram, в чат «Telegram» "
            "(на телефоне или компьютере, где вы уже вошли).")
        say("   Берите САМЫЙ ПОСЛЕДНИЙ код. Вводите его руками — если код "
            "переслать или вставить в любой чат Telegram, он сгорает.\n")

        for _ in range(CODE_TRIES):
            code = clean_code(ask("Код из Telegram: "))
            if not code:
                continue
            await _ensure(client)
            try:
                return await client.sign_in(phone=phone, code=code,
                                             phone_code_hash=code_hash)
            except errors.PhoneCodeInvalidError:
                say("  ⚠️  Код не подошёл. Проверьте, что это последний присланный код.")
            except errors.PhoneCodeEmptyError:
                say("  ⚠️  Пустой код.")
            except errors.PhoneCodeExpiredError:
                say("  ⚠️  Код устарел — запрашиваю новый.")
                break
            except errors.SessionPasswordNeededError:
                return await _password(client, ask_secret=ask_secret, say=say)
            except errors.FloodWaitError as exc:
                say(f"❌ Слишком много попыток. Telegram просит подождать "
                    f"{exc.seconds} с. Запустите вход позже.")
                return None
        else:
            if attempt + 1 < SENDS:
                say("\nЗапрашиваю новый код…")
            continue
    say("❌ Войти не получилось. Подождите несколько минут и запустите вход снова.")
    return None


async def _password(client, *, ask_secret, say):
    """Облачный пароль (двухэтапная проверка)."""
    from telethon import errors

    say("\n🔐 У аккаунта включён облачный пароль. Введите его "
        "(при вводе символы не видны — так и должно быть).")
    for _ in range(3):
        password = ask_secret("Облачный пароль: ")
        if not password:
            continue
        await _ensure(client)
        try:
            return await client.sign_in(password=password)
        except errors.PasswordHashInvalidError:
            say("  ⚠️  Пароль не подошёл.")
        except errors.FloodWaitError as exc:
            say(f"❌ Слишком много попыток. Подождите {exc.seconds} с.")
            return None
    say("❌ Пароль так и не подошёл. Забыли — сбросьте его в настройках Telegram.")
    return None


async def drop_dead_session(client_class) -> bool:
    """Сеанс завершили в Telegram — старый файл только мешает входу.

    Не удаляем, а откладываем рядом (.old): вдруг его ещё захотят
    посмотреть. True — отложили.
    """
    path = settings.session_file
    if not path.exists():
        return False
    client = client_class(str(path), settings.tg_api_id, settings.tg_api_hash)
    alive = False
    try:
        await client.connect()
        alive = await client.is_user_authorized()
    except Exception as exc:  # noqa: BLE001 — битый файл тоже мёртвый
        log.info("Старый сеанс не открылся: %s", exc)
    finally:
        await client.disconnect()
    if alive:
        return False
    for suffix in ("", "-journal"):
        old = path.with_name(path.name + suffix)
        if old.exists():
            old.replace(old.with_name(old.name + ".old"))
    print("ℹ️  Старый сеанс завершён в Telegram — отложил его в сторону, "
          "входим заново.")
    return True


async def main() -> None:
    from telethon import TelegramClient

    if not (settings.tg_api_id and settings.tg_api_hash):
        print("❌ Нет TG_API_ID или TG_API_HASH в .env.\n"
              "   Возьмите их на https://my.telegram.org → API development tools")
        return

    settings.session_file.parent.mkdir(parents=True, exist_ok=True)
    await drop_dead_session(TelegramClient)
    client = TelegramClient(str(settings.session_file), settings.tg_api_id,
                            settings.tg_api_hash)
    try:
        me = await sign_in_flow(client, ask=input, ask_secret=getpass.getpass,
                                say=print)
        if me is None:
            return
        print(f"\n✅ Вошли как @{me.username or me.id} ({me.first_name})")
        print(f"   Файл сессии: {settings.session_file}")
        print("   Больше код вводить не потребуется.")
        print("   Дальше: stars-bot userbot start\n")

        if settings.bank_bot:
            try:
                entity = await client.get_entity(settings.bank_bot)
                print(f"✅ Банковский бот найден: id={entity.id} "
                      f"@{getattr(entity, 'username', '—')}")
            except Exception as exc:  # noqa: BLE001 — это подсказка, не работа
                print(f"⚠️ Не нашёл {settings.bank_bot}: {exc}")
                print("   Проверьте, что переписка с этим ботом у вас есть.")
        else:
            print("⚠️ BANK_BOT в .env пуст — юзербот не будет знать, кого слушать.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nОтменено.")
