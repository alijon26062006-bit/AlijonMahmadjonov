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
    from telethon.errors import FloodWaitError
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
    await client.start()

    try:
        peer = await client.get_input_entity(
            int(channel) if channel.lstrip("-").isdigit() else channel
        )

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
