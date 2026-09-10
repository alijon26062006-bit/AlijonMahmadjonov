"""Проверка денежной логики на настоящей базе.

Запуск (нужна поднятая MySQL/MariaDB и заполненный .env):
    python test_money.py

Проверяет то, что дороже всего сломать: чтобы баланс не ушёл в минус,
чтобы одновременные заказы не списали лишнего и чтобы возврат не
случился дважды.
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

import db

UID = 999_000_001
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAIL
    if not ok:
        FAIL += 1
    mark = "✔" if ok else "✘"
    print(f"  {mark} {name}" + (f"  — {detail}" if detail else ""))


async def reset() -> None:
    await db.run("DELETE FROM z_tx WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_orders WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_topups WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_users WHERE id=%s", (UID,))
    await db.ensure_user(UID, "tester", "Тест Тестов")
    await db.run("UPDATE z_users SET balance=0, spent=0, orders_cnt=0 WHERE id=%s", (UID,))


async def main() -> None:
    await db.init()
    print("\n─── денежная логика ───")

    # 1. зачисление
    await reset()
    bal = await db.credit(UID, Decimal("100.00"), "тестовое пополнение")
    check("зачисление 100", bal == Decimal("100.00"), f"баланс {bal}")

    # 2. списание
    bal = await db.charge(UID, Decimal("12.50"), "покупка")
    check("списание 12.50", bal == Decimal("87.50"), f"баланс {bal}")

    # 3. нельзя уйти в минус
    res = await db.charge(UID, Decimal("1000"), "слишком дорого")
    after = await db.balance(UID)
    check("списание больше баланса отклонено",
          res is None and after == Decimal("87.50"), f"баланс {after}")

    # 4. ноль и минус не проходят
    check("списание нуля отклонено", await db.charge(UID, Decimal("0"), "ноль") is None)
    check("списание минуса отклонено", await db.charge(UID, Decimal("-5"), "минус") is None)

    # 5. десять одновременных списаний по 10 при балансе 87.50:
    #    пройти должны ровно 8, баланс — 7.50, в минус уйти нельзя
    await reset()
    await db.credit(UID, Decimal("87.50"), "старт")
    results = await asyncio.gather(
        *[db.charge(UID, Decimal("10"), f"параллель {i}") for i in range(10)]
    )
    ok_count = sum(1 for r in results if r is not None)
    final = await db.balance(UID)
    check("10 одновременных списаний по 10: прошло ровно 8",
          ok_count == 8, f"прошло {ok_count}")
    check("баланс после гонки верный и не отрицательный",
          final == Decimal("7.50"), f"баланс {final}")

    # 6. история операций совпадает с балансом
    rows = await db.all(
        "SELECT kind, amount FROM z_tx WHERE uid=%s ORDER BY id", (UID,))
    total = sum(Decimal(r["amount"]) for r in rows)
    check("сумма всех операций = баланс", total == final,
          f"операций {len(rows)}, сумма {total}, баланс {final}")

    print("\n─── заказы ───")
    await reset()
    await db.credit(UID, Decimal("50"), "старт")
    game = await db.game(1)
    pack = await db.pack(1)
    check("тестовая игра и пакет на месте", bool(game and pack))

    price = Decimal(pack["price"])
    bal = await db.charge(UID, price, "заказ")
    oid = await db.create_order(UID, game, pack, "123456789", None, price)
    check("заказ создан", oid > 0, f"#{oid}")

    # двойное нажатие «выполнен» двумя админами
    first = await db.set_order_status(oid, "done", 111)
    second = await db.set_order_status(oid, "done", 222)
    check("повторная смена статуса не проходит", first and not second)

    # возврат ровно один раз
    await reset()
    await db.credit(UID, Decimal("50"), "старт")
    await db.charge(UID, price, "заказ 2")
    oid2 = await db.create_order(UID, game, pack, "987654321", None, price)
    before = await db.balance(UID)
    rej1 = await db.set_order_status(oid2, "rejected", 111)
    if rej1:
        await db.credit(UID, price, f"возврат #{oid2}", kind="refund", ref_id=oid2)
        await db.mark_refunded(oid2)
    rej2 = await db.set_order_status(oid2, "rejected", 222)
    after = await db.balance(UID)
    check("отклонение проходит один раз", rej1 and not rej2)
    check("возврат зачислен ровно один раз",
          after == before + price, f"было {before}, стало {after}, цена {price}")

    print("\n─── пополнения ───")
    tid = await db.create_topup(UID, Decimal("25"), 1, "photo_abc")
    ok1 = await db.set_topup_status(tid, "done", 111)
    ok2 = await db.set_topup_status(tid, "done", 222)
    check("пополнение подтверждается один раз", ok1 and not ok2, f"#{tid}")

    print("\n─── каталог и справочники ───")
    check("список игр читается", len(await db.games()) >= 1)
    check("список пакетов читается", len(await db.packs(1)) >= 1)
    check("реквизиты читаются", len(await db.requisites()) >= 1)
    check("валюта из настроек", (await db.currency()) == "TJS")

    await db.run("DELETE FROM z_tx WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_orders WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_topups WHERE uid=%s", (UID,))
    await db.run("DELETE FROM z_users WHERE id=%s", (UID,))
    await db.close()

    print()
    if FAIL:
        print(f"ПРОВАЛЕНО ПРОВЕРОК: {FAIL}")
        sys.exit(1)
    print("Все проверки пройдены.")


if __name__ == "__main__":
    asyncio.run(main())
