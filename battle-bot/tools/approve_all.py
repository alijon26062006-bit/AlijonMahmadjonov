"""Принять ВСЕ накопленные заявки на вступление — одной командой.

Зачем отдельный инструмент. Бот работает через Bot API, а там нет метода,
который отдаёт список уже накопленных заявок: боту приходят только новые.
Поэтому тысяча заявок, поданных до бота, для него не существует.

У вашего собственного аккаунта такой возможности не отнимали: в клиентском
API есть `messages.hideAllChatJoinRequests` — ровно кнопка «принять всех»
из приложения Telegram, только вызванная скриптом. Этот скрипт входит в
Telegram под вашим аккаунтом и нажимает её.

Запуск:

    python tools/approve_all.py

Скрипт спросит всё сам. Ключи api_id и api_hash берутся один раз на
https://my.telegram.org → API development tools.

Про безопасность: по умолчанию вход держится только в памяти, на диск
ничего не пишется, и в конце скрипт выходит из сессии. Значит, после работы
на сервере не остаётся ничего, чем можно зайти в ваш аккаунт.
"""
from __future__ import annotations

import asyncio
import os
import sys

try:
    from telethon import TelegramClient, functions, types
    from telethon.errors import (
        FloodWaitError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        PhoneNumberInvalidError,
        PhoneNumberUnoccupiedError,
        SessionPasswordNeededError,
    )
    from telethon.sessions import StringSession
except ImportError:  # pragma: no cover - подсказка вместо трассировки
    sys.exit(
        "Не установлен telethon. Поставьте его и запустите снова:\n"
        "    pip install telethon"
    )

PAGE = 100      # столько заявок берём за один запрос
PACE = 0.05     # пауза в запасном режиме, по одной заявке


