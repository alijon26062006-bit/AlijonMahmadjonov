"""Свои реквизиты: любой банк и номер — из панели к клиенту."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app import db, keyboards, runtime
from app.handlers import deposit, panel
from app.services import paymethods

PASS, FAIL = [], []
ADMIN, CLIENT = 111, 6100


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class User:
    def __init__(self, uid):
        self.id, self.username, self.first_name = uid, "u", "U"


class Chat:
    id = 1


class Screen:
    def __init__(self, uid=ADMIN, text=""):
        self.text, self.markup, self.from_user = text, None, User(uid)
        self.chat, self.message_id, self.answers = Chat(), 10, []

    async def edit_text(self, text, reply_markup=None, **kw):
        self.text, self.markup = text, reply_markup
        return self

    async def answer(self, text, reply_markup=None, **kw):
        self.answers.append(text)
        self.markup = reply_markup
        return self


class Call:
    def __init__(self, data, uid=ADMIN):
        self.data, self.from_user, self.message = data, User(uid), Screen(uid)
        self.alerts = []

    async def answer(self, text="", **kw):
        if text:
            self.alerts.append(text)


def btns(markup):
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


def state_of(uid):
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=uid, user_id=uid))


async def run(conn) -> None:
    await paymethods.load(conn)
    st = state_of(ADMIN)

    # ---- панель: добавить по шагам
    await panel.cb_pm_new(Call("pn:pmn"), st)
    for handler, value in ((panel.on_pm_bank, "Алиф"), (panel.on_pm_number, "+992 900 00 00 00"),
                           (panel.on_pm_holder, "Иван И.")):
        await handler(Screen(text=value), st)
    await panel.on_pm_note(Screen(text="-"), st, conn)
    methods = paymethods.all_()
    check("реквизит добавлен из панели",
          len(methods) == 1 and methods[0]["bank"] == "Алиф"
          and methods[0]["number"] == "+992 900 00 00 00" and methods[0]["note"] == "",
          str(methods))
    mid = methods[0]["id"]

    check("у клиента — кнопка банка в «Пополнить»",
          ("🏦 Алиф", f"dep:m:{mid}") in btns(keyboards.deposit_methods()),
          str(btns(keyboards.deposit_methods())))

    # ---- клиент: банк → сумма → реквизиты этого банка
    await db.upsert_user(conn, CLIENT, "c", "C")
    cst = state_of(CLIENT)
    call = Call(f"dep:m:{mid}", CLIENT)
    await deposit.cb_own_method(call, cst, conn)
    check("спрашиваем сумму", await cst.get_state() == "Deposit:amount")
    msg = Screen(CLIENT, text="10")
    await deposit.on_amount(msg, cst, conn)
    shown = msg.answers[-1] if msg.answers else ""
    check("реквизиты выбранного банка", "+992 900 00 00 00" in shown and "Алиф" in shown
          and "Иван И." in shown, shown[:200])
    dep = await db.open_deposit_of(conn, CLIENT)
    check("заявка помечена банком", dep.method == "Алиф" and dep.pay_method_id == mid,
          f"{dep.method} {dep.pay_method_id}")
    check("сумма с копейками", dep.amount != 1000 and 1000 < dep.amount < 1100, str(dep.amount))
    check("номер можно скопировать",
          any(getattr(b, "copy_text", None) for row in msg.markup.inline_keyboard for b in row))
    check("без кнопки «Душанбе Сити»",
          not any(getattr(b, "url", None) for row in msg.markup.inline_keyboard for b in row))

    # ---- после перезапуска «Назад» показывает те же реквизиты
    fresh = state_of(CLIENT)
    call = Call("dep:back", CLIENT)
    await deposit.cb_back_to_requisites(call, fresh, conn)
    check("после перезапуска — реквизиты того же банка",
          "+992 900 00 00 00" in call.message.text, call.message.text[:120])

    # ---- правка, скрыть, удалить
    await panel.cb_pm_edit(Call(f"pn:pme:{mid}:note"), st)
    await panel.on_pm_edit(Screen(text="Только через приложение"), st, conn)
    check("примечание изменено", paymethods.get(mid)["note"] == "Только через приложение")
    await panel.cb_pm_toggle(Call(f"pn:pmt:{mid}"), st, conn)
    check("скрыт — у клиента кнопки нет",
          not any(c == f"dep:m:{mid}" for _, c in btns(keyboards.deposit_methods())))
    call = Call(f"dep:m:{mid}", CLIENT + 1)
    await db.upsert_user(conn, CLIENT + 1, "d", "D")
    await deposit.cb_own_method(call, state_of(CLIENT + 1), conn)
    check("старая кнопка скрытого банка не работает", call.alerts and "дастрас нест" in call.alerts[0])
    await panel.cb_pm_delete(Call(f"pn:pmdy:{mid}"), st, conn)
    check("удалён", paymethods.all_() == [])


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
