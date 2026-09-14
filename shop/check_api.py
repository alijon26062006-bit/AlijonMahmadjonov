"""Проверка API поставщика (FireLoot) — запускается на сервере.

    bash check_api.sh                          баланс, каталог, сверка SKU
    bash check_api.sh --ff-cis 123456789       + проверка ID в Free Fire СНГ
    bash check_api.sh --ff-id 123456789        + Free Fire Индонезия
    bash check_api.sh --pubg 5123456789        + PUBG Mobile
    bash check_api.sh --tg alijon              + Telegram Stars по username

Заказы НЕ создаются — только запросы на чтение, денег не тратит.
"""

from __future__ import annotations

import asyncio
import sys

from . import catalog
from .config import load_config
from .db import Database
from .supplier import FireLootSupplier, build_supplier

G, R, Y, C, B, E = "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[1m", "\033[0m"


def ok(msg: str) -> None:
    print(f"{G}✅ {msg}{E}")


def bad(msg: str) -> None:
    print(f"{R}❌ {msg}{E}")


def warn(msg: str) -> None:
    print(f"{Y}⚠️  {msg}{E}")


def head(msg: str) -> None:
    print(f"\n{C}── {msg} {'─' * max(0, 46 - len(msg))}{E}")


ARG_TO_CATEGORY = {
    "--ff-cis": catalog.CAT_FF_CIS,
    "--ff-id": catalog.CAT_FF_ID,
    "--pubg": catalog.CAT_PUBG,
}


def parse_args(argv: list[str]) -> tuple[dict[str, str], str | None]:
    """--ff-cis 123 --pubg 456 --tg name → ({категория: id}, username)"""
    players: dict[str, str] = {}
    username: str | None = None
    i = 0
    while i < len(argv):
        flag = argv[i]
        value = argv[i + 1] if i + 1 < len(argv) else None
        if flag in ARG_TO_CATEGORY and value:
            players[ARG_TO_CATEGORY[flag]] = value
        elif flag in ("--tg", "--stars") and value:
            username = value
        else:
            warn(f"Непонятный аргумент: {flag}")
            i += 1
            continue
        i += 2
    return players, username


async def check_balance(supplier) -> bool:
    head("1. Ключ и баланс")
    data = await supplier.balance()
    if not data.get("ok"):
        bad(f"Ключ не принят или сеть недоступна: {data.get('error')}")
        return False
    ok(f"Ключ рабочий. Баланс: {B}{data.get('balance')} {data.get('currency')}{E}")
    stars = data.get("stars_balance")
    if stars is not None:
        ok(f"Баланс Telegram Stars: {B}{stars}{E}")
    else:
        warn("Поля stars_balance нет — продажа Stars может быть не подключена")
    active = data.get("telegram_active")
    if active is not None:
        (ok if active else warn)(
            f"Telegram Stars: {'включены' if active else 'ВЫКЛЮЧЕНЫ у поставщика'}"
        )
    return True


async def check_catalog(supplier, db: Database) -> dict:
    head("2. Каталог поставщика и наши SKU")
    live = await supplier.products()
    if not live:
        bad("Каталог получить не удалось — SKU не сверены")
        return {}
    ok(f"У поставщика {B}{len(live)}{E} товаров")

    missing, found = [], 0
    for category in catalog.CATEGORIES:
        for row in db.products(category, only_active=False):
            if row["kind"] != "game" or not row["sku"]:
                continue
            if row["sku"] in live:
                found += 1
            else:
                missing.append(f"{row['title']} → {row['sku']}")
    if missing:
        bad(f"Нет у поставщика ({len(missing)}):")
        for line in missing:
            print(f"     {line}")
    else:
        ok(f"Все наши {found} SKU есть у поставщика")
    return live


async def check_player(supplier, db: Database, category: str, player_id: str) -> None:
    """Главная проверка: отдаёт ли поставщик ник по ID."""
    info = catalog.CATEGORY_INFO[category]
    rows = [r for r in db.products(category, only_active=False) if r["kind"] == "game"]
    if not rows:
        warn(f"{info.title}: нет товаров для проверки")
        return
    sku = rows[0]["sku"]
    print(f"\n{B}{info.title}{E}  ID {B}{player_id}{E}  (через SKU {sku})")

    # Сырой ответ — по нему видно, что именно отдаёт поставщик.
    if isinstance(supplier, FireLootSupplier):
        try:
            status, raw = await supplier._request(
                "POST", "/validate", json={"sku": sku, "uid": str(player_id)}
            )
            print(f"     HTTP {status}: {raw}")
        except Exception as exc:
            print(f"     запрос не прошёл: {exc}")

    result = await supplier.check(kind="game", sku=sku, target=player_id, amount=0)
    if result.ok and result.nickname:
        ok(f"Ник получен: {B}{result.nickname}{E}")
    elif result.ok:
        warn("Ответ успешный, но ника нет")
    else:
        bad(f"Ник не получен: {result.error}")


async def check_username(supplier, username: str) -> None:
    print(f"\n{B}Telegram Stars{E}  username {B}@{username.lstrip('@')}{E}")
    if isinstance(supplier, FireLootSupplier):
        try:
            status, raw = await supplier._request(
                "POST", "/telegram/check",
                json={"username": username.lstrip("@"), "stars": 50},
            )
            print(f"     HTTP {status}: {raw}")
        except Exception as exc:
            print(f"     запрос не прошёл: {exc}")
    result = await supplier.check(kind="stars", sku="stars_50", target=username, amount=50)
    if result.ok and result.nickname:
        ok(f"Имя получено: {B}{result.nickname}{E}")
    else:
        bad(f"Имя не получено: {result.error}")


async def run(argv: list[str]) -> int:
    players, username = parse_args(argv)

    try:
        cfg = load_config()
    except RuntimeError as exc:
        bad(str(exc))
        return 1

    print(f"{B}Проверка API поставщика{E}")
    print(f"Режим: {cfg.supplier} | адрес: {cfg.supplier_url or '—'}")
    if not cfg.has_supplier:
        bad("Поставщик выключен: нужны SHOP_SUPPLIER=fireloot, SHOP_SUPPLIER_URL и ключ.")
        return 1

    db = Database(cfg.db_path)
    supplier = build_supplier(cfg.supplier, cfg.supplier_url, cfg.supplier_key)
    try:
        if not await check_balance(supplier):
            return 1
        await check_catalog(supplier, db)

        head("3. Проверка ника по ID игрока")
        if not players and not username:
            warn("ID не передан — эта часть пропущена.")
            print("     Пример: bash check_api.sh --pubg 5123456789 --ff-cis 123456789")
        for category, player_id in players.items():
            await check_player(supplier, db, category, player_id)
        if username:
            await check_username(supplier, username)

        head("Итог")
        print("Заказы не создавались — деньги не потрачены.")
        return 0
    finally:
        await supplier.close()
        db.close()


def main() -> None:
    sys.exit(asyncio.run(run(sys.argv[1:])))


if __name__ == "__main__":
    main()
