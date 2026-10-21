"""Анимация сообщений: где включается и что бывает при отказе Telegram."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage

from app import db, effects, runtime
from app.handlers import admin, menu
from app.middlewares.effect_guard import EffectGuard

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class User:
    def __init__(self, uid):
        self.id, self.username, self.first_name = uid, "u", "U"


class Msg:
    def __init__(self, uid):
        self.from_user = User(uid)
        self.sent = []

    async def answer(self, text, **kw):
        self.sent.append(kw)


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))


async def run(conn) -> None:
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))

    msg = Msg(7001)
    await db.upsert_user(conn, 7001, "u", "U")
    await menu.cmd_start(msg, state, conn, is_new_user=False)
    check("на /start огонь", msg.sent[-1].get("message_effect_id") == effects.FIRE,
          str(msg.sent[-1]))
    await menu.cmd_start(msg, state, conn, is_new_user=True)
    check("новому клиенту — конфетти",
          msg.sent[-1].get("message_effect_id") == effects.PARTY)

    # Оплата прошла: сообщение клиенту с конфетти, бонус пригласившему тоже.
    await db.upsert_user(conn, 7002, "ref", "Пригласил")
    await db.upsert_user(conn, 7003, "new", "Новый", 7002)
    await runtime.set_value(conn, "referral_percent", "10")
    dep = await db.create_deposit(conn, user_id=7003, amount=10_00, method="card",
                                  receipt_file_id="x")
    bot = Bot()
    await admin._resolve_deposit(conn, bot, dep.id, 111, approved=True)
    to_client = [k for c, _, k in bot.sent if c == 7003]
    to_ref = [k for c, _, k in bot.sent if c == 7002]
    check("оплата прошла — конфетти",
          to_client and to_client[0].get("message_effect_id") == effects.PARTY,
          str(to_client))
    check("пригласившему бонус — конфетти",
          to_ref and to_ref[0].get("message_effect_id") == effects.PARTY, str(to_ref))

    # Выключили в панели — анимации нет нигде.
    await runtime.set_value(conn, "effects_on", "0")
    await menu.cmd_start(msg, state, conn)
    check("выключено — на /start без анимации", "message_effect_id" not in msg.sent[-1])
    check("выключено — пусто", effects.kw("paid") == {})
    await runtime.set_value(conn, "effects_on", "1")

    # Telegram не принял эффект — сообщение уходит без него.
    calls = []

    async def make_request(bot_, method):
        calls.append(method.message_effect_id)
        if method.message_effect_id:
            raise TelegramBadRequest(method=method, message="Bad Request: EFFECT_ID_INVALID")
        return "ok"

    method = SendMessage(chat_id=1, text="x", message_effect_id=effects.FIRE)
    result = await EffectGuard()(make_request, None, method)
    check("эффект отвергнут — сообщение всё равно ушло",
          result == "ok" and calls == [effects.FIRE, None], str(calls))

    async def other_error(bot_, method):
        raise TelegramBadRequest(method=method, message="Bad Request: chat not found")

    try:
        await EffectGuard()(other_error, None, SendMessage(chat_id=1, text="x"))
        check("чужие ошибки не глотаются", False)
    except TelegramBadRequest:
        check("чужие ошибки не глотаются", True)


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await run(conn)
    finally:
        await conn.close()
    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
