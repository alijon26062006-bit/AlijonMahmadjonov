"""Локальный запуск без Telegram: только сервер и Mini App.

Нужен, чтобы посмотреть игру в обычном браузере, не поднимая домен и бота.
Подпись Telegram при этом не проверяется, поэтому так можно работать только
на своей машине.

    python -m duel.dev
    открыть http://127.0.0.1:8081 в двух окнах
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from aiohttp import web

from . import storage
from .config import ROOT, DuelConfig
from .server import Hub, make_app


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8081

    config = DuelConfig(
        bot_token="dev",
        public_url=f"http://{host}:{port}",
        data_dir=Path(ROOT) / "data",
        host=host,
        port=port,
        dev_mode=True,
    )
    config.ensure_dirs()
    conn = storage.connect(config.data_dir / "duel-dev.sqlite3")
    hub = Hub(config, conn, bot_username="")

    print(f"Открой http://{host}:{port} в двух окнах браузера — это два игрока.")
    print("Каждое окно получает свой номер игрока и хранит его в localStorage.")
    web.run_app(make_app(hub), host=host, port=port, print=None)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
