"""Разбор игровых заказов: что у нас и что говорит поставщик.

Запуск (из папки бота):  python -m app.tools.game_orders [СЛОВО] [СКОЛЬКО]
    СЛОВО   — часть названия или кода игры, например «индонез» или «free»;
              пусто — все игры.
    СКОЛЬКО — сколько последних заказов показать, по умолчанию 10.

Ничего не меняет: только читает базу и спрашивает статус у поставщика.
Ключей и токенов не печатает — вывод можно показывать кому угодно.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from app import db, runtime

# Что печатаем из ответа поставщика. Остальное — служебное и длинное.
SHOW = ("status", "state", "error", "message", "reason", "comment",
        "note", "created_at", "updated_at", "completed_at")

# Как в разговоре называют Индонезию — чтобы «индонезия» нашла FF_ID.
ALIASES = {"индонез": ("indones", "_id"), "indonez": ("indones", "_id")}


def _minutes(stamp: str) -> str:
    try:
        created = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return "?"
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    minutes = int((datetime.now(timezone.utc) - created).total_seconds() // 60)
    if minutes < 120:
        return f"{minutes} мин назад"
    if minutes < 48 * 60:
        return f"{minutes // 60} ч назад"
    return f"{minutes // 1440} дн назад"


def matches(game: db.Game, word: str) -> bool:
    if not word:
        return True
    word = word.lower()
    hay = f"{game.title} {game.category_id}".lower()
    for alias, variants in ALIASES.items():
        if word.startswith(alias):
            return any(v in hay for v in variants) or "индонез" in hay
    return word in hay


def short(remote) -> str:
    if remote is None:
        return "не ответил (нет связи или заказа с таким номером нет)"
    if not isinstance(remote, dict):
        return str(remote)[:200]
    parts = [f"{k}={str(remote[k])[:120]}" for k in SHOW if remote.get(k) not in (None, "")]
    return " · ".join(parts) or ("поля: " + ", ".join(list(remote)[:15]))


async def main(word: str, limit: int) -> None:
    from app.services import suppliers
    from app.services.fragment import build_provider, mode_now

    conn = await db.connect()
    provider = None
    try:
        await runtime.load(conn)
        games = [g for g in await db.list_games(conn) if matches(g, word)]
        if not games:
            print(f"Игр по слову «{word}» не нашлось. Все игры:")
            for g in await db.list_games(conn):
                print(f"  {g.category_id:<28} {g.title}")
            return

        print(f"Режим выдачи: {mode_now()}")
        provider = build_provider(None)
        games_provider = suppliers.for_games(provider)
        print("Ключ для игр: " + ("отдельный" if suppliers.has_own_games_key()
                                   else "общий со звёздами"))
        try:
            print(f"Баланс у поставщика: {await games_provider.get_balance()}")
        except Exception as exc:  # noqa: BLE001
            print(f"Баланс не прочитался: {exc}")
        print(f"Ждём выдачу до возврата: {runtime.get_int('games_timeout_min') or 20} мин")

        for game in games:
            print("\n" + "═" * 60)
            print(f"{game.title}  [{game.category_id}]")
            print(f"  в меню: {'да' if game.enabled else 'нет'} · поля: {game.field}"
                  f" · регион ника: {game.region or '—'}")
            async with conn.execute(
                "SELECT * FROM orders WHERE product_type = ? ORDER BY id DESC LIMIT ?",
                (game.product_type, limit),
            ) as cur:
                rows = await cur.fetchall()
            if not rows:
                print("  заказов нет")
                continue
            counts: dict[str, int] = {}
            for row in rows:
                counts[row["status"]] = counts.get(row["status"], 0) + 1
            print("  последние: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
            for row in rows:
                print(f"\n  #{row['id']} · {row['status']} · {_minutes(row['created_at'])}"
                      f" · игрок {row['recipient']} · {row['price'] / 100:.2f} с.")
                if row["error"]:
                    print(f"    ошибка у нас: {row['error'][:300]}")
                external = row["fragment_order_id"]
                if not external:
                    print("    номера у поставщика нет — заказ до него не дошёл")
                    continue
                remote = await games_provider.order_status(external)
                print(f"    у поставщика #{external}: {short(remote)}")
    finally:
        if provider is not None:
            await suppliers.close_all()
            await provider.close()
        await conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    count = 10
    if args and args[-1].isdigit():
        count = min(int(args.pop()), 50)
    asyncio.run(main(" ".join(args).strip(), count))
