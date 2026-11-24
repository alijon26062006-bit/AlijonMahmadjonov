"""Цены в рублях рядом с сомони: «10.00 с. / 95 ₽»."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app import db, runtime
from app.money import fmt, fmt_short
from app.services import rubrate

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


async def run(conn) -> None:
    check("без курса — как раньше", fmt(1000) == "10.00 с.", fmt(1000))

    await runtime.set_value(conn, "rub_per_tjs", "10")
    check("с курсом — «10.00 с. / 100 ₽»", fmt(1000) == "10.00 с. / 100 ₽", fmt(1000))
    check("на кнопках тоже", fmt_short(1000) == "10 с. / 100 ₽", fmt_short(1000))
    check("тысячи с пробелом", fmt(150_000) == "1 500.00 с. / 15 000 ₽", fmt(150_000))
    await runtime.set_value(conn, "rub_per_tjs", "8.7368")
    check("рубли целые, округлённые", fmt(1250) == "12.50 с. / 109 ₽", fmt(1250))

    await runtime.set_value(conn, "rub_show", "0")
    check("выключено в панели — без рублей", fmt(1000) == "10.00 с.")
    await runtime.set_value(conn, "rub_show", "1")

    sample = {"Valute": {"TJS": {"Nominal": 10, "Value": 87.368}}}
    check("курс ЦБ разобран: рублей в 1 сомони",
          abs(rubrate.parse(sample) - 8.7368) < 1e-9, str(rubrate.parse(sample)))
    check("кривой ответ ЦБ — без курса", rubrate.parse({"Valute": {}}) is None)

    async def fake_fetch():
        return 9.1

    rubrate.fetch = fake_fetch
    await runtime.set_value(conn, "rub_mode", "manual")
    await runtime.set_value(conn, "rub_per_tjs", "10")
    await rubrate.refresh(conn)
    check("свой курс бот не перезаписывает", runtime.get("rub_per_tjs") == "10")
    await runtime.set_value(conn, "rub_mode", "auto")
    await rubrate.refresh(conn)
    check("в режиме ЦБ курс обновляется", runtime.get("rub_per_tjs") == "9.1000")
    await runtime.set_value(conn, "rub_per_tjs", "")


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
