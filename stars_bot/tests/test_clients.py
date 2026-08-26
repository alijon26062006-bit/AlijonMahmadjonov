"""Работа с клиентами из панели: поиск, начисление, списание, блокировка."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app import db, reports, runtime
from app.handlers import panel

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeUser:
    def __init__(self, uid=111):
        self.id, self.username, self.first_name = uid, "admin", "Админ"


class FakeMessage:
    def __init__(self, text=None):
        self.text = text
        self.from_user = FakeUser()
        self.replies: list[str] = []

    async def answer(self, text, **kw):
        self.replies.append(text)
        return self

    async def edit_text(self, text, **kw):
        return await self.answer(text, **kw)

    @property
    def last(self):
        return self.replies[-1] if self.replies else ""


class FakeCallback:
    def __init__(self, data):
        self.data = data
        self.from_user = FakeUser()
        self.message = FakeMessage()
        self.alerts: list[str] = []

    async def answer(self, text="", **kw):
        if text:
            self.alerts.append(text)

    @property
    def last(self):
        return self.message.last


class FakeState:
    def __init__(self):
        self.data, self.state = {}, None

    async def set_state(self, v):
        self.state = getattr(v, "state", v)

    async def update_data(self, **kw):
        self.data.update(kw)

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.data.clear()
        self.state = None


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


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


async def run(conn) -> None:
    bot = FakeBot()
    await db.upsert_user(conn, 900, "klient", "Клиент")
    await db.credit(conn, 900, 5000, as_deposit=True)

    # ------------------------------------------------------------- поиск
    check("клиент находится по ID",
          (await db.find_user(conn, "900")) is not None)
    check("клиент находится по юзернейму",
          (await db.find_user(conn, "@klient")).id == 900)
    check("юзернейм без собаки тоже ищется",
          (await db.find_user(conn, "klient")).id == 900)
    check("регистр не мешает", (await db.find_user(conn, "@KLIENT")).id == 900)
    check("несуществующий не находится",
          await db.find_user(conn, "@nobody") is None)

    state = FakeState()
    msg = FakeMessage("@nobody")
    await panel.on_user_search(msg, state, conn)
    check("на ненайденного объясняем причину", "напишет боту" in msg.last)

    msg = FakeMessage("900")
    await panel.on_user_search(msg, state, conn)
    check("карточка клиента показывается",
          "@klient" in msg.last and "50.00" in msg.last, msg.last[:90])

    # --------------------------------------------------------- начисление
    call = FakeCallback("pn:give:900")
    await panel.cb_adjust_start(call, state, conn)
    check("экран начисления открывается", "Начислить" in call.last)
    check("запомнили, кому начисляем", state.data["adjust_user"] == 900)

    msg = FakeMessage("25 бонус за отзыв")
    await panel.on_adjust_amount(msg, state, conn, bot)
    user = await db.get_user(conn, 900)
    check("баланс вырос", user.balance == 7500, str(user.balance))
    check("отчёт о начислении показан", "Начислено" in msg.last and "25.00" in msg.last)
    check("клиенту ушло уведомление",
          any("начислено" in t.lower() for _, t in bot.sent), str(bot.sent))
    check("причина дошла до клиента",
          any("бонус за отзыв" in t for _, t in bot.sent))

    ops = await db.list_adjustments(conn, user_id=900)
    check("правка записана", len(ops) == 1 and ops[0].amount == 2500, str(ops))
    check("записан админ, который её сделал", ops[0].admin_id == 111)
    check("записана причина", ops[0].reason == "бонус за отзыв")

    # ---------------------------------------------------------- списание
    call = FakeCallback("pn:take:900")
    await panel.cb_adjust_start(call, state, conn)
    msg = FakeMessage("10")
    await panel.on_adjust_amount(msg, state, conn, bot)
    user = await db.get_user(conn, 900)
    check("баланс уменьшился", user.balance == 6500, str(user.balance))
    check("списание записано со знаком минус",
          (await db.list_adjustments(conn, user_id=900))[0].amount == -1000)

    # ------------------------------- в минус баланс не уводим
    call = FakeCallback("pn:take:900")
    await panel.cb_adjust_start(call, state, conn)
    msg = FakeMessage("999")
    await panel.on_adjust_amount(msg, state, conn, bot)
    user = await db.get_user(conn, 900)
    check("списать больше, чем есть, нельзя",
          user.balance == 6500 and "Не хватает" in msg.last, str(user.balance))
    check("лишней записи не появилось",
          len(await db.list_adjustments(conn, user_id=900)) == 2)

    # ---------------------------------------------- неверный ввод
    msg = FakeMessage("много")
    await panel.on_adjust_amount(msg, state, conn, bot)
    check("нечисловая сумма отклоняется", "числом" in msg.last)

    msg = FakeMessage("0")
    await panel.on_adjust_amount(msg, state, conn, bot)
    check("ноль отклоняется", "числом" in msg.last)

    # ------------------------------------------------------- блокировка
    call = FakeCallback("pn:ban:900")
    await panel.cb_ban_toggle(call, conn)
    check("клиент блокируется", (await db.get_user(conn, 900)).is_banned == 1)
    check("в карточке видно блокировку", "аблокирован" in call.last)

    call = FakeCallback("pn:ban:900")
    await panel.cb_ban_toggle(call, conn)
    check("клиент разблокируется", (await db.get_user(conn, 900)).is_banned == 0)

    # ------------------------------- правки видны в отчёте
    today = reports.local_today()
    data = await db.report(conn, *reports.bounds(today, today))
    check("начисления попали в отчёт", data["adjust_added"] == 2500, str(data))
    check("списания попали в отчёт", data["adjust_taken"] == 1000, str(data))
    check("в тексте отчёта есть раздел правок",
          "Правки вручную" in panel.format_report("Тест", data, []))

    empty = await db.report(conn, "2020-01-01T00:00:00+00:00", "2020-01-02T00:00:00+00:00")
    check("без правок раздел не показывается",
          "Правки вручную" not in panel.format_report("Пусто", empty, []))

    # --------------------------- история правок видна в карточке
    stats = await db.user_order_stats(conn, 900)
    card = panel.user_card(await db.get_user(conn, 900), stats,
                           await db.list_adjustments(conn, user_id=900))
    check("в карточке видна история правок", "Правки баланса" in card)
    check("в истории видны и плюс, и минус",
          "+25.00" in card and "−10.00" in card, card[-140:])


asyncio.run(main())
