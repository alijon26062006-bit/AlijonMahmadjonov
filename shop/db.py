"""Базаи маълумот: SQLite. Ҳамаи маблағҳо дар дирам (бутун) нигоҳ дошта мешаванд."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import catalog

SCHEMA_VERSION = 1

ORDER_NEW = "new"            # фармоиш сохта шуд, пул гирифта шуд
ORDER_SENT = "sent"          # ба таъминкунанда фиристода шуд
ORDER_DONE = "done"          # иҷро шуд
ORDER_REJECTED = "rejected"  # рад шуд, пул баргардонида шуд
ORDER_STATUSES = (ORDER_NEW, ORDER_SENT, ORDER_DONE, ORDER_REJECTED)
ORDER_OPEN = (ORDER_NEW, ORDER_SENT)

TOPUP_WAITING = "waiting"
TOPUP_PAID = "paid"
TOPUP_REJECTED = "rejected"
TOPUP_STATUSES = (TOPUP_WAITING, TOPUP_PAID, TOPUP_REJECTED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    balance     INTEGER NOT NULL DEFAULT 0,
    spent       INTEGER NOT NULL DEFAULT 0,
    orders_done INTEGER NOT NULL DEFAULT 0,
    is_blocked  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    last_seen   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_spent ON users(spent DESC);

CREATE TABLE IF NOT EXISTS products (
    code     TEXT PRIMARY KEY,
    category TEXT    NOT NULL,
    title    TEXT    NOT NULL,
    amount   INTEGER NOT NULL DEFAULT 0,
    price    INTEGER NOT NULL,
    partner_price INTEGER,
    sku      TEXT    NOT NULL DEFAULT '',
    kind     TEXT    NOT NULL DEFAULT 'game',
    sort     INTEGER NOT NULL DEFAULT 0,
    active   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category, sort);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    product_code TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    title        TEXT    NOT NULL,
    price        INTEGER NOT NULL,
    sku          TEXT    NOT NULL DEFAULT '',
    kind         TEXT    NOT NULL DEFAULT 'game',
    target       TEXT,
    nickname     TEXT,
    status       TEXT    NOT NULL,
    external_id  TEXT,
    note         TEXT,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, id DESC);

CREATE TABLE IF NOT EXISTS topups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    amount     INTEGER NOT NULL,
    code       TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    admin_id   INTEGER,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_topups_user ON topups(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_topups_status ON topups(status, id DESC);
CREATE INDEX IF NOT EXISTS idx_topups_code ON topups(code);

CREATE TABLE IF NOT EXISTS balance_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    delta         INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reason        TEXT    NOT NULL,
    admin_id      INTEGER,
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_balance_log_user ON balance_log(user_id, id DESC);

CREATE TABLE IF NOT EXISTS partners (
    user_id    INTEGER PRIMARY KEY,
    note       TEXT,
    added_by   INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def price_of(row: sqlite3.Row, partner: bool = False) -> int:
    """Нархе, ки харидор воқеан мепардозад.

    Шарик нархи махсусро мегирад, агар он гузошта шуда бошад.
    """
    if partner:
        special = row["partner_price"] if "partner_price" in row.keys() else None
        if special:
            return int(special)
    return int(row["price"])


class NotEnoughMoney(Exception):
    """Дар ҳисоб маблағи кофӣ нест."""


@dataclass(frozen=True)
class User:
    id: int
    username: str | None
    first_name: str | None
    balance: int
    spent: int
    orders_done: int
    is_blocked: bool
    created_at: str
    last_seen: str

    @property
    def title(self) -> str:
        name = (self.first_name or "").strip()
        if self.username:
            return f"{name} (@{self.username})".strip()
        return name or str(self.id)


def _user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        first_name=row["first_name"],
        balance=row["balance"],
        spent=row["spent"],
        orders_done=row["orders_done"],
        is_blocked=bool(row["is_blocked"]),
        created_at=row["created_at"],
        last_seen=row["last_seen"],
    )


class Database:
    """Як пайвасти SQLite бо қулф — барои кори бехатар аз чанд корутина."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    # ── хидматӣ ───────────────────────────────────────────────────────
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._add_missing_columns()
            row = self._conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,)
                )
            self._conn.commit()
        self.seed_products()

    _NEW_COLUMNS = (
        ("products", "partner_price", "INTEGER"),
        ("products", "sku", "TEXT NOT NULL DEFAULT ''"),
        ("products", "kind", "TEXT NOT NULL DEFAULT 'game'"),
        ("orders", "sku", "TEXT NOT NULL DEFAULT ''"),
        ("orders", "kind", "TEXT NOT NULL DEFAULT 'game'"),
    )

    def _add_missing_columns(self) -> None:
        """Базаи кӯҳнаро бе гум кардани маълумот нав мекунад."""
        for table, column, decl in self._NEW_COLUMNS:
            have = {r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")}
            if column not in have:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        self._conn.commit()

    def _all(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))

    def _one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def _run(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    # ── молҳо ─────────────────────────────────────────────────────────
    def seed_products(self) -> None:
        """Каталогро нав мекунад.

        Нарх ва ҳолати «фаъол» ба админ тааллуқ доранд — ламс намешаванд.
        Ном, SKU, навъ ва тартиб ҳамеша аз `catalog.py` гирифта мешаванд.
        """
        with self._lock:
            for i, p in enumerate(catalog.DEFAULT_PRODUCTS):
                self._conn.execute(
                    "INSERT OR IGNORE INTO products"
                    "(code, category, title, amount, price, partner_price, sku, kind, sort, active) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (p.code, p.category, p.title, p.amount, p.price,
                     p.partner_price or None, p.sku, p.kind, i),
                )
                self._conn.execute(
                    "UPDATE products SET category = ?, title = ?, amount = ?, "
                    "sku = ?, kind = ?, sort = ? WHERE code = ?",
                    (p.category, p.title, p.amount, p.sku, p.kind, i, p.code),
                )
            # Молҳое, ки дигар дар каталог нестанд, пинҳон карда мешаванд.
            known = tuple(p.code for p in catalog.DEFAULT_PRODUCTS)
            marks = ", ".join("?" * len(known))
            self._conn.execute(
                f"UPDATE products SET active = 0 WHERE code NOT IN ({marks})", known
            )
            self._conn.commit()

    def products(self, category: str, *, only_active: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM products WHERE category = ?"
        if only_active:
            sql += " AND active = 1"
        sql += " ORDER BY sort, price"
        return self._all(sql, (category,))

    def product(self, code: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM products WHERE code = ?", (code,))

    def set_partner_price(self, code: str, price: int | None) -> bool:
        """Нархи шарикӣ. `None` — шарик нархи оддиро мепардозад."""
        cur = self._run(
            "UPDATE products SET partner_price = ? WHERE code = ?", (price, code)
        )
        return cur.rowcount > 0

    def set_price(self, code: str, price: int) -> bool:
        cur = self._run("UPDATE products SET price = ? WHERE code = ?", (price, code))
        return cur.rowcount > 0

    def set_active(self, code: str, active: bool) -> bool:
        cur = self._run(
            "UPDATE products SET active = ? WHERE code = ?", (1 if active else 0, code)
        )
        return cur.rowcount > 0

    # ── шарикон ───────────────────────────────────────────────────────
    def add_partner(self, user_id: int, note: str = "", admin_id: int | None = None) -> None:
        self._run(
            "INSERT INTO partners(user_id, note, added_by, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET note = excluded.note",
            (user_id, note, admin_id, now()),
        )

    def remove_partner(self, user_id: int) -> bool:
        return self._run("DELETE FROM partners WHERE user_id = ?", (user_id,)).rowcount > 0

    def is_partner(self, user_id: int) -> bool:
        return self._one("SELECT 1 FROM partners WHERE user_id = ?", (user_id,)) is not None

    def partners(self) -> list[sqlite3.Row]:
        return self._all(
            "SELECT p.*, u.username, u.first_name, u.balance, u.spent "
            "FROM partners p LEFT JOIN users u ON u.id = p.user_id "
            "ORDER BY p.created_at DESC"
        )

    # ── корбарон ──────────────────────────────────────────────────────
    def touch_user(
        self, user_id: int, username: str | None = None, first_name: str | None = None
    ) -> User:
        stamp = now()
        with self._lock:
            self._conn.execute(
                "INSERT INTO users(id, username, first_name, created_at, last_seen) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "  username = COALESCE(excluded.username, users.username), "
                "  first_name = COALESCE(excluded.first_name, users.first_name), "
                "  last_seen = excluded.last_seen",
                (user_id, username, first_name, stamp, stamp),
            )
            self._conn.commit()
        user = self.user(user_id)
        assert user is not None
        return user

    def user(self, user_id: int) -> User | None:
        row = self._one("SELECT * FROM users WHERE id = ?", (user_id,))
        return _user(row) if row else None

    def find_user(self, query: str) -> User | None:
        """Ҷустуҷӯ бо ID ё бо @username."""
        query = query.strip()
        if not query:
            return None
        if query.lstrip("-").isdigit():
            found = self.user(int(query))
            if found:
                return found
        name = query.lstrip("@").lower()
        row = self._one(
            "SELECT * FROM users WHERE LOWER(username) = ? ORDER BY last_seen DESC LIMIT 1",
            (name,),
        )
        return _user(row) if row else None

    def set_blocked(self, user_id: int, blocked: bool) -> None:
        self._run(
            "UPDATE users SET is_blocked = ? WHERE id = ?", (1 if blocked else 0, user_id)
        )

    def all_user_ids(self) -> list[int]:
        return [r["id"] for r in self._all("SELECT id FROM users WHERE is_blocked = 0")]

    def top_users(self, limit: int = 10) -> list[User]:
        rows = self._all(
            "SELECT * FROM users WHERE spent > 0 ORDER BY spent DESC, orders_done DESC LIMIT ?",
            (limit,),
        )
        return [_user(r) for r in rows]

    # ── ҳисоб ─────────────────────────────────────────────────────────
    def change_balance(
        self, user_id: int, delta: int, reason: str, admin_id: int | None = None
    ) -> int:
        """Ҳисобро иваз мекунад ва баланси навро бармегардонад.

        Агар маблағ нарасад — `NotEnoughMoney` мепартояд ва ҳеҷ чиз иваз намешавад.
        """
        stamp = now()
        with self._lock:
            row = self._conn.execute(
                "SELECT balance FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO users(id, created_at, last_seen) VALUES (?, ?, ?)",
                    (user_id, stamp, stamp),
                )
                current = 0
            else:
                current = row["balance"]
            new_balance = current + delta
            if new_balance < 0:
                raise NotEnoughMoney(f"balance={current}, delta={delta}")
            self._conn.execute(
                "UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id)
            )
            self._conn.execute(
                "INSERT INTO balance_log(user_id, delta, balance_after, reason, admin_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, delta, new_balance, reason, admin_id, stamp),
            )
            self._conn.commit()
        return new_balance

    def balance_log(self, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM balance_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    # ── фармоишҳо ─────────────────────────────────────────────────────
    def create_order(
        self,
        *,
        user_id: int,
        product_code: str,
        category: str,
        title: str,
        price: int,
        target: str | None,
        nickname: str | None,
        sku: str = "",
        kind: str = "game",
    ) -> int:
        """Пулро аз ҳисоб мегирад ва фармоиш мекушояд. Ҳама дар як амалиёт."""
        stamp = now()
        with self._lock:
            row = self._conn.execute(
                "SELECT balance FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            balance = row["balance"] if row else 0
            if balance < price:
                raise NotEnoughMoney(f"balance={balance}, price={price}")
            new_balance = balance - price
            self._conn.execute(
                "UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id)
            )
            cur = self._conn.execute(
                "INSERT INTO orders(user_id, product_code, category, title, price, sku, kind, "
                "target, nickname, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id, product_code, category, title, price, sku, kind,
                    target, nickname, ORDER_NEW, stamp, stamp,
                ),
            )
            order_id = int(cur.lastrowid)
            self._conn.execute(
                "INSERT INTO balance_log(user_id, delta, balance_after, reason, admin_id, created_at) "
                "VALUES (?, ?, ?, ?, NULL, ?)",
                (user_id, -price, new_balance, f"order#{order_id}", stamp),
            )
            self._conn.commit()
        return order_id

    def order(self, order_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM orders WHERE id = ?", (order_id,))

    def user_orders(self, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    def open_orders(self, limit: int = 20) -> list[sqlite3.Row]:
        marks = ", ".join("?" * len(ORDER_OPEN))
        return self._all(
            f"SELECT * FROM orders WHERE status IN ({marks}) ORDER BY id ASC LIMIT ?",
            (*ORDER_OPEN, limit),
        )

    def set_order_note(self, order_id: int, note: str) -> None:
        """Эзоҳро нигоҳ медорад — ҳолати фармоишро тағйир намедиҳад."""
        self._run(
            "UPDATE orders SET note = ?, updated_at = ? WHERE id = ?",
            (note, now(), order_id),
        )

    def set_order_status(
        self,
        order_id: int,
        status: str,
        *,
        external_id: str | None = None,
        note: str | None = None,
    ) -> sqlite3.Row | None:
        """Ҳолати фармоишро иваз мекунад.

        `done` — ҳисоби «харҷкарда» зиёд мешавад.
        `rejected` — пул ба харидор бармегардад.
        """
        if status not in ORDER_STATUSES:
            raise ValueError(f"status номаълум: {status}")
        stamp = now()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if row is None or row["status"] == status:
                self._conn.commit()
                return row
            was_open = row["status"] in ORDER_OPEN
            self._conn.execute(
                "UPDATE orders SET status = ?, updated_at = ?, "
                "external_id = COALESCE(?, external_id), note = COALESCE(?, note) WHERE id = ?",
                (status, stamp, external_id, note, order_id),
            )
            if status == ORDER_DONE and was_open:
                self._conn.execute(
                    "UPDATE users SET spent = spent + ?, orders_done = orders_done + 1 WHERE id = ?",
                    (row["price"], row["user_id"]),
                )
            elif status == ORDER_REJECTED and was_open:
                bal = self._conn.execute(
                    "SELECT balance FROM users WHERE id = ?", (row["user_id"],)
                ).fetchone()
                new_balance = (bal["balance"] if bal else 0) + row["price"]
                self._conn.execute(
                    "UPDATE users SET balance = ? WHERE id = ?", (new_balance, row["user_id"])
                )
                self._conn.execute(
                    "INSERT INTO balance_log(user_id, delta, balance_after, reason, admin_id, created_at) "
                    "VALUES (?, ?, ?, ?, NULL, ?)",
                    (row["user_id"], row["price"], new_balance, f"refund#{order_id}", stamp),
                )
            self._conn.commit()
            return self._conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()

    # ── пур кардани ҳисоб ─────────────────────────────────────────────
    def create_topup(self, user_id: int, amount: int, code: str) -> int:
        stamp = now()
        cur = self._run(
            "INSERT INTO topups(user_id, amount, code, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount, code, TOPUP_WAITING, stamp, stamp),
        )
        return int(cur.lastrowid)

    def topup(self, topup_id: int) -> sqlite3.Row | None:
        return self._one("SELECT * FROM topups WHERE id = ?", (topup_id,))

    def open_topups(self, limit: int = 20) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM topups WHERE status = ? ORDER BY id ASC LIMIT ?",
            (TOPUP_WAITING, limit),
        )

    def user_topups(self, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self._all(
            "SELECT * FROM topups WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )

    def confirm_topup(self, topup_id: int, admin_id: int) -> sqlite3.Row | None:
        """Пардохтро тасдиқ мекунад ва пулро ба ҳисоб мегузорад."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM topups WHERE id = ?", (topup_id,)
            ).fetchone()
            if row is None or row["status"] != TOPUP_WAITING:
                return row
            self._conn.execute(
                "UPDATE topups SET status = ?, admin_id = ?, updated_at = ? WHERE id = ?",
                (TOPUP_PAID, admin_id, now(), topup_id),
            )
            self._conn.commit()
        self.change_balance(
            row["user_id"], row["amount"], f"topup#{topup_id}", admin_id=admin_id
        )
        return self.topup(topup_id)

    def reject_topup(self, topup_id: int, admin_id: int) -> sqlite3.Row | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM topups WHERE id = ?", (topup_id,)
            ).fetchone()
            if row is None or row["status"] != TOPUP_WAITING:
                return row
            self._conn.execute(
                "UPDATE topups SET status = ?, admin_id = ?, updated_at = ? WHERE id = ?",
                (TOPUP_REJECTED, admin_id, now(), topup_id),
            )
            self._conn.commit()
        return self.topup(topup_id)

    # ── танзимоти дохилӣ ──────────────────────────────────────────────
    def setting(self, key: str, default: str = "") -> str:
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._run(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ── омор ──────────────────────────────────────────────────────────
    def stats(self) -> dict[str, int]:
        def scalar(sql: str, params: Iterable[Any] = ()) -> int:
            row = self._one(sql, tuple(params))
            return int(row[0] or 0) if row else 0

        return {
            "users": scalar("SELECT COUNT(*) FROM users"),
            "blocked": scalar("SELECT COUNT(*) FROM users WHERE is_blocked = 1"),
            "balance": scalar("SELECT SUM(balance) FROM users"),
            "orders": scalar("SELECT COUNT(*) FROM orders"),
            "orders_open": scalar(
                "SELECT COUNT(*) FROM orders WHERE status IN (?, ?)", ORDER_OPEN
            ),
            "orders_done": scalar(
                "SELECT COUNT(*) FROM orders WHERE status = ?", (ORDER_DONE,)
            ),
            "revenue": scalar(
                "SELECT SUM(price) FROM orders WHERE status = ?", (ORDER_DONE,)
            ),
            "topups_open": scalar(
                "SELECT COUNT(*) FROM topups WHERE status = ?", (TOPUP_WAITING,)
            ),
            "topups_paid": scalar(
                "SELECT SUM(amount) FROM topups WHERE status = ?", (TOPUP_PAID,)
            ),
        }
