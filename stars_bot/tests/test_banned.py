"""Панель: список заблокированных и разблокировка."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app import db, runtime
from app.handlers import panel

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class Screen:
    def __init__(self):
        self.text, self.markup = "", None

    async def edit_text(self, text, reply_markup=None, **kw):
        self.text, self.markup = text, reply_markup

    async def answer(self, text, reply_markup=None, **kw):
        self.text, self.markup = text, reply_markup


class Call:
    def __init__(self, data, bot):
        self.data, self.bot, self.message = data, bot, Screen()
        self.answers = []

    async def answer(self, text="", **kw):
        self.answers.append(text)


def buttons(markup) -> list[tuple[str, str]]:
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


async def run(conn) -> None:
    bot = Bot()
    state = FSMContext(storage=MemoryStorage(),
                       key=StorageKey(bot_id=1, chat_id=111, user_id=111))
    for uid in range(9001, 9012):            # 11 человек — две страницы
        await db.upsert_user(conn, uid, f"user{uid}", "Имя")
        await db.set_banned(conn, uid, True)
    await db.upsert_user(conn, 9100, "free", "Свободный")

    call = Call("pn:users", bot)
    await panel.cb_users(call, state, conn)
    check("в «Клиентах» есть кнопка со счётчиком",
          ("🚫 Заблокированные (11)", "pn:banned:0") in buttons(call.message.markup),
          str(buttons(call.message.markup))[:200])

    call = Call("pn:banned:0", bot)
    await panel.cb_banned(call, state, conn)
    btns = buttons(call.message.markup)
    check("список показывает всех заблокированных", "Заблокированные: 11" in call.message.text)
    check("на странице 8 человек с кнопкой разблокировки",
          len([b for b in btns if b[1].startswith("pn:unban:")]) == 8)
    check("свободного в списке нет", "9100" not in call.message.text)
    check("есть переход на вторую страницу", ("›", "pn:banned:1") in btns, str(btns[-4:]))

    call = Call("pn:unban:9005:0", bot)
    await panel.cb_unban(call, conn)
    check("разблокирован одной кнопкой",
          not (await db.get_user(conn, 9005)).is_banned)
    check("человеку сообщили", bot.sent and bot.sent[-1][0] == 9005)
    check("список обновился", "Заблокированные: 10" in call.message.text)

    call = Call("pn:unban:9005:0", bot)
    await panel.cb_unban(call, conn)
    check("повторное нажатие не ломается", "Уже разблокирован." in call.answers)

    call = Call("pn:banned:5", bot)           # страницы уже нет
    await panel.cb_banned(call, state, conn)
    check("несуществующая страница → первая", "Заблокированные: 10" in call.message.text)

    for uid in range(9001, 9012):
        await db.set_banned(conn, uid, False)
    call = Call("pn:banned:0", bot)
    await panel.cb_banned(call, state, conn)
    check("пустой список объяснён", "Никто не заблокирован" in call.message.text)


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
