"""Боты для гильдии (Glory FF) через Donatix: цены, запуск, отказ, обрыв, стоп."""
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
from app.handlers import glory as gh
from app.services import donatix as dx

PASS, FAIL = [], []
UID = 8100


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class Fake:
    """Donatix понарошку: подменяет dx._call."""

    def __init__(self):
        self.mode = "ok"
        self.calls = []
        self.orders = {}

    async def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/glory/regions":
            return {"ok": True, "items": [
                {"id": "bd", "name": "Bangladesh", "premium": False, "price_usd": "1.0000"},
                {"id": "sg", "name": "Singapore", "premium": True, "price_usd": "2.0000"}]}
        if method == "POST" and path == "/glory/orders":
            if self.mode == "refuse":
                raise dx.GloryError("Для этого клана уже работает группа", "clan_busy")
            oid = f"gl-{len(self.orders) + 1}"
            self.orders[oid] = {"id": oid, "clan_id": body["clan_id"], "status": "running",
                                "glory": 1000, "farmed": 0, "clan": {"name": "Tigers"},
                                "uptime": "0m", "bots": 30}
            if self.mode == "lost":
                raise dx.GloryUnknown("нет связи")
            if self.mode == "lost_nothing":
                del self.orders[oid]
                raise dx.GloryUnknown("нет связи")
            return {"ok": True, "order": self.orders[oid]}
        if path == "/glory/orders":
            return {"ok": True, "items": list(self.orders.values())}
        if path.endswith("/stop"):
            oid = path.split("/")[3]
            self.orders[oid]["status"] = "stopped"
            return {"ok": True, "order": self.orders[oid]}
        if path.startswith("/glory/orders/"):
            return {"ok": True, "order": self.orders[path.split("/")[3]]}
        if path == "/balance":
            return {"ok": True, "balance": "9.5000", "currency": "USD"}
        raise AssertionError(path)


class User:
    def __init__(self, uid):
        self.id, self.username, self.first_name = uid, "u", "U"


class Screen:
    def __init__(self):
        self.text, self.markup = "", None

    async def edit_text(self, text, reply_markup=None, **kw):
        self.text, self.markup = text, reply_markup

    async def answer(self, text, reply_markup=None, **kw):
        self.text, self.markup = text, reply_markup


class Call:
    def __init__(self, data, uid=UID):
        self.data, self.from_user, self.message = data, User(uid), Screen()
        self.alerts = []

    async def answer(self, text="", **kw):
        if text:
            self.alerts.append(text)


class Msg(Screen):
    def __init__(self, text, uid=UID):
        super().__init__()
        self.text_in, self.from_user = text, User(uid)

    @property
    def text(self):
        return self.text_in

    @text.setter
    def text(self, value):
        self.reply = value


class Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


def btns(markup):
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


async def flow(conn, fake: Fake, bot: Bot, clan: str):
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=UID, user_id=UID))
    call = Call("gl:r:bd")
    await gh.cb_region(call, state)
    msg = Msg(clan)
    await gh.on_clan(msg, state, conn)
    call = Call("gl:go")
    if await state.get_state() != "Glory:confirm":
        call.message.text = msg.reply
        return call
    await gh.cb_go(call, state, conn, bot)
    return call


