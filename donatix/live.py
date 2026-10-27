"""«Живой» сайт: страница узнаёт об изменениях сама, без кнопки «обновить».

Браузер держит одно соединение /panel/data/live (Server-Sent Events). Сервер раз в секунду смотрит в базу
«отпечаток» клиента: баланс, непрочитанные уведомления, заказы, движения по счёту (у админа — ещё все заказы
и оплаты сайта). Изменилось — сразу шлёт новое состояние, страница меняет баланс и списки на месте.
Через 30 минут соединение закрывается, браузер переподключается сам (так не копятся «мёртвые» соединения).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

from . import cache, db
from .config import Config

TICK = 1.0          # как часто смотреть в базу, секунд
MAX_AGE = 1800      # одно соединение живёт не дольше 30 минут
PING = 15           # пустая строка раз в 15 с — чтобы nginx и мобильная сеть не рвали соединение
CACHE = 1.0         # одно и то же состояние на все открытые вкладки одного пользователя — считаем раз в секунду


def state(config: Config, user_id: int, admin: bool, cur: str) -> dict[str, Any]:
    pool = db.pool(config.db_path)
    c = pool.acquire()
    try:
        u = c.execute("SELECT balance_micro FROM users WHERE id = ?", (user_id,)).fetchone()
        if u is None:
            return {"gone": True}
        unread = c.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
                           (user_id,)).fetchone()[0]
        o = c.execute("SELECT COUNT(*), MAX(id), SUM(status IN ('processing', 'attention')) FROM orders "
                      "WHERE user_id = ?", (user_id,)).fetchone()
        tx = c.execute("SELECT MAX(id) FROM transactions WHERE user_id = ?", (user_id,)).fetchone()[0]
        sig = [o[0], o[1], o[2], tx]
        if admin:
            a = c.execute("SELECT MAX(id) FROM orders").fetchone()[0]
            busy = c.execute("SELECT COUNT(*) FROM orders WHERE status IN ('processing', 'attention')").fetchone()[0]
            p = c.execute("SELECT MAX(id), SUM(status = 'pending') FROM payments").fetchone()
            t = c.execute("SELECT MAX(id) FROM transactions").fetchone()[0]
            sig += [a, busy, p[0], p[1], t]
        rate = None
        if cur == "TJS":
            from .payments import settings
            rate = settings(c, config)["tjs_rate"]
    finally:
        pool.release(c)
    if cur != "TJS":
        from . import fx
        rate = fx.rate(config, cur)   # валюта СНГ; у доллара курса нет
    from .deps import _money
    balance = u[0]
    return {"balance": balance, "balance_html": str(_money({"cur_code": cur, "cur_rate": rate}, balance)),
            "unread": unread, "sig": ".".join(str(x or 0) for x in sig)}


def cached(config: Config, user_id: int, admin: bool, cur: str) -> dict[str, Any] | None:
    """Состояние не чаще раза в CACHE секунд на пользователя: пять вкладок — один запрос к базе, а не пять."""
    return cache.get_or_set(f"live:{user_id}:{int(admin)}:{cur}", CACHE,
                            lambda: state(config, user_id, admin, cur))


async def stream(request, config: Config, user_id: int, admin: bool, cur: str) -> AsyncIterator[str]:
    started, quiet, last = time.monotonic(), 0.0, None
    yield "retry: 2000\n\n"
    while time.monotonic() - started < MAX_AGE:
        if await request.is_disconnected():
            return
        try:
            now = await asyncio.to_thread(cached, config, user_id, admin, cur)
        except Exception:  # noqa: BLE001 — база занята на миг: попробуем через секунду
            now = last
        if now is not None and now != last:
            last, quiet = now, 0.0
            yield f"data: {json.dumps(now, ensure_ascii=False)}\n\n"
            if now.get("gone"):
                return
        else:
            quiet += TICK
            if quiet >= PING:
                quiet = 0.0
                yield ": ping\n\n"
        await asyncio.sleep(TICK)
