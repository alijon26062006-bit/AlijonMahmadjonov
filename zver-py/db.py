"""Работа с базой. Таблицы те же, что у PHP-версии (z_*) — балансы и
история заказов остаются на месте, обе версии видят одни данные.

Все денежные операции идут через транзакцию с SELECT ... FOR UPDATE,
поэтому два одновременных заказа не могут увести баланс в минус.
"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Iterable

import aiomysql

import config

_pool: aiomysql.Pool | None = None

ZERO = Decimal("0.00")


async def init() -> None:
    global _pool
    _pool = await aiomysql.create_pool(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASS,
        db=config.DB_NAME,
        charset="utf8mb4",
        autocommit=True,
        minsize=1,
        maxsize=10,
        pool_recycle=3600,
    )


async def close() -> None:
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()


def _p() -> aiomysql.Pool:
    if _pool is None:
        raise RuntimeError("db.init() не вызван")
    return _pool


async def all(sql: str, args: Iterable[Any] = ()) -> list[dict]:
    async with _p().acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, tuple(args))
            return list(await cur.fetchall())


async def one(sql: str, args: Iterable[Any] = ()) -> dict | None:
    rows = await all(sql, args)
    return rows[0] if rows else None


async def run(sql: str, args: Iterable[Any] = ()) -> int:
    """Выполнить запрос. Возвращает lastrowid (или число задетых строк)."""
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, tuple(args))
            return cur.lastrowid or cur.rowcount


# ─────────────────────────── настройки ───────────────────────────

async def setting(key: str, default: str = "") -> str:
    row = await one("SELECT v FROM z_settings WHERE k=%s", (key,))
    return row["v"] if row and row["v"] is not None else default


async def currency() -> str:
    return await setting("cur", config.CURRENCY) or config.CURRENCY


# ─────────────────────────── пользователи ───────────────────────────

async def get_user(uid: int) -> dict | None:
    return await one("SELECT * FROM z_users WHERE id=%s", (uid,))


async def ensure_user(uid: int, username: str | None,
                      name: str | None) -> tuple[dict, bool]:
    """Создаёт или обновляет пользователя.

    Возвращает (запись, новый_ли). В схеме lang имеет DEFAULT 'tj', поэтому
    пустого языка не бывает — «новый» определяем по факту вставки, иначе
    выбор языка не показался бы никому.
    """
    now = int(time.time())
    existed = await get_user(uid) is not None
    await run(
        """INSERT INTO z_users (id, username, name, created_at, seen_at)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
             username = VALUES(username),
             name     = VALUES(name),
             seen_at  = VALUES(seen_at)""",
        (uid, username, name, now, now),
    )
    user = await get_user(uid)
    assert user is not None
    return user, not existed


async def set_lang(uid: int, lang: str) -> None:
    await run("UPDATE z_users SET lang=%s WHERE id=%s", (lang, uid))


async def balance(uid: int) -> Decimal:
    row = await one("SELECT balance FROM z_users WHERE id=%s", (uid,))
    return Decimal(row["balance"]) if row and row["balance"] is not None else ZERO


async def is_blocked(uid: int) -> bool:
    row = await one("SELECT blocked FROM z_users WHERE id=%s", (uid,))
    return bool(row and row["blocked"])


# ─────────────────────────── деньги ───────────────────────────

async def _tx(conn, uid: int, kind: str, amount: Decimal,
              new_balance: Decimal, title: str, ref_id: int | None) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            """INSERT INTO z_tx (uid, kind, amount, balance, title, ref_id, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (uid, kind, str(amount), str(new_balance), title[:160],
             ref_id, int(time.time())),
        )


async def charge(uid: int, amount: Decimal, title: str,
                 ref_id: int | None = None) -> Decimal | None:
    """Списать с баланса. Возвращает новый баланс либо None, если не хватило.

    Блокирует строку пользователя на время операции, поэтому два заказа
    одновременно не спишут больше, чем есть.
    """
    if amount <= ZERO:
        return None
    async with _p().acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT balance FROM z_users WHERE id=%s FOR UPDATE", (uid,))
                row = await cur.fetchone()
                if not row:
                    await conn.rollback()
                    return None
                cur_bal = Decimal(row["balance"] or 0)
                if cur_bal < amount:
                    await conn.rollback()
                    return None
                new_bal = cur_bal - amount
                await cur.execute(
                    """UPDATE z_users
                          SET balance = %s, spent = spent + %s, orders_cnt = orders_cnt + 1
                        WHERE id = %s""",
                    (str(new_bal), str(amount), uid),
                )
            await _tx(conn, uid, "buy", -amount, new_bal, title, ref_id)
            await conn.commit()
            return new_bal
        except Exception:
            await conn.rollback()
            raise