def ask(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    answer = input(f"{question}{hint}: ").strip()
    return answer or default


def ask_code() -> str:
    """Код подтверждения. Берём из ввода только цифры.

    Код приходит в само приложение Telegram сообщением «Login code: 12345».
    Люди часто вводят его с пробелами или дописывают лишнее — цифры всё
    равно достанем, чтобы не тратить попытку зря.
    """
    raw = input("Код из Telegram (5 цифр): ")
    return "".join(char for char in raw if char.isdigit())


async def login(client) -> None:
    """Вход по телефону с понятными подсказками вместо английских.

    Код Telegram присылает **в приложение**, а не по SMS. Важно: если
    переслать или написать этот код в любом чате Telegram, он тут же
    перестаёт работать — Telegram так защищает аккаунты.
    """
    phone = os.getenv("TG_PHONE") or ask("Номер телефона (например +992...)")
    await client.connect()
    if await client.is_user_authorized():
        return

    # номер должен быть тот, под которым вы владеете каналом: на чужой
    # номер уйдёт чужой код, а на незанятый Telegram предложит регистрацию
    if ask(f"Отправляю код на {phone} — верно? (да/нет)", "да").lower() not in {
        "да", "y", "yes", "д"
    }:
        sys.exit("Запустите battle-approve заново и введите нужный номер.")

    try:
        await client.send_code_request(phone)
    except FloodWaitError as error:
        sys.exit(
            f"Telegram временно не шлёт коды на этот номер: подождите "
            f"{error.seconds // 60 + 1} мин и запустите заново. Так бывает "
            "после нескольких неверных попыток."
        )
    except PhoneNumberInvalidError:
        sys.exit("Такого номера не бывает. Пишите с кодом страны, например +992...")
    except PhoneNumberUnoccupiedError:
        sys.exit(
            "На этом номере нет аккаунта Telegram. Введите номер того "
            "аккаунта, который владеет каналом."
        )

    print("\n─────────────────────────────────────────")
    print("Код ушёл В САМО ПРИЛОЖЕНИЕ Telegram, а не по SMS.")
    print("Откройте Telegram на телефоне и найдите чат «Telegram»")
    print("(синяя галочка, служебные сообщения) — код там, 5 цифр.")
    print()
    print("Не пересылайте его в чатах: пересланный код сразу сгорает.")
    print("─────────────────────────────────────────\n")

    for attempt in range(3):
        code = ask_code()
        if not code:
            print("Нужны только цифры кода. Попробуйте ещё раз.")
            continue
        try:
            await client.sign_in(phone, code)
            return
        except PhoneCodeInvalidError:
            print("Код не подошёл. Проверьте цифры и введите заново.")
        except PhoneCodeExpiredError:
            sys.exit(
                "Код истёк. Запустите battle-approve заново — придёт новый."
            )
        except SessionPasswordNeededError:
            password = ask("Облачный пароль (двухэтапная проверка)")
            await client.sign_in(password=password)
            return

    sys.exit("Три раза код не подошёл. Запустите battle-approve заново.")


async def find_channel(client, channel: str):
    """Найти канал по @имени или по ID.

    По одному числовому ID Telegram канал не отдаёт, пока аккаунт его
    «не видел» в этой сессии. Поэтому при неудаче проходим по своим чатам
    и ищем канал там — для владельца канала это всегда срабатывает.
    """
    try:
        return await client.get_input_entity(
            int(channel) if channel.lstrip("-").isdigit() else channel
        )
    except (ValueError, TypeError):
        pass

    print("Ищу канал среди ваших чатов…")
    wanted = channel.lstrip("-").removeprefix("100")
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        name = getattr(entity, "username", None) or ""
        if str(entity.id).endswith(wanted) or name.lower() == channel.lstrip("@").lower():
            print(f"Нашёл: {dialog.name}")
            return await client.get_input_entity(entity)

    sys.exit(
        "Не нашёл такой канал у этого аккаунта. Проверьте ID (его видно "
        "в панели бота, раздел «Канал») и что вы вошли тем аккаунтом, "
        "который владеет каналом."
    )


async def waiting_count(client, peer) -> int:
    """Сколько заявок сейчас ждёт решения."""
    result = await client(
        functions.messages.GetChatInviteImportersRequest(
            peer=peer,
            offset_date=None,
            offset_user=types.InputUserEmpty(),
            limit=1,
            requested=True,
        )
    )
    return int(result.count)


async def approve_one_by_one(client, peer) -> int:
    """Запасной путь: пройти по заявкам и принять каждую.

    Нужен, если «принять всех» отработало не до конца — например, часть
    заявок пришла по другой ссылке-приглашению.
    """
    done = 0
    while True:
        batch = await client(
            functions.messages.GetChatInviteImportersRequest(
                peer=peer,
                offset_date=None,
                offset_user=types.InputUserEmpty(),
                limit=PAGE,
                requested=True,
            )
        )
        if not batch.users:
            return done

        for user in batch.users:
            try:
                await client(
                    functions.messages.HideChatJoinRequestRequest(
                        peer=peer, user_id=user.id, approved=True
                    )
                )
                done += 1
            except FloodWaitError as error:
                print(f"   Telegram просит подождать {error.seconds} с — жду…")
                await asyncio.sleep(error.seconds + 1)
            except Exception as error:  # noqa: BLE001 - один сбой не рушит проход
                print(f"   {user.id}: {error}")
            if done % 50 == 0:
                print(f"   принято {done}…")
            await asyncio.sleep(PACE)


async def main() -> None:
    print("\n=== Принять все заявки в канал ===\n")
    api_id = os.getenv("TG_API_ID") or ask("api_id с my.telegram.org")
    api_hash = os.getenv("TG_API_HASH") or ask("api_hash")
    channel = os.getenv("TG_CHANNEL") or ask("канал (@имя или -100…)")

    if not api_id.isdigit():
        sys.exit("api_id — это число. Возьмите его на https://my.telegram.org")

    # сессия живёт только в памяти: на диске не остаётся ничего от вашего входа
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await login(client)

    try:
        peer = await find_channel(client, channel)

        waiting = await waiting_count(client, peer)
        print(f"\nЖдут решения: {waiting}")
        if not waiting:
            print("Принимать нечего.")
            return

        if ask("Принять всех? (да/нет)", "да").lower() not in {"да", "y", "yes", "д"}:
            print("Отменено.")
            return

        print("Принимаю всех одним запросом…")
        try:
            await client(
                functions.messages.HideAllChatJoinRequestsRequest(peer=peer, approved=True)
            )
        except FloodWaitError as error:
            print(f"Telegram просит подождать {error.seconds} с — жду…")
            await asyncio.sleep(error.seconds + 1)
            await client(
                functions.messages.HideAllChatJoinRequestsRequest(peer=peer, approved=True)
            )

        left = await waiting_count(client, peer)
        if left:
            print(f"Осталось {left} — прохожу по одной…")
            await approve_one_by_one(client, peer)
            left = await waiting_count(client, peer)

        print(f"\nГотово. Принято: {waiting - left}. Осталось ждать: {left}")
    finally:
        # выходим из сессии: после работы на сервере не остаётся доступа к аккаунту
        await client.log_out()
        print("Из аккаунта вышел, ничего на сервере не осталось.")


if __name__ == "__main__":
    asyncio.run(main())
