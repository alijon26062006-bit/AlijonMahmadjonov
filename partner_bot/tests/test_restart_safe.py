"""Обновление бота не теряет заказы: мягкая остановка, ключ повтора, дожимание прерванных."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app import db, runtime
from app.services import delivery, inflight
from app.services.fazer import ORDER_KEY, FazerProvider
from app.services.fragment import DeliveryProvider

BUYER = 777_000_001
PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class Provider(DeliveryProvider):
    """Запоминает, с каким ключом повтора пришёл заказ."""

    def __init__(self):
        self.keys = []

    async def deliver_stars(self, recipient, quantity):
        self.keys.append(ORDER_KEY.get())
        return type("R", (), {"order_id": "DX-1"})()


async def drain_waits_for_started() -> None:
    mw = inflight.InFlight()
    done = []

    async def slow(event, data):
        await asyncio.sleep(0.2)
        done.append(1)

    task = asyncio.create_task(mw(slow, None, {}))
    await asyncio.sleep(0.01)
    check("начатое нажатие отмечено", inflight.busy() == 1)
    left = await inflight.drain(timeout=2)
    check("остановка дождалась начатого", left == 0 and done == [1] and task.done())

    async def endless(event, data):
        await asyncio.sleep(30)

    t2 = asyncio.create_task(mw(endless, None, {}))
    await asyncio.sleep(0.01)
    check("слишком долгое — не ждём вечно", await inflight.drain(timeout=0.1) == 1)
    t2.cancel()


async def fazer_sends_key() -> None:
    p = FazerProvider.__new__(FazerProvider)
    seen = {}

    async def fake_request(method, path, payload=None, **kw):
        seen.update(kw)
        return {"order": {"id": "DX-9", "status": "completed"}}

    p._request = fake_request
    tok = ORDER_KEY.set("pbot-order-5")
    try:
        await p.deliver_stars("@durov", 50)
    finally:
        ORDER_KEY.reset(tok)
    check("Stars уходят с ключом повтора", (seen.get("headers") or {}).get("Idempotency-Key") == "pbot-order-5")


async def resume(conn) -> None:
    bot, provider = FakeBot(), Provider()
    order = await db.create_order(conn, user_id=BUYER, product_type="stars", quantity=100,
                                  recipient="@durov", price=1400, cost=1000)
    os.environ["DONATIX_URL"] = "https://donatix.tj"
    stuck = await db.interrupted_orders(conn)
    check("прерванный заказ найден", [o.id for o in stuck] == [order.id])
    n = await delivery.resume_interrupted(bot, conn, provider, stuck)
    fresh = await db.get_order(conn, order.id)
    check("через Donatix — доведён с тем же ключом",
          n == 1 and provider.keys == [delivery.order_key(order.id)] and fresh.status == db.ORDER_DELIVERED,
          f"{provider.keys} {fresh.status}")

    other = await db.create_order(conn, user_id=BUYER, product_type="stars", quantity=50,
                                  recipient="@durov", price=700, cost=500)
    os.environ.pop("DONATIX_URL", None)
    await delivery.resume_interrupted(bot, conn, Provider())
    fresh = await db.get_order(conn, other.id)
    check("без Donatix — на проверку админу, не пропал",
          fresh.status == db.ORDER_FAILED and any(f"/refund {other.id}" in t for _, t in bot.sent))
    check("клиенту сказали «проверяется»", any(c == BUYER and "проверяется" in t for c, t in bot.sent))


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await db.upsert_user(conn, BUYER, "buyer", "Покупатель")
        await drain_waits_for_started()
        await fazer_sends_key()
        await resume(conn)
    finally:
        await conn.close()
    print(f"\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ: " + ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
