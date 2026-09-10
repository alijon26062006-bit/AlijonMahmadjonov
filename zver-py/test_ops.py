"""Проверка авто-возвратов, очереди, лимита частоты, банов и отзывов.

Запуск: python test_ops.py   (нужна база и .env)
"""
from __future__ import annotations

import asyncio
import sys
import time
from decimal import Decimal

import db

UID = 999_000_021
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAIL
    if not ok:
        FAIL += 1
    print(f"  {'✔' if ok else '✘'} {name}" + (f"  — {detail}" if detail else ""))


async def clean() -> None:
    await db.run("DELETE FROM z_reviews WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_queue WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_tx WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_orders WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_users WHERE id=%s", (UID,))
    await db.run("DELETE FROM z_bans WHERE ip LIKE 'test:%%'")
    await db.run("DELETE FROM z_rate WHERE k LIKE 'test:%%'")


async def make_order(age_sec: int) -> int:
    """Создать заказ с нужным «возрастом»."""
    game = await db.game(1)
    pack = await db.pack(1)
    oid = await db.create_order(UID, game, pack, "123456789", None,
                                Decimal(pack["price"]))
    await db.run("UPDATE z_orders SET created_at=%s WHERE id=%s",
                 (int(time.time()) - age_sec, oid))
    return oid


async def main() -> None:
    await db.init()
    await clean()
    await db.ensure_user(UID, "ops", "Тест Операций")

    print("\n─── лимит частоты ───")
    key = "test:rate1"
    allowed = [await db.rate_ok(key, 3, 60) for _ in range(5)]
    check("первые 3 действия проходят", allowed[:3] == [True, True, True])
    check("4-е и 5-е отсекаются", allowed[3:] == [False, False], f"{allowed}")

    check("другой ключ не задет", await db.rate_ok("test:rate2", 3, 60))

    print("\n─── баны ───")
    check("изначально не забанен", not await db.is_banned("test:ban1"))
    await db.ban("test:ban1", 5, "flood")
    check("после бана заблокирован", await db.is_banned("test:ban1"))
    await db.unban("test:ban1")
    check("разбан снимает блокировку", not await db.is_banned("test:ban1"))

    # истёкший бан не действует
    await db.run("INSERT INTO z_bans (ip,until,why) VALUES ('test:old',%s,'x')",
                 (int(time.time()) - 10,))
    check("истёкший бан не действует", not await db.is_banned("test:old"))

    print("\n─── авто-возврат зависших заказов ───")
    await db.credit(UID, Decimal("100"), "старт")
    price = Decimal((await db.pack(1))["price"])

    fresh = await make_order(60)          # свежий — трогать нельзя
    old = await make_order(3600)          # висит час — вернуть
    await db.charge(UID, price, "за старый")

    stuck = await db.stuck_orders(min_age=900)
    ids = [int(r["id"]) for r in stuck]
    check("свежий заказ не считается зависшим", fresh not in ids)
    check("старый заказ найден", old in ids, f"найдено {len(ids)}")

    before = await db.balance(UID)
    claimed = await db.claim_stuck_refund(old)
    again = await db.claim_stuck_refund(old)
    check("возврат бронируется один раз", claimed and not again)

    if claimed:
        await db.credit(UID, price, "возврат", kind="refund", ref_id=old)
    after = await db.balance(UID)
    check("деньги вернулись ровно один раз", after == before + price,
          f"было {before}, стало {after}")

    row = await db.order(old)
    check("статус заказа стал refund и стоит отметка",
          row["status"] == "refund" and int(row["refunded"]) == 1,
          f"статус {row['status']}, refunded={row['refunded']}")

    # заказ, который админ уже выполнил, авто-возврат не тронет
    done_oid = await make_order(3600)
    await db.set_order_status(done_oid, "done", 111)
    check("выполненный заказ не возвращается",
          not await db.claim_stuck_refund(done_oid))

    print("\n─── очередь повторов ───")
    q_oid = await make_order(60)
    await db.queue_add(q_oid, UID, "нет товара")
    check("заказ добавлен в очередь", await db.queue_size() >= 1)
    check("статус стал wait", (await db.order(q_oid))["status"] == "wait")
    await db.queue_add(q_oid, UID, "ещё раз")
    rows = await db.queue_rows(50)
    check("повторное добавление не дублирует",
          sum(1 for r in rows if int(r["order_id"]) == q_oid) == 1)
    await db.queue_bump(q_oid, "снова пусто")
    rows = await db.queue_rows(50)
    mine = [r for r in rows if int(r["order_id"]) == q_oid][0]
    check("счётчик попыток растёт", int(mine["tries"]) == 1)
    await db.queue_del(q_oid)
    check("удаление из очереди работает",
          not [r for r in await db.queue_rows(50) if int(r["order_id"]) == q_oid])

    print("\n─── отзывы ───")
    rev_oid = await make_order(60)
    await db.set_order_status(rev_oid, "done", 111)
    check("отзыв заводится один раз", await db.review_open(UID, rev_oid))
    check("повторно не заводится", not await db.review_open(UID, rev_oid))

    await db.review_set_stars(rev_oid, 5)
    await db.review_set_text(rev_oid, "Быстро и удобно")
    rev = await db.review_by_order(rev_oid)
    check("оценка и текст сохранены",
          int(rev["stars"]) == 5 and rev["txt"] == "Быстро и удобно")
    check("отзыв ещё не опубликован", int(rev["posted"]) == 0)
    await db.review_mark_posted(rev_oid)
    check("отметка о публикации ставится",
          int((await db.review_by_order(rev_oid))["posted"]) == 1)

    pending = await db.orders_awaiting_review(20)
    check("заказ с отзывом не попадает в очередь запросов",
          rev_oid not in [int(r["id"]) for r in pending])

    await clean()
    await db.close()
    print()
    if FAIL:
        print(f"ПРОВАЛЕНО ПРОВЕРОК: {FAIL}")
        sys.exit(1)
    print("Все проверки пройдены.")


if __name__ == "__main__":
    asyncio.run(main())
