"""Найти банковский бот среди чатов юзербота.

Запуск (из папки бота, служба юзербота остановлена):
    python -m app.tools.find_bank          показать, кто похож на банк
    python -m app.tools.find_bank --set    и сразу записать его в BANK_BOT

Смотрит последние сообщения личных чатов и ищет в них слова банковского
уведомления (Zachislenie, Зачисление, Summa…). Печатает только имя, юзернейм
и id чата — текст переписки не выводит и никуда не пишет.
"""
from __future__ import annotations

import asyncio
import sys

from app.config import settings

MARKS = ("zachislenie", "зачисление", "postuplenie", "поступление")
EXTRA = ("summa", "сумма", "komis", "balans", "баланс", "tjs")


def looks_like_bank(texts: list[str]) -> int:
    """Сколько сообщений похожи на уведомление банка."""
    hits = 0
    for text in texts:
        low = (text or "").lower()
        if any(m in low for m in MARKS) and any(e in low for e in EXTRA):
            hits += 1
    return hits


async def main(write: bool) -> int:
    from telethon import TelegramClient

    from app.userbot.runner import sources

    if not (settings.tg_api_id and settings.tg_api_hash):
        print("❌ Нет TG_API_ID / TG_API_HASH.")
        return 1
    client = TelegramClient(str(settings.session_file), settings.tg_api_id,
                            settings.tg_api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            print("❌ Сеанс не активен — сначала: stars-bot userbot login")
            return 1
        ids, names = sources()
        print(f"Сейчас в BANK_BOT: {settings.bank_bot or '—'}\n")
        found = []
        async for dialog in client.iter_dialogs(limit=300):
            if not dialog.is_user:
                continue
            texts = [m.message or "" async for m in client.iter_messages(dialog, limit=15)]
            hits = looks_like_bank(texts)
            if hits:
                ent = dialog.entity
                found.append((hits, ent.id, getattr(ent, "username", "") or "",
                              dialog.name or ""))
        if not found:
            print("❌ Ни в одном чате нет уведомлений о зачислении.\n"
                  "   Уведомления банка приходят на ДРУГОЙ аккаунт Telegram —\n"
                  "   юзербот должен войти именно в тот аккаунт.")
            return 1
        found.sort(reverse=True)
        for hits, uid, uname, title in found:
            mark = "  ← сейчас слушаем" if uid in ids or uname.lower() in names else ""
            print(f"🏦 {title}  @{uname or '—'}  id={uid}  "
                  f"(уведомлений: {hits}){mark}")
        best = found[0]
        value = f"{best[2]},{best[1]}" if best[2] else str(best[1])
        if write:
            import setup as wizard

            values = wizard.read_existing()
            values["BANK_BOT"] = value
            wizard.write_env(values)
            print(f"\n✅ BANK_BOT={value} записан.")
        else:
            print(f"\nЗаписать: stars-bot userbot findbank --set  (будет BANK_BOT={value})")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--set" in sys.argv)))
