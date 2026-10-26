"""Glory в боте партнёра: оплата, возврат при неудаче, «живые» цифры, кнопка в меню."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app import db, keyboards, runtime
from app.config import settings
from app.services import glory

BUYER = 777_000_111
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class Sent:
    def __init__(self, mid):
        self.message_id = mid


class FakeBot:
    def __init__(self):
        self.sent, self.edits, self.mid = [], [], 500

    async def send_message(self, chat_id, text, **kw):
        self.mid += 1
        self.sent.append((chat_id, text))
        return Sent(self.mid)

    async def edit_message_text(self, text, chat_id=None, message_id=None, **kw):
        self.edits.append((chat_id, message_id, text))


class FakeDonatix:
    def __init__(self):
        self.order = {"id": "gl-7", "status": "running", "glory": 48210, "farmed": 1350, "refunded": False,
                      "clan": {"name": "TJ KINGS", "level": 6, "members": 47, "capacity": 55},
                      "uptime": "1h12m", "bots": 4}
        self.launch_error = None
        self.calls = []

    async def __call__(self, method, path, json=None):
        self.calls.append((method, path, json))
        if path == "/regions":
            return 200, {"items": [{"id": "bd", "name": "Bangladesh", "code": "BD", "price_usd": "2.0000"}]}
        if method == "POST" and path == "/orders":
            if self.launch_error:
                return 409, {"ok": False, "code": self.launch_error, "error": "x"}
            return 200, {"order": dict(self.order, status="starting")}
        if path.endswith("/stop"):
            return 200, {"order": dict(self.order, status="stopped")}
        return 200, {"order": self.order}


async def balance(conn) -> int:
    return (await db.get_user(conn, BUYER)).balance


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    fake = FakeDonatix()
    glory._dx = fake
    os.environ["DONATIX_URL"] = "https://donatix.tj"
    settings.fazer_api_key = settings.fazer_api_key or "test-key"
    bot = FakeBot()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await runtime.set_value(conn, "usd_rate_diram", "1100")     # 1 $ = 11 сомони
        await runtime.set_value(conn, "margin_percent", "10")
        await db.upsert_user(conn, BUYER, "buyer", "Покупатель")
        await db.credit(conn, BUYER, 10_000)                         # 100 сомони

        items = await glory.regions(force=True)
        price, cost = glory.price_of(items[0])
        check("Glory доступен — кнопка в меню", glory.available and any(
            b.callback_data == "gl:home" for row in keyboards.main_menu().inline_keyboard for b in row))
        check("цена = Donatix × курс + наценка", cost == 2200 and price >= 2420, f"{price} {cost}")

        gid = await glory.launch(bot, conn, BUYER, "bd", "3012345678")
        check("запуск: списано с клиента", await balance(conn) == 10_000 - price)
        check("в Donatix ушли регион и клан",
              ("POST", "/orders", {"region": "bd", "clan_id": "3012345678"}) in fake.calls)

        g = await glory.get(conn, gid)
        await glory.show(bot, conn, g, chat_id=BUYER)
        check("живое сообщение с цифрами", bot.sent and "48210" in bot.sent[-1][1] and "+1350" in bot.sent[-1][1]
              and "TJ KINGS" in bot.sent[-1][1], bot.sent[-1][1] if bot.sent else "")
        fake.order = dict(fake.order, glory=48900, farmed=2040)
        await glory.show(bot, conn, await glory.get(conn, gid))
        check("цифры меняются — то же сообщение правится", bot.edits and "48900" in bot.edits[-1][2])
        n = len(bot.edits)
        await glory.show(bot, conn, await glory.get(conn, gid))
        check("не поменялось — Telegram не дёргаем", len(bot.edits) == n)

        before = await balance(conn)
        fake.launch_error = "clan_busy"
        try:
            await glory.launch(bot, conn, BUYER, "bd", "3012345678")
            check("клан занят — отказ", False)
        except glory.GloryFail as exc:
            check("клан занят — понятная причина и деньги на месте",
                  "клан" in str(exc) and await balance(conn) == before, str(exc))
        fake.launch_error = None

        try:
            await glory.launch(bot, conn, BUYER, "bd", "abc")
            check("плохой ID клана — отказ", False)
        except glory.GloryFail:
            check("плохой ID клана — отказ без списания", await balance(conn) == before)

        gid2 = await glory.launch(bot, conn, BUYER, "bd", "3099999999")
        mid_balance = await balance(conn)
        fake.order = dict(fake.order, status="failed", refunded=True)
        await glory.live(conn, await glory.get(conn, gid2))
        await glory.live(conn, await glory.get(conn, gid2))
        check("Donatix: не запустилась — клиенту вернули один раз", await balance(conn) == mid_balance + price)

        fake.order = dict(fake.order, status="running", refunded=False)
        ok = await glory.stop(conn, await glory.get(conn, gid))
        check("остановить", ok and (await glory.get(conn, gid))["status"] == "stopped")

        await runtime.set_value(conn, "glory_margin", "50")
        check("своя наценка на Glory", glory.price_of(items[0])[0] >= 3300, str(glory.price_of(items[0])))
        await runtime.set_value(conn, "glory_price_diram", "3000")
        check("одна цена для всех регионов", glory.price_of(items[0]) == (3000, 2200))
        from app.handlers import panel
        await runtime.set_value(conn, "glory_price_diram", "2000")
        txt = await panel.glory_text()
        check("цена ниже закупки — предупреждение владельцу", "в минус" in txt and "ниже закупки" in txt, txt)
        await runtime.set_value(conn, "glory_price_diram", "0")
        await runtime.set_value(conn, "glory_margin", "0")
        check("сброс — снова общая наценка", glory.price_of(items[0])[0] == price)

        os.environ.pop("DONATIX_URL", None)
        await glory.regions(force=True)
        check("без Donatix — раздела нет", not glory.available)
    finally:
        await conn.close()
    print(f"\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ: " + ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
