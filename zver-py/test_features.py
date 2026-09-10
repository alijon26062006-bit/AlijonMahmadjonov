"""Проверка промокодов, рефералов и нормализации каналов подписки.

Запуск: python test_features.py   (нужна база и .env)
"""
from __future__ import annotations

import asyncio
import sys
import time
from decimal import Decimal

import db
from services import promo as promo_svc
from services import referral, subs

U1 = 999_000_011          # покупатель
U2 = 999_000_012          # пригласивший
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global FAIL
    if not ok:
        FAIL += 1
    print(f"  {'✔' if ok else '✘'} {name}" + (f"  — {detail}" if detail else ""))


async def clean() -> None:
    for uid in (U1, U2):
        await db.run("DELETE FROM z_tx WHERE uid=%s", (uid,))
        await db.run("DELETE FROM z_promo_use WHERE uid=%s", (uid,))
        await db.run("DELETE FROM z_users WHERE id=%s", (uid,))
    await db.run("DELETE FROM z_promo WHERE code LIKE 'TEST%%'")


async def mkpromo(code: str, **kw) -> int:
    cols = {"code": code, "kind": "pct", "val": "10", "min_sum": "0",
            "max_uses": "0", "per_user": "1", "active": 1,
            "until": None, "created_at": int(time.time())}
    cols.update(kw)
    keys = ",".join(cols)
    marks = ",".join(["%s"] * len(cols))
    return await db.run(f"INSERT INTO z_promo ({keys}) VALUES ({marks})",
                        tuple(cols.values()))


async def main() -> None:
    await db.init()
    await clean()
    await db.ensure_user(U1, "buyer", "Покупатель")
    await db.ensure_user(U2, "inviter", "Пригласивший")

    print("\n─── промокоды ───")
    await mkpromo("TESTPCT", kind="pct", val="10")
    r = await promo_svc.check("TESTPCT", U1, Decimal("100"))
    check("процентный: 10% от 100 = 10", r.ok and r.off == Decimal("10.00"),
          f"скидка {r.off}, итого {r.total}")

    # регистр и пробелы не мешают
    r = await promo_svc.check("  testpct ", U1, Decimal("100"))
    check("код нечувствителен к регистру и пробелам", r.ok)

    await mkpromo("TESTFIX", kind="fix", val="7.50")
    r = await promo_svc.check("TESTFIX", U1, Decimal("100"))
    check("фиксированный: скидка 7.50", r.ok and r.off == Decimal("7.50"))

    # скидка не может превысить сумму заказа
    r = await promo_svc.check("TESTFIX", U1, Decimal("5"))
    check("скидка не больше суммы заказа",
          r.ok and r.off == Decimal("5.00") and r.total == Decimal("0.00"),
          f"скидка {r.off}, итого {r.total}")

    check("несуществующий код", (await promo_svc.check("TESTNOPE", U1, Decimal("100"))).err == "NOT_FOUND")
    check("пустой код", (await promo_svc.check("", U1, Decimal("100"))).err == "EMPTY")

    await mkpromo("TESTOFF", active=0)
    check("выключенный код", (await promo_svc.check("TESTOFF", U1, Decimal("100"))).err == "OFF")

    await mkpromo("TESTOLD", until=int(time.time()) - 10)
    check("просроченный код", (await promo_svc.check("TESTOLD", U1, Decimal("100"))).err == "EXPIRED")

    await mkpromo("TESTMIN", min_sum="50")
    r = await promo_svc.check("TESTMIN", U1, Decimal("20"))
    check("сумма ниже минимальной", r.err == "MIN" and r.min_sum == Decimal("50.00"))

    await mkpromo("TESTCAP", max_uses=1)
    p = await db.promo_by_code("TESTCAP")
    await promo_svc.apply(p, U2, None, Decimal("1"))
    check("общий лимит исчерпан",
          (await promo_svc.check("TESTCAP", U1, Decimal("100"))).err == "LIMIT")

    await mkpromo("TESTONE", per_user=1)
    p = await db.promo_by_code("TESTONE")
    await promo_svc.apply(p, U1, None, Decimal("3"))
    check("повторно тем же пользователем нельзя",
          (await promo_svc.check("TESTONE", U1, Decimal("100"))).err == "USED")
    check("другому пользователю можно",
          (await promo_svc.check("TESTONE", U2, Decimal("100"))).ok)

    p = await db.promo_by_code("TESTONE")
    check("счётчики промокода обновились",
          int(p["used"]) == 1 and Decimal(p["saved"]) == Decimal("3.00"),
          f"использован {p['used']} раз, сэкономлено {p['saved']}")

    print("\n─── рефералы ───")
    await db.run("UPDATE z_users SET ref_by=NULL, ref_paid=0 WHERE id=%s", (U1,))
    await db.run("UPDATE z_users SET balance=0, ref_cnt=0, ref_sum=0 WHERE id=%s", (U2,))
    await db.run("INSERT INTO z_settings (k,v) VALUES ('ref_bonus','0.50') "
                 "ON DUPLICATE KEY UPDATE v='0.50'")

    check("сам себя пригласить нельзя", not await db.set_ref_by(U1, U1))
    check("несуществующий пригласивший отклонён", not await db.set_ref_by(U1, 1))
    check("пригласивший записан", await db.set_ref_by(U1, U2))
    check("повторно переписать нельзя", not await db.set_ref_by(U1, 777))

    first = await db.claim_ref_bonus(U1)
    second = await db.claim_ref_bonus(U1)
    check("право на бонус выдаётся один раз",
          first == U2 and second is None, f"первый {first}, второй {second}")

    bonus = await referral.bonus_amount()
    stats = await db.pay_ref_bonus(U2, bonus, "Покупатель", U1)
    check("бонус начислен пригласившему",
          Decimal(stats["balance"]) == bonus and int(stats["ref_cnt"]) == 1,
          f"баланс {stats['balance']}, друзей {stats['ref_cnt']}")

    tx = await db.all("SELECT kind, amount FROM z_tx WHERE uid=%s", (U2,))
    check("операция записана в историю",
          len(tx) == 1 and tx[0]["kind"] == "ref", f"{tx}")

    print("\n─── каналы подписки ───")
    cases = [
        ("https://t.me/mychan", "@mychan"),
        ("t.me/mychan",         "@mychan"),
        ("@mychan",             "@mychan"),
        ("mychan",              "@mychan"),
        ("-1001234567890",      "-1001234567890"),
        ("https://t.me/+AbCdEf", ""),
        ("https://t.me/joinchat/XXX", ""),
        ("",                    ""),
    ]
    for raw, want in cases:
        got = subs.norm_chat(raw)
        check(f"{raw or '(пусто)':28} → {got or '(пропуск)'}", got == want,
              "" if got == want else f"ждали {want!r}")

    await clean()
    await db.close()
    print()
    if FAIL:
        print(f"ПРОВАЛЕНО ПРОВЕРОК: {FAIL}")
        sys.exit(1)
    print("Все проверки пройдены.")


if __name__ == "__main__":
    asyncio.run(main())
