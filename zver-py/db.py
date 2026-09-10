"""Работа с базой. Таблицы те же, что у PHP-версии (z_*) — балансы и
история заказов остаются на месте, обе версии видят одни данные.

Все денежные операции идут через транзакцию с SELECT ... FOR UPDATE,
поэтому два одновременных заказа не могут увести баланс в минус.
"""
from __future__ import annotations

import time
import warnings
from decimal import Decimal
from typing import Any, Iterable

import aiomysql

import config

# INSERT IGNORE и ON DUPLICATE KEY — штатный приём в этом коде: так мы
# не заводим второй отзыв по заказу и не дублируем строку очереди.
# MySQL сообщает о каждом пропуске предупреждением — в журнале это шум.
for _noise in (r".*Duplicate entry.*", r".*already exists.*",
               r".*Duplicate column name.*", r".*Duplicate key name.*"):
    warnings.filterwarnings("ignore", message=_noise)

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
            # пустые параметры передаём как None: иначе драйвер прогоняет
            # запрос через %-форматирование и спотыкается о LIKE 'z\_%'
            await cur.execute(sql, tuple(args) or None)
            return list(await cur.fetchall())


async def one(sql: str, args: Iterable[Any] = ()) -> dict | None:
    rows = await all(sql, args)
    return rows[0] if rows else None


async def run(sql: str, args: Iterable[Any] = ()) -> int:
    """Выполнить запрос. Возвращает lastrowid (или число задетых строк)."""
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, tuple(args) or None)
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


# ─────────────────────────── промокоды ───────────────────────────

async def promo_by_code(code: str) -> dict | None:
    return await one("SELECT * FROM z_promo WHERE code=%s", (code.strip().upper(),))


async def promo_used_by(promo_id: int, uid: int) -> int:
    row = await one(
        "SELECT COUNT(*) AS c FROM z_promo_use WHERE promo_id=%s AND uid=%s",
        (promo_id, uid))
    return int((row or {}).get("c", 0))


async def promo_apply(promo_id: int, uid: int, order_id: int | None,
                      off: Decimal) -> None:
    """Отметить использование промокода. Счётчики и запись — одной транзакцией."""
    async with _p().acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO z_promo_use (promo_id, uid, order_id, sum_off, at)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (promo_id, uid, order_id, str(off), int(time.time())))
                await cur.execute(
                    "UPDATE z_promo SET used=used+1, saved=saved+%s WHERE id=%s",
                    (str(off), promo_id))
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


# ─────────────────────────── обязательная подписка ───────────────────────────

async def subs_list(only_active: bool = True) -> list[dict]:
    """Каналы обязательной подписки. Если таблицы ещё нет — не роняем бота."""
    where = "WHERE active=1" if only_active else ""
    try:
        return await all(f"SELECT * FROM z_subs {where} ORDER BY sort DESC, id ASC")
    except Exception:
        return []


async def sub_ok_at(uid: int) -> int:
    try:
        row = await one("SELECT sub_ok_at FROM z_users WHERE id=%s", (uid,))
        return int((row or {}).get("sub_ok_at") or 0)
    except Exception:
        return 0


async def mark_sub_ok(uid: int) -> None:
    try:
        await run("UPDATE z_users SET sub_ok_at=%s WHERE id=%s", (int(time.time()), uid))
    except Exception:
        pass


# ─────────────────────────── рефералы ───────────────────────────

async def set_ref_by(uid: int, inviter: int) -> bool:
    """Записать пригласившего — только если он ещё не записан и это не сам себя."""
    if inviter == uid:
        return False
    if not await one("SELECT id FROM z_users WHERE id=%s", (inviter,)):
        return False
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE z_users SET ref_by=%s WHERE id=%s AND ref_by IS NULL",
                (inviter, uid))
            return cur.rowcount > 0


