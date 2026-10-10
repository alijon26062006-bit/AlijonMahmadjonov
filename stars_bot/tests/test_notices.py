"""Заявки на пополнение: кнопки у всех админов, старые сообщения, чек в любое время."""
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
from app.handlers import admin, deposit
from app.middlewares.stale_screen import StaleScreenGuard

PASS, FAIL = [], []
CLIENT = 5005


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class Bot:
    def __init__(self):
        self.stripped, self.sent = [], []

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None):
        self.stripped.append((chat_id, message_id))

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw.get("reply_to_message_id")))


class Sent:
    def __init__(self, mid):
        self.message_id = mid


class User:
    def __init__(self, uid, username="client"):
        self.id, self.username, self.first_name = uid, username, "Клиент"


class Photo:
    def __init__(self, fid):
        self.file_id = fid


class Msg:
    counter = 100

    def __init__(self, uid=CLIENT, photo="file-1"):
        self.from_user = User(uid)
        self.photo = [Photo(photo)] if photo else None
        self.document = None
        self.answers, self.copies = [], []

    async def answer(self, text, **kw):
        self.answers.append(text)

    async def copy_to(self, chat_id, caption="", reply_markup=None):
        Msg.counter += 1
        self.copies.append((chat_id, caption, reply_markup))
        return Sent(Msg.counter)


class Chat:
    def __init__(self, cid):
        self.id = cid


class Stub:
    """Заглушка Telegram для сообщения старше двух суток: без правки."""

    def __init__(self, chat_id, message_id):
        self.chat, self.message_id = Chat(chat_id), message_id


class Call:
    def __init__(self, data, uid, message):
        self.data, self.from_user, self.message = data, User(uid, "adm"), message
        self.answers = []

    async def answer(self, text="", **kw):
        self.answers.append(text)


def state_of(uid: int) -> FSMContext:
    return FSMContext(storage=MemoryStorage(),
                      key=StorageKey(bot_id=1, chat_id=uid, user_id=uid))


async def run(conn) -> None:
    await db.upsert_user(conn, CLIENT, "client", "Клиент")
    for admin_id in (111, 222):
        await db.upsert_user(conn, admin_id, "adm", "Админ")
    bot = Bot()

    # Чек без шага диалога (бот перезапускался) — ложится к открытой заявке.
    dep = await db.create_deposit(conn, user_id=CLIENT, amount=10_03,
                                  method="Перевод на карту", receipt_file_id="",
                                  reference="TOP1111")
    state = state_of(CLIENT)
    msg = Msg()
    await deposit.on_receipt_any_time(msg, state, conn, bot)
    fresh = await db.get_deposit(conn, dep.id)
    check("чек без шага диалога прикреплён к заявке",
          fresh.receipt_file_id == "file-1", fresh.receipt_file_id)
    with_buttons = [c for c in msg.copies if c[2] is not None]
    check("заявка ушла всем админам с кнопками", len(with_buttons) >= 2,
          str(len(with_buttons)))
    rows = await conn.execute_fetchall(
        "SELECT chat_id, message_id FROM admin_notices WHERE ref_id = ?", (dep.id,))
    check("копии запомнены", len(rows) == len(with_buttons))

    # Первый админ жмёт «Зачислить» на сообщении старше двух суток.
    first_chat, _, _ = with_buttons[0]
    first_msg = rows[0]["message_id"] if rows[0]["chat_id"] == first_chat else rows[1]["message_id"]
    call = Call(f"a:dep_ok:{dep.id}", first_chat, Stub(first_chat, first_msg))
    passed = []

    async def handler(event, data):
        passed.append(event)
        await admin.cb_dep_ok(event, conn, bot)

    await StaleScreenGuard()(handler, call, {"conn": conn})
    check("старое сообщение не мешает кнопке заявки", bool(passed))
    check("заявка зачислена",
          (await db.get_deposit(conn, dep.id)).status == db.DEP_APPROVED)
    check("кнопки сняты у всех копий",
          set(bot.stripped) >= {(r["chat_id"], r["message_id"]) for r in rows},
          str(bot.stripped))
    others = [s for s in bot.sent if s[0] != first_chat and "Зачислено" in s[1]]
    check("остальным админам пометка, кто решил",
          len(others) == len(rows) - 1 and "@adm" in others[0][1], str(bot.sent))
    check("нажавшему — ответ в ответ на его сообщение",
          any(s[0] == first_chat and s[2] == first_msg for s in bot.sent))

    # Второй админ жмёт на своей копии (кнопки у него могли не успеть пропасть).
    second_chat = with_buttons[1][0]
    call = Call(f"a:dep_ok:{dep.id}", second_chat, Stub(second_chat, 999))
    await admin.cb_dep_ok(call, conn, bot)
    user = await db.get_user(conn, CLIENT)
    check("второе нажатие не зачисляет ещё раз", user.balance == 10_03, str(user.balance))
    check("второму сказано, что уже обработана",
          any("уже обработана" in a for a in call.answers), str(call.answers))

    # Чек, когда заявки нет вовсе, — всё равно принят и ушёл админам.
    msg = Msg(photo="file-2")
    await deposit.on_receipt_any_time(msg, state_of(CLIENT), conn, bot)
    check("чек без заявки принят, клиенту ответ", bool(msg.answers), str(msg.answers))
    check("чек без заявки ушёл админам",
          msg.copies and "без открытой заявки" in msg.copies[0][1])
    msg = Msg(photo="file-2")
    await deposit.on_receipt_any_time(msg, state_of(CLIENT), conn, bot)
    check("тот же чек второй раз не пересылается", not msg.copies)


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