async def credit(uid: int, amount: Decimal, title: str, kind: str = "topup",
                 ref_id: int | None = None) -> Decimal:
    """Зачислить на баланс (пополнение или возврат). Возвращает новый баланс."""
    async with _p().acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT balance FROM z_users WHERE id=%s FOR UPDATE", (uid,))
                row = await cur.fetchone()
                cur_bal = Decimal(row["balance"] or 0) if row else ZERO
                new_bal = cur_bal + amount
                await cur.execute(
                    "UPDATE z_users SET balance=%s WHERE id=%s", (str(new_bal), uid))
            await _tx(conn, uid, kind, amount, new_bal, title, ref_id)
            await conn.commit()
            return new_bal
        except Exception:
            await conn.rollback()
            raise


# ─────────────────────────── каталог ───────────────────────────

async def games() -> list[dict]:
    return await all(
        """SELECT id, name, COALESCE(NULLIF(title,''), name) AS label,
                  need_server, id_label, server_label, hint
             FROM z_games
            WHERE active = 1 AND COALESCE(hidden, 0) = 0
            ORDER BY sort DESC, id ASC"""
    )


async def game(gid: int) -> dict | None:
    return await one("SELECT * FROM z_games WHERE id=%s AND active=1", (gid,))


async def packs(gid: int) -> list[dict]:
    return await all(
        """SELECT id, game_id, COALESCE(NULLIF(title,''), name) AS label,
                  name, price, old_price, tag
             FROM z_packs
            WHERE game_id = %s AND active = 1
            ORDER BY sort DESC, price ASC"""
    , (gid,))


async def pack(pid: int) -> dict | None:
    return await one("SELECT * FROM z_packs WHERE id=%s AND active=1", (pid,))


# ─────────────────────────── заказы ───────────────────────────

async def create_order(uid: int, g: dict, p: dict,
                       player_id: str, server_id: str | None,
                       price: Decimal) -> int:
    return await run(
        """INSERT INTO z_orders
             (uid, game_id, pack_id, game_name, pack_name,
              player_id, server_id, qty, price, status, created_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,'new',%s)""",
        (uid, g["id"], p["id"], g.get("name"), p.get("name"),
         player_id, server_id, str(price), int(time.time())),
    )


async def order(oid: int) -> dict | None:
    return await one("SELECT * FROM z_orders WHERE id=%s", (oid,))


async def user_orders(uid: int, limit: int = 10) -> list[dict]:
    return await all(
        """SELECT id, game_name, pack_name, player_id, price, status, created_at
             FROM z_orders WHERE uid=%s ORDER BY id DESC LIMIT %s""",
        (uid, limit),
    )


async def orders_by_status(status: str, limit: int = 10) -> list[dict]:
    return await all(
        "SELECT * FROM z_orders WHERE status=%s ORDER BY id ASC LIMIT %s",
        (status, limit),
    )


async def set_order_status(oid: int, status: str, admin_id: int,
                           note: str | None = None) -> bool:
    """Меняет статус только если заказ ещё в 'new' — защита от двойного
    нажатия двумя админами одновременно."""
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE z_orders
                      SET status=%s, admin_id=%s, note=COALESCE(%s, note), done_at=%s
                    WHERE id=%s AND status='new'""",
                (status, admin_id, note, int(time.time()), oid),
            )
            return cur.rowcount > 0


async def mark_refunded(oid: int) -> None:
    await run("UPDATE z_orders SET refunded=1 WHERE id=%s", (oid,))


# ─────────────────────────── пополнения ───────────────────────────

async def requisites() -> list[dict]:
    return await all(
        """SELECT id, bank, owner, number, kind
             FROM z_reqs WHERE active=1 ORDER BY sort DESC, id ASC"""
    )


async def create_topup(uid: int, amount: Decimal, req_id: int | None,
                       file_id: str | None) -> int:
    return await run(
        """INSERT INTO z_topups (uid, amount, req_id, file_id, status, created_at)
           VALUES (%s,%s,%s,%s,'new',%s)""",
        (uid, str(amount), req_id, file_id, int(time.time())),
    )


async def topup(tid: int) -> dict | None:
    return await one("SELECT * FROM z_topups WHERE id=%s", (tid,))


async def topups_by_status(status: str, limit: int = 10) -> list[dict]:
    return await all(
        "SELECT * FROM z_topups WHERE status=%s ORDER BY id ASC LIMIT %s",
        (status, limit),
    )


async def set_topup_status(tid: int, status: str, admin_id: int) -> bool:
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE z_topups SET status=%s, admin_id=%s, done_at=%s
                    WHERE id=%s AND status='new'""",
                (status, admin_id, int(time.time()), tid),
            )
            return cur.rowcount > 0