async def claim_ref_bonus(uid: int) -> int | None:
    """Забронировать выплату бонуса за приглашение uid.

    Возвращает id пригласившего, если выплату надо сделать именно сейчас,
    иначе None. Флаг ref_paid ставится условным UPDATE, поэтому бонус
    не начислится дважды даже при двух одновременных заказах.
    """
    u = await one("SELECT ref_by, ref_paid FROM z_users WHERE id=%s", (uid,))
    if not u or not u.get("ref_by") or int(u.get("ref_paid") or 0) == 1:
        return None
    inviter = int(u["ref_by"])
    if inviter == uid or not await one("SELECT id FROM z_users WHERE id=%s", (inviter,)):
        return None
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE z_users SET ref_paid=1 WHERE id=%s AND ref_paid=0", (uid,))
            return inviter if cur.rowcount > 0 else None


async def pay_ref_bonus(inviter: int, bonus: Decimal, who: str,
                        ref_uid: int) -> dict:
    """Начислить бонус пригласившему. Возвращает его баланс и число друзей."""
    async with _p().acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT balance FROM z_users WHERE id=%s FOR UPDATE", (inviter,))
                row = await cur.fetchone()
                new_bal = Decimal((row or {}).get("balance") or 0) + bonus
                await cur.execute(
                    """UPDATE z_users
                          SET balance=%s, ref_sum=ref_sum+%s, ref_cnt=ref_cnt+1
                        WHERE id=%s""",
                    (str(new_bal), str(bonus), inviter))
            await _tx(conn, inviter, "ref", bonus,
                      new_bal, f"Бонус за друга · {who}", ref_uid)
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    row = await one("SELECT balance, ref_cnt FROM z_users WHERE id=%s", (inviter,))
    return row or {"balance": ZERO, "ref_cnt": 0}


async def ref_stats(uid: int) -> dict:
    row = await one(
        "SELECT ref_cnt, ref_sum FROM z_users WHERE id=%s", (uid,))
    return row or {"ref_cnt": 0, "ref_sum": ZERO}


# ─────────────────────────── отзывы ───────────────────────────

async def review_by_order(oid: int) -> dict | None:
    try:
        return await one("SELECT * FROM z_reviews WHERE order_id=%s", (oid,))
    except Exception:
        return None


