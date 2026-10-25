"""Реклама Donatix в боте: клиентам — да, владельцу и админам — никогда; «Пропустить» убирает её."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app.config import settings
from app.handlers import menu
from app.services import ads

OWNER = 111          # админ из .env в тестовом окружении
CLIENT = 999_000_111
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


AD = {"photo": "https://donatix.tj/static/bn/a-tg.jpg", "caption": "Канал\n\nРеклама",
      "reply_markup": {"inline_keyboard": [[{"text": "Перейти", "url": "https://donatix.tj/bn-go/1"}],
                                           [{"text": "Пропустить", "callback_data": "adskip"}]]}}


class FakeBot:
    def __init__(self):
        self.photos = []

    async def send_photo(self, chat_id, photo, caption, reply_markup):
        self.photos.append((chat_id, photo, caption, reply_markup))


class FakeMessage:
    def __init__(self):
        self.deleted = False

    async def delete(self):
        self.deleted = True


class FakeCall:
    def __init__(self):
        self.message, self.answered = FakeMessage(), False

    async def answer(self, *a, **k):
        self.answered = True


async def main() -> None:
    asked = []

    async def fake_ask(uid):
        asked.append(uid)
        return AD
    ads._ask = fake_ask

    bot = FakeBot()
    old = os.environ.pop("DONATIX_URL", None)
    ads.maybe_show(bot, CLIENT)
    await asyncio.sleep(0)
    check("без Donatix рекламы нет", not asked and not bot.photos)

    os.environ["DONATIX_URL"] = "https://donatix.tj"
    settings.fazer_api_key = settings.fazer_api_key or "test-key"
    ads.maybe_show(bot, OWNER)
    await asyncio.sleep(0.01)
    check("владельцу и админам — никогда", not asked and not bot.photos)

    ads.maybe_show(bot, CLIENT)
    await asyncio.sleep(0.01)
    check("клиенту — картинка", asked == [CLIENT] and bot.photos and bot.photos[0][1] == AD["photo"])
    kb = bot.photos[0][3].inline_keyboard if bot.photos else []
    check("кнопки «Перейти» и «Пропустить»",
          len(kb) == 2 and kb[0][0].url == AD["reply_markup"]["inline_keyboard"][0][0]["url"]
          and kb[1][0].callback_data == ads.SKIP)

    call = FakeCall()
    await menu.cb_ad_skip(call)
    check("«Пропустить» удаляет рекламу", call.message.deleted and call.answered)

    async def broken(uid):
        raise RuntimeError("Donatix недоступен")
    ads._ask = broken
    ads.maybe_show(bot, CLIENT)
    await asyncio.sleep(0.01)
    check("сбой рекламы бот не ломает", True)

    if old is None:
        os.environ.pop("DONATIX_URL", None)
    else:
        os.environ["DONATIX_URL"] = old
    print(f"\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
