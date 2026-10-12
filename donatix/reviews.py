"""Отзывы покупателей: оценка 1–5 и текст к выполненному заказу, ответ магазина под отзывом.

Правила:
- оставить отзыв можно только к своему ВЫПОЛНЕННОМУ заказу (значок «покупка подтверждена»), один на заказ;
- пока магазин не ответил, отзыв можно исправить;
- магазин (админ) отвечает под отзывом — клиенту приходит уведомление; ответ можно поправить;
- админ может скрыть отзыв (спам, оскорбления) — он пропадает со страницы «Отзывы», но не удаляется.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db

MAX_TEXT = 1000
MAX_REPLY = 1500


class ReviewError(Exception):
    pass


def _game(conn: sqlite3.Connection, order: sqlite3.Row) -> str:
    p = conn.execute("SELECT category_name FROM products WHERE id = ?", (order["product_id"],)).fetchone()
    name = (p["category_name"] if p else "") or order["product_name"].split(" — ")[0]
    return name[:60]


def _product(order: sqlite3.Row, game: str) -> str:
    name = order["product_name"]
    if game and name.startswith(game + " — "):
        name = name[len(game) + 3:]
    return name[:80]


def can_review(conn: sqlite3.Connection, user_id: int, public_id: str) -> sqlite3.Row | None:
    """Свой выполненный заказ без отзыва — можно оставить отзыв."""
    o = conn.execute("SELECT * FROM orders WHERE public_id = ? AND user_id = ? AND status = 'completed'",
                     (public_id, user_id)).fetchone()
    if o is None or conn.execute("SELECT 1 FROM reviews WHERE order_id = ?", (o["id"],)).fetchone():
        return None
    return o


def by_order(conn: sqlite3.Connection, order_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM reviews WHERE order_id = ?", (order_id,)).fetchone()


def _clean(rating: Any, text: str) -> tuple[int, str]:
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        raise ReviewError("Поставьте оценку — от 1 до 5 звёзд.")
    text = " ".join((text or "").split())[:MAX_TEXT]
    if len(text) < 3:
        raise ReviewError("Напишите пару слов о заказе.")
    return rating, text


def add(conn: sqlite3.Connection, config: Any, user: sqlite3.Row, public_id: str, rating: Any, text: str) -> int:
    rating, text = _clean(rating, text)
    o = conn.execute("SELECT * FROM orders WHERE public_id = ? AND user_id = ?", (public_id, user["id"])).fetchone()
    if o is None:
        raise ReviewError("Заказ не найден.")
    if o["status"] != "completed":
        raise ReviewError("Отзыв можно оставить, когда заказ выполнен.")
    old = by_order(conn, o["id"])
    game = _game(conn, o)
    if old is not None:
        if old["reply_text"]:
            raise ReviewError("Магазин уже ответил на отзыв — изменить его нельзя.")
        conn.execute("UPDATE reviews SET rating = ?, text = ?, updated_at = ? WHERE id = ?",
                     (rating, text, db.now(), old["id"]))
        return int(old["id"])
    rid = int(conn.execute(
        "INSERT INTO reviews (user_id, order_id, rating, text, game, product, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user["id"], o["id"], rating, text, game, _product(o, game), db.now(), db.now())).lastrowid)
    from .notify import notify
    for a in conn.execute("SELECT id FROM users WHERE role = 'admin'"):
        notify(conn, config, a["id"], f"Новый отзыв {'★' * rating}{'☆' * (5 - rating)} от {user['login']}: {text[:120]}",
               "/admin/reviews")
    return rid


def reply(conn: sqlite3.Connection, config: Any, admin: sqlite3.Row, rid: int, text: str) -> None:
    text = (text or "").strip()[:MAX_REPLY]
    r = conn.execute("SELECT * FROM reviews WHERE id = ?", (rid,)).fetchone()
    if r is None:
        raise ReviewError("Отзыв не найден.")
    if not text:   # пустой ответ — убрать ответ
        conn.execute("UPDATE reviews SET reply_text = NULL, reply_at = NULL, reply_by = NULL, updated_at = ? "
                     "WHERE id = ?", (db.now(), rid))
        return
    first = not r["reply_text"]
    conn.execute("UPDATE reviews SET reply_text = ?, reply_at = ?, reply_by = ?, updated_at = ? WHERE id = ?",
                 (text, db.now(), admin["id"], db.now(), rid))
    if first:
        from .notify import notify
        notify(conn, config, r["user_id"], f"Магазин ответил на ваш отзыв: {text[:160]}", "/reviews#r" + str(rid))


def set_hidden(conn: sqlite3.Connection, rid: int, hidden: bool) -> None:
    conn.execute("UPDATE reviews SET hidden = ?, updated_at = ? WHERE id = ?", (1 if hidden else 0, db.now(), rid))


def _view(r: sqlite3.Row) -> dict[str, Any]:
    name = r["login"] or "Покупатель"
    words = name.replace("_", " ").replace(".", " ").split()
    initials = ((words[0][:1] + (words[1][:1] if len(words) > 1 else words[0][1:2])) if words else "?").upper()
    hue = sum(map(ord, name)) % 360   # у каждого свой цвет кружка
    return {"id": r["id"], "name": name, "initials": initials, "hue": hue, "rating": r["rating"], "text": r["text"],
            "game": r["game"], "product": r["product"], "reply": r["reply_text"], "reply_at": r["reply_at"],
            "created_at": r["created_at"], "hidden": bool(r["hidden"]), "order": r["public_id"],
            "user_id": r["user_id"]}


_SELECT = ("SELECT r.*, u.login, o.public_id FROM reviews r JOIN users u ON u.id = r.user_id "
           "LEFT JOIN orders o ON o.id = r.order_id")


def listing(conn: sqlite3.Connection, stars: int = 0, include_hidden: bool = False, unanswered: bool = False,
            limit: int = 30, offset: int = 0) -> list[dict[str, Any]]:
    where, args = [], []
    if not include_hidden:
        where.append("r.hidden = 0")
    if 1 <= stars <= 5:
        where.append("r.rating = ?")
        args.append(stars)
    if unanswered:
        where.append("r.reply_text IS NULL")
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY r.id DESC LIMIT ? OFFSET ?"
    return [_view(r) for r in conn.execute(sql, (*args, limit, offset))]


def summary(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT rating, COUNT(*) FROM reviews WHERE hidden = 0 GROUP BY rating").fetchall()
    counts = {i: 0 for i in range(1, 6)}
    for rating, n in rows:
        counts[rating] = n
    total = sum(counts.values())
    avg = sum(k * v for k, v in counts.items()) / total if total else 0
    return {"total": total, "avg": round(avg, 1), "counts": counts,
            "pct": {k: round(v * 100 / total) if total else 0 for k, v in counts.items()},
            "unanswered": conn.execute("SELECT COUNT(*) FROM reviews WHERE reply_text IS NULL AND hidden = 0")
            .fetchone()[0]}
