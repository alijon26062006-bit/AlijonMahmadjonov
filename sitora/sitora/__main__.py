"""Запуск: python -m sitora serve [--port 8020]  ·  python -m sitora check — проверить настройки."""
from __future__ import annotations

import argparse
import logging
import threading

from . import db
from .config import Config


def main() -> None:
    ap = argparse.ArgumentParser(prog="sitora")
    ap.add_argument("cmd", choices=["serve", "check"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8020)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = Config.load()
    db.init(config.db_path)
    from .supplier import Supplier
    from .tg import Bot
    bot = Bot(config.bot_token) if config.bot_token else None
    supplier = Supplier(config.fazer_key, config.fazer_url) if config.fazer_key else None

    if a.cmd == "check":
        print("Бот:", (bot.safe("getMe") or {}).get("username", "НЕТ — проверьте SITORA_BOT_TOKEN") if bot else "токен не задан")
        print("Админы:", config.admin_ids or "НЕТ — задайте SITORA_ADMIN_IDS")
        try:
            print("Поставщик, баланс $:", supplier.balance() if supplier else "ключ не задан")
        except Exception as exc:  # noqa: BLE001
            print("Поставщик: ошибка —", exc)
        print("Адрес:", config.base_url)
        return

    import uvicorn

    from .bot import Handler, poll
    from .web import create_app
    from .worker import Worker
    stop = threading.Event()
    if bot:
        threading.Thread(target=poll, args=(config, Handler(config, bot, supplier), stop), daemon=True, name="bot").start()
    threading.Thread(target=Worker(config, bot, supplier).run, args=(stop,), daemon=True, name="worker").start()
    try:
        uvicorn.run(create_app(config, bot), host=a.host, port=a.port, log_level="warning", proxy_headers=True)
    finally:
        stop.set()


if __name__ == "__main__":
    main()