async def run(conn) -> None:
    fake = Fake()
    dx._call = fake
    await runtime.set_value(conn, "usd_rate_diram", "1100")      # 11.00 с. за $
    # Здесь проверяем цену по наценке и все регионы; «только СНГ за 30» —
    # в test_screens.
    await runtime.set_value(conn, "glory_regions", "")
    await runtime.set_value(conn, "glory_price_diram", "0")
    await runtime.set_value(conn, "glory_region_title", "")
    await db.upsert_user(conn, UID, "u", "U")
    await db.credit(conn, UID, 100_00)

    check("без ключа раздела нет", not dx.ready()
          and not any("gl:menu" == c for _, c in btns(keyboards.games_menu([]))))
    await runtime.set_value(conn, "donatix_key", "dx_live_test_key_123456")
    check("с ключом — кнопка в меню игр",
          any(c == "gl:menu" for _, c in btns(keyboards.games_menu([]))))

    from app.money import round_price

    items = await dx.regions(fresh=True)
    price = round_price(13_75)
    check("цена = Donatix × курс + наценка 25%, округлена как все цены",
          items[0]["price"] == price, str(items[0]["price"]))

    call = Call("gl:menu")
    await gh.cb_menu(call, FSMContext(storage=MemoryStorage(),
                                      key=StorageKey(bot_id=1, chat_id=1, user_id=1)))
    check("экран регионов с ценой", any(f"{price / 100:.2f}" in t for t, _ in btns(call.message.markup)),
          str(btns(call.message.markup))[:200])

    bot = Bot()
    call = await flow(conn, fake, bot, "3012345678")
    order = (await db.list_orders_of(conn, UID))[0] if hasattr(db, "list_orders_of") else None
    run_ = (await db.glory_runs_of(conn, UID))[0]
    check("запущено, карточка с очками", "Tigers" in call.message.text
          and "1000" in call.message.text, call.message.text[:200])
    check("с баланса списано", (await db.get_user(conn, UID)).balance == 100_00 - price)
    order = await db.get_order(conn, run_["order_id"])
    check("заказ выполнен, номер Donatix записан",
          order.status == db.ORDER_DELIVERED and order.fragment_order_id == "gl-1"
          and order.product_type == "glory", f"{order.status} {order.fragment_order_id}")
    check("в названии заказа клан", "3012345678" in order.title, order.title)
    check("есть кнопка «Қатъ кардан»",
          any(c.startswith("gl:s:") for _, c in btns(call.message.markup)))

    call = await flow(conn, fake, bot, "3012345678")
    check("второй запуск на тот же клан не даём", "аллакай кор мекунанд" in call.message.text
          or "аллакай кор мекунанд" in str(call.alerts), call.message.text[:120])

    # Отказ Donatix — деньги назад сразу.
    fake.mode = "refuse"
    before = (await db.get_user(conn, UID)).balance
    call = await flow(conn, fake, bot, "4000000001")
    check("отказ — деньги вернулись", (await db.get_user(conn, UID)).balance == before)
    check("клиенту объяснили", "оғоз нашуданд" in call.message.text.lower()
          or "Оғоз нашуданд" in call.message.text, call.message.text[:120])

    # Обрыв, но запуск нашёлся в списке — засчитываем.
    fake.mode = "lost"
    call = await flow(conn, fake, bot, "4000000002")
    run_ = (await db.glory_runs_of(conn, UID))[0]
    check("обрыв связи, но запуск найден — работает",
          run_["status"] == "running" and run_["ext_id"], f"{run_['status']} {run_['ext_id']}")

    # Обрыв и запуска нет — деньги держим, владельцу /done /refund.
    fake.mode = "lost_nothing"
    before = (await db.get_user(conn, UID)).balance
    call = await flow(conn, fake, bot, "4000000003")
    order = await db.get_order(conn, (await db.glory_runs_of(conn, UID))[0]["order_id"])
    check("неизвестно — заказ придержан, не возвращён",
          order.status == db.ORDER_FAILED
          and (await db.get_user(conn, UID)).balance == before - price, order.status)
    check("владельцу команды /done и /refund",
          any("/refund" in t and "Donatix не ответил" in t for _, t in bot.sent))
    fake.mode = "ok"

    # Стоп.
    first = [r for r in await db.glory_runs_of(conn, UID, 20) if r["clan_id"] == "3012345678"][0]
    call = Call(f"gl:sy:{first['order_id']}")
    await gh.cb_stop(call, conn)
    check("остановлено", (await db.get_glory_run(conn, first["order_id"]))["status"] == "stopped")

    # Чужой заказ не открыть.
    call = Call(f"gl:v:{first['order_id']}", uid=999)
    await gh.cb_view(call, conn)
    check("чужой запуск не показываем", call.alerts and "ёфт нашуд" in call.alerts[0])

    # Присмотр: группа закончила — клиенту сообщение.
    lost = [r for r in await db.glory_runs_of(conn, UID, 20) if r["clan_id"] == "4000000002"][0]
    fake.orders[lost["ext_id"]].update(status="stopped", glory=1500, farmed=500)
    bot.sent.clear()
    await gh.check_run(bot, conn, await db.get_glory_run(conn, lost["order_id"]))
    check("закончила — клиенту «+500»",
          any(c == UID and "+500" in t for c, t in bot.sent), str(bot.sent)[:200])

    from app.handlers import panel

    call = Call("pn:glory", uid=111)
    await panel.cb_glory(call, FSMContext(storage=MemoryStorage(),
                                          key=StorageKey(bot_id=1, chat_id=111, user_id=111)), conn)
    check("в панели баланс Donatix", "9.5000 USD" in call.message.text, call.message.text[:300])
    check("ключ в панели скрыт",
          "dx_live_test_key_123456" not in call.message.text
          and "dx_live_…3456" in call.message.text.replace("dx_live_", "dx_live_"),
          call.message.text[:200])

    await runtime.set_value(conn, "glory_on", "0")
    check("выключено в панели — кнопки нет",
          not any(c == "gl:menu" for _, c in btns(keyboards.games_menu([]))))


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
