"""Номера заказов для покупок вне таблицы orders: у каждой покупки есть номер, по нему её находят.

Обычные заказы (игры, Stars, Premium) — dx-<id>. Остальные:
  GL-<id> — Glory (glory_orders), VN-<id> — виртуальный номер (vnumbers), GF-<id> — подарок Telegram (gift_orders).
Номер выводится из id — у старых покупок он есть тоже.
"""

from __future__ import annotations

import re

PREFIX = {"glory": "GL", "vnum": "VN", "gift": "GF"}
TABLE = {"glory": "glory_orders", "vnum": "vnumbers", "gift": "gift_orders"}
_RE = re.compile(r"^\s*#?(GL|VN|GF)[-\s]?(\d+)\s*$", re.I)


def ref(kind: str, obj_id: int) -> str:
    return f"{PREFIX[kind]}-{obj_id}"


def parse(text: str) -> tuple[str, int] | None:
    """«GL-12», «gl12», «#VN-7» → (kind, id)."""
    m = _RE.match(text or "")
    if not m:
        return None
    kind = next(k for k, p in PREFIX.items() if p == m.group(1).upper())
    return kind, int(m.group(2))


def owner(conn, text: str) -> int | None:
    """Чей это заказ (user_id) — для поиска в админке по номеру."""
    got = parse(text)
    if got is None:
        return None
    try:
        row = conn.execute(f"SELECT user_id FROM {TABLE[got[0]]} WHERE id = ?", (got[1],)).fetchone()
    except Exception:  # noqa: BLE001 — таблицы подарков ещё нет
        return None
    return row[0] if row else None


GLORY_STATUS = {"starting": "запускается", "running": "работает", "stopped": "завершён", "failed": "ошибка"}
VNUM_STATUS = {"PENDING": "ждём код", "RECEIVED": "код пришёл", "FINISHED": "выполнен", "CANCELED": "отменён",
               "TIMEOUT": "код не пришёл", "BANNED": "номер заблокирован", "FAILED": "ошибка"}


def _rows(conn, sql: str, args: tuple) -> list:
    try:
        return conn.execute(sql, args).fetchall()
    except Exception:  # noqa: BLE001 — таблицы подарков нет, пока подарки не включали
        return []


def history(conn, user_id: int, limit: int = 50) -> list[dict]:
    """Glory, виртуальные номера и подарки клиента одним списком (свежие сверху) — для профиля в админке."""
    out = []
    for r in _rows(conn, "SELECT * FROM glory_orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)):
        out.append({"ref": ref("glory", r["id"]), "title": f"Glory · клан {r['clan_id']} · {r['region']}",
                    "price_micro": r["price_micro"], "created_at": r["created_at"], "refunded": r["refunded"],
                    "status": GLORY_STATUS.get(r["status"], r["status"]),
                    "bad": r["status"] == "failed", "ok": r["status"] == "stopped", "note": r["note"]})
    for r in _rows(conn, "SELECT * FROM vnumbers WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)):
        out.append({"ref": ref("vnum", r["id"]),
                    "title": f"Номер {r['service']} · {r['country']}" + (f" · {r['phone']}" if r["phone"] else "")
                             + (f" · код {r['code']}" if r["code"] else ""),
                    "price_micro": r["price_micro"], "created_at": r["created_at"], "refunded": r["refunded"],
                    "status": VNUM_STATUS.get(r["status"], r["status"]),
                    "bad": r["status"] in ("FAILED", "BANNED", "TIMEOUT", "CANCELED"),
                    "ok": r["status"] in ("RECEIVED", "FINISHED"), "note": r["note"]})
    from .tggifts import STATUS_TITLES
    for r in _rows(conn, "SELECT * FROM gift_orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)):
        out.append({"ref": ref("gift", r["id"]),
                    "title": f"Подарок Telegram ⭐{r['star_count']} → {r['recipient'] or '?'}"
                             + (f" (ID {r['recipient_id']})" if r["recipient_id"] else ""),
                    "price_micro": r["price_micro"], "created_at": r["created_at"],
                    "refunded": int(r["status"] in ("failed", "refunded")),
                    "status": STATUS_TITLES.get(r["status"], r["status"]),
                    "bad": r["status"] in ("failed", "refunded"), "ok": r["status"] == "sent", "note": r["error"] or ""})
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out[:limit]


def telegram_of(conn, user_id: int) -> list[dict]:
    """Какие Telegram-аккаунты привязаны к клиенту (бот-магазин, мини-приложение): ID, имя, @ник."""
    out = []
    for r in _rows(conn, "SELECT s.tg_id, s.name, s.created_at, s.last_seen, g.username FROM shop_users s "
                         "LEFT JOIN gift_users g ON g.tg_id = s.tg_id WHERE s.user_id = ?", (user_id,)):
        out.append(dict(r))
    if not out:   # gift_users нет — без ника
        out = [dict(r) | {"username": None} for r in _rows(
            conn, "SELECT tg_id, name, created_at, last_seen FROM shop_users WHERE user_id = ?", (user_id,))]
    return out


def user_by_telegram(conn, q: str) -> int | None:
    """Поиск клиента по Telegram ID (цифры) или @нику."""
    q = (q or "").strip()
    if q.isdigit():
        row = _rows(conn, "SELECT user_id FROM shop_users WHERE tg_id = ?", (int(q),))
        return row[0][0] if row else None
    if q.startswith("@") and len(q) > 2:
        row = _rows(conn, "SELECT s.user_id FROM gift_users g JOIN shop_users s ON s.tg_id = g.tg_id "
                          "WHERE g.username = ?", (q[1:].lower(),))
        return row[0][0] if row else None
    return None
