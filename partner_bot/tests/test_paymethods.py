"""Реквизиты бота из конструктора: мастер, проверка ввода, выбор банка покупателем."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401  — фиксирует настройки до импорта app

os.environ["DONATIX_URL"] = "http://donatix.test"

from app import db, runtime  # noqa: E402
from app.config import settings  # noqa: E402

settings.fazer_api_key = settings.fazer_api_key or "dx_live_test"
from app.handlers.deposit import _requisites  # noqa: E402
from app.keyboards import deposit_methods  # noqa: E402
from app.services import paymethods as pm  # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"{'✅' if condition else '❌'} {name}" + (f"  — {detail}" if detail else ""))


async def main() -> None:
    check("карта группами по 4", pm.clean_number("5058270012345678") == "5058 2700 1234 5678")
    check("телефон с +992", pm.clean_number("+992 900 12 34 56") == "+992900123456")
    check("мусор не принимаем", pm.clean_number("привет") is None)
    check("имя без цифр", pm.clean_holder("Алиджон М.") == "Алиджон М." and pm.clean_holder("1234 5678") is None)
    check("маска номера", pm.masked("5058 2700 1234 5678") == "•••• 5678")

    conn = await db.connect()
    await db.init(conn)
    await runtime.load(conn)
    await runtime.set_value(conn, pm.KEY, "")
    await runtime.set_value(conn, "pay_card_number", "")
    check("пусто — способов нет", pm.all_methods() == [])
    a = await pm.add(conn, "Душанбе Сити", "5058 2700 1234 5678", "Алиджон М.")
    b = await pm.add(conn, "Алиф", "+992900123456", "Алиджон М.")
    check("два способа", [m["bank"] for m in pm.enabled()] == ["Душанбе Сити", "Алиф"])
    check("первый — в старых настройках", runtime.get("pay_card_number") == "5058 2700 1234 5678")
    kb = [b_.text for row in deposit_methods().inline_keyboard for b_ in row]
    check("покупатель видит оба банка", "🏦 Душанбе Сити" in kb and "🏦 Алиф" in kb, str(kb))
    await pm.update(conn, a["id"], enabled=False)
    kb = [b_.text for row in deposit_methods().inline_keyboard for b_ in row]
    check("скрытый не показывается", "🏦 Душанбе Сити" not in kb and "🏦 Алиф" in kb)
    check("старые настройки — следующий способ", runtime.get("pay_card_number") == "+992900123456")
    body, _ = _requisites(1004, "R1", pm.get(b["id"]))
    check("реквизиты выбранного банка", "+992900123456" in body and "Алиф" in body)
    await pm.delete(conn, b["id"])
    check("удаление", pm.get(b["id"]) is None)
    await conn.close()


asyncio.run(main())
print(f"\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
sys.exit(1 if FAIL else 0)
