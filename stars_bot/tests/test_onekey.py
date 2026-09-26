"""stars-bot onekey: всё на игровой ключ, прежний ключ звёзд не тратится."""
from __future__ import annotations

import asyncio
import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

import setup as wizard
from app import db, runtime
from app.config import settings
from app.services import suppliers
from app.tools import one_key

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


async def run() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    await db.init(conn)
    await runtime.load(conn)

    real_env, was_main = wizard.ENV, settings.fazer_api_key
    with tempfile.TemporaryDirectory() as tmp:
        wizard.ENV = Path(tmp) / ".env"
        wizard.ENV.write_text("BOT_TOKEN=1:x\nFAZER_API_KEY=fc_stars_old_1111\n"
                              "FAZER_GAMES_KEY=\nFRAGMENT_MODE=fazer\n", encoding="utf-8")
        settings.fazer_api_key = "fc_stars_old_1111"
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = await one_key.main()
            check("без игрового ключа — отказ, ничего не тронуто",
                  code == 1 and "fc_stars_old_1111" in wizard.ENV.read_text(), out.getvalue())

            await runtime.set_value(conn, "fazer_games_key", "fc_games_new_2222")
            check("до переключения у игр свой ключ", suppliers.has_own_games_key())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = await one_key.main()
            env = wizard.ENV.read_text()
            check("основным стал игровой ключ",
                  code == 0 and "FAZER_API_KEY=fc_games_new_2222" in env, env)
            check("прежний ключ звёзд из настроек убран", "fc_stars_old_1111" not in env)
            check("отдельного игрового ключа больше нет", "FAZER_GAMES_KEY=\n" in env)
            await runtime.load(conn)
            check("и в панели он тоже убран", runtime.get("fazer_games_key") == "")
            check("ключи целиком не печатаются",
                  "fc_games_new_2222" not in out.getvalue()
                  and "2222" in out.getvalue(), out.getvalue())
        finally:
            wizard.ENV, settings.fazer_api_key = real_env, was_main
            await conn.close()


asyncio.run(run())
print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
if FAIL:
    print("ПРОВАЛЫ:", ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