async def review_open(uid: int, oid: int) -> bool:
    """Завести пустой отзыв. False — если по заказу его уже спрашивали."""
    try:
        async with _p().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT IGNORE INTO z_reviews (uid, order_id, stars, created_at)
                       VALUES (%s,%s,0,%s)""",
                    (uid, oid, int(time.time())))
                return cur.rowcount > 0
    except Exception:
        return False


async def review_set_stars(oid: int, stars: int) -> None:
    await run("UPDATE z_reviews SET stars=%s WHERE order_id=%s", (stars, oid))


async def review_set_text(oid: int, txt: str) -> None:
    await run("UPDATE z_reviews SET txt=%s WHERE order_id=%s", (txt[:2000], oid))


async def review_mark_posted(oid: int) -> None:
    await run("UPDATE z_reviews SET posted=1 WHERE order_id=%s", (oid,))


async def orders_awaiting_review(limit: int = 15) -> list[dict]:
    """Выполненные заказы, по которым отзыв ещё не спрашивали.

    Берём старше двух минут (клиент успел получить товар) и не старше
    трёх суток — как в PHP.
    """
    now = int(time.time())
    try:
        return await all(
            """SELECT o.id, o.uid FROM z_orders o
                 LEFT JOIN z_reviews r ON r.order_id = o.id
                WHERE o.status='done' AND r.id IS NULL
                  AND o.done_at > %s AND o.done_at < %s
                ORDER BY o.id DESC LIMIT %s""",
            (now - 3 * 86400, now - 120, limit))
    except Exception:
        return []


# ─────────────────────────── зависшие заказы ───────────────────────────

async def stuck_orders(min_age: int = 900, limit: int = 500) -> list[dict]:
    return await all(
        """SELECT o.*, u.name, u.username
             FROM z_orders o LEFT JOIN z_users u ON u.id = o.uid
            WHERE o.status='new' AND o.refunded=0 AND o.price > 0
              AND o.created_at < %s
            ORDER BY o.id ASC LIMIT %s""",
        (int(time.time()) - min_age, limit))


async def claim_stuck_refund(oid: int) -> bool:
    """Забронировать авто-возврат по заказу. True — возвращать должны мы.

    Условие status='new' AND refunded=0 гарантирует, что заказ, который
    админ уже обработал руками, повторно не вернётся.
    """
    async with _p().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """UPDATE z_orders
                      SET status='refund', refunded=1, done_at=%s,
                          note=CONCAT(COALESCE(note,''),' [авто-возврат]')
                    WHERE id=%s AND status='new' AND refunded=0""",
                (int(time.time()), oid))
            return cur.rowcount > 0


# ─────────────────────────── очередь повторов ───────────────────────────

async def queue_add(oid: int, uid: int, err: str) -> None:
    try:
        await run(
            """INSERT IGNORE INTO z_queue (order_id, uid, tries, last_err, created_at)
               VALUES (%s,%s,0,%s,%s)""",
            (oid, uid, (err or "")[:180], int(time.time())))
        await run("UPDATE z_orders SET status='wait', note=NULL WHERE id=%s", (oid,))
    except Exception:
        pass


async def queue_size() -> int:
    try:
        row = await one("SELECT COUNT(*) AS c FROM z_queue")
        return int((row or {}).get("c", 0))
    except Exception:
        return 0


async def queue_rows(limit: int = 25) -> list[dict]:
    try:
        return await all(
            """SELECT q.*, o.status FROM z_queue q
                 JOIN z_orders o ON o.id = q.order_id
                ORDER BY q.id LIMIT %s""", (limit,))
    except Exception:
        return []


async def queue_del(oid: int) -> None:
    await run("DELETE FROM z_queue WHERE order_id=%s", (oid,))


async def queue_bump(oid: int, err: str) -> None:
    await run("UPDATE z_queue SET tries=tries+1, last_err=%s WHERE order_id=%s",
              ((err or "")[:180], oid))


# ─────────────────────────── баны и лимит частоты ───────────────────────────

async def is_banned(key: str) -> bool:
    try:
        row = await one("SELECT until FROM z_bans WHERE ip=%s", (key[:64],))
        return bool(row and int(row["until"] or 0) > int(time.time()))
    except Exception:
        return False


async def ban(key: str, minutes: int, why: str = "") -> None:
    try:
        await run(
            """INSERT INTO z_bans (ip, until, why) VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 until = GREATEST(until, VALUES(until)), why = VALUES(why)""",
            (key[:64], int(time.time()) + minutes * 60, (why or "")[:60]))
    except Exception:
        pass


async def unban(key: str) -> None:
    try:
        await run("DELETE FROM z_bans WHERE ip=%s", (key[:64],))
    except Exception:
        pass


async def rate_ok(key: str, limit: int, window: int) -> bool:
    """True — действие в пределах лимита. Окно фиксированное, как в PHP.

    Любая ошибка базы пропускает пользователя: лимитер не должен
    становиться причиной отказа в обслуживании.
    """
    try:
        now = int(time.time())
        win = now - (now % window)
        await run(
            """INSERT INTO z_rate (k, cnt, win) VALUES (%s, 1, %s)
               ON DUPLICATE KEY UPDATE
                 cnt = IF(win = VALUES(win), cnt + 1, 1), win = VALUES(win)""",
            (key[:78], win))
        row = await one("SELECT cnt FROM z_rate WHERE k=%s AND win=%s", (key[:78], win))
        return int((row or {}).get("cnt", 1)) <= limit
    except Exception:
        return True
