"""Турнир друзей в боте-магазине: кто за неделю привёл больше настоящих друзей — призы на баланс.

Друг приходит по ссылке t.me/<бот>?start=t_<Telegram ID пригласившего>. Баллы пригласившему за каждого друга,
пришедшего в эту неделю:
  +1 — друг НОВЫЙ (раньше бот не запускал), нажал «Я не бот» (выбрал нужный эмодзи) и подписан на канал турнира;
       вышел из канала — балл снимается (−1), вернулся — снова +1;
  +5 — друг сделал покупку (выполненный заказ после прихода).

Защита от накрутки: себя пригласить нельзя, не больше DAY_LIMIT друзей за сутки на одного, друг без «Я не бот»
не считается, перед выдачей призов подписка каждого друга проверяется заново, админ может снять участника.

Неделя — как у конкурса сайта: до воскресенья 20:00 по местному времени. Итоги подводит бот сам:
топ-3 получают призы (в сомони по курсу) на баланс, им и админу приходит сообщение.

Значок турнира — премиум-эмодзи или стикер: админ присылает в бот сообщение с ним, бот сам достаёт его ID.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Any, Callable

from . import accounts, db
from .contest import _iso, _local, week_bounds

SUB_POINTS, BUY_POINTS = 1, 5
DAY_LIMIT = 20                     # друзей за сутки на одного пригласившего — больше похоже на накрутку
DEFAULT_PRIZES = (100, 50, 30)     # сомони за 1, 2, 3 место
CAPTCHA = ("💎", "🎮", "⭐", "🎁")  # «Я не бот»: нажать названный эмодзи


# ── Настройки (меняет админ в боте) ──

def enabled(conn: sqlite3.Connection) -> bool:
    return db.get_setting(conn, "tour.on") == "1"


def set_enabled(conn: sqlite3.Connection, on: bool) -> None:
    db.set_setting(conn, "tour.on", "1" if on else "0")


def channel(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Канал турнира: {chat_id, title, url} или None — тогда +1 дают сразу после «Я не бот»."""
    try:
        ch = json.loads(db.get_setting(conn, "tour.channel") or "null")
    except ValueError:
        return None
    return ch if isinstance(ch, dict) and ch.get("chat_id") else None


def set_channel(conn: sqlite3.Connection, ch: dict[str, Any] | None) -> None:
    db.set_setting(conn, "tour.channel", json.dumps(ch, ensure_ascii=False) if ch else "")


def prizes(conn: sqlite3.Connection) -> list[int]:
    try:
        got = [max(0, int(x)) for x in (db.get_setting(conn, "tour.prizes") or "").split(",") if x.strip()][:3]
    except ValueError:
        got = []
    return got if len(got) == 3 else list(DEFAULT_PRIZES)


def set_prizes(conn: sqlite3.Connection, text: str) -> list[int] | None:
    nums = [int(x) for x in text.replace(",", " ").split() if x.isdigit()]
    if len(nums) != 3:
        return None
    db.set_setting(conn, "tour.prizes", ",".join(str(n) for n in nums))
    return nums


def badge(conn: sqlite3.Connection) -> dict[str, str]:
    """Значок турнира: {"emoji_id": ID премиум-эмодзи, "emoji": его обычный вид, "sticker": file_id стикера}."""
    try:
        got = json.loads(db.get_setting(conn, "tour.badge") or "{}")
    except ValueError:
        got = {}
    return got if isinstance(got, dict) else {}


def badge_from_message(msg: dict[str, Any]) -> dict[str, str] | None:
    """Бот сам находит премиум-эмодзи в тексте (entities custom_emoji) или стикер в сообщении админа."""
    text = msg.get("text") or msg.get("caption") or ""
    for ent in (msg.get("entities") or msg.get("caption_entities") or []):
        if ent.get("type") == "custom_emoji" and ent.get("custom_emoji_id"):
            # смещения Telegram — в UTF-16: так достаём сам символ, который виден без Premium
            raw = text.encode("utf-16-le")[ent["offset"] * 2:(ent["offset"] + ent["length"]) * 2]
            return {"emoji_id": str(ent["custom_emoji_id"]), "emoji": raw.decode("utf-16-le", "ignore") or "🏆"}
    st = msg.get("sticker")
    if st and st.get("file_id"):
        out = {"sticker": st["file_id"], "emoji": st.get("emoji") or "🏆"}
        if st.get("custom_emoji_id"):   # эмодзи-стикер из премиум-набора — годится и как значок в тексте
            out["emoji_id"] = str(st["custom_emoji_id"])
        return out
    return None


def set_badge(conn: sqlite3.Connection, b: dict[str, str] | None) -> None:
    db.set_setting(conn, "tour.badge", json.dumps(b or {}, ensure_ascii=False))


# ── Друзья ──

def friend(conn: sqlite3.Connection, tg: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM bot_tour WHERE friend_tg = ?", (tg,)).fetchone()


def add_friend(conn: sqlite3.Connection, friend_tg: int, friend_user: int, inviter_tg: int) -> str:
    """Записать нового друга. Вернёт "" — записан, иначе причину, почему не засчитан."""
    if friend_tg == inviter_tg:
        return "self"
    inv = conn.execute("SELECT user_id FROM shop_users WHERE tg_id = ?", (inviter_tg,)).fetchone()
    if inv is None:
        return "no_inviter"
    day_ago = _iso(_now() - timedelta(days=1))
    n = conn.execute("SELECT COUNT(*) FROM bot_tour WHERE inviter_tg = ? AND joined_at >= ?",
                     (inviter_tg, day_ago)).fetchone()[0]
    if n >= DAY_LIMIT:
        return "limit"
    cur = conn.execute("INSERT OR IGNORE INTO bot_tour (friend_tg, inviter_tg, friend_user, inviter_user, joined_at) "
                       "VALUES (?, ?, ?, ?, ?)", (friend_tg, inviter_tg, friend_user, inv["user_id"], db.now()))
    return "" if cur.rowcount else "dup"


def captcha_try(conn: sqlite3.Connection, friend_tg: int, ok: bool) -> int:
    """Ответ на «Я не бот». Вернёт: 1 — прошёл, 0 — ошибся (можно ещё), -1 — попытки кончились."""
    if ok:
        conn.execute("UPDATE bot_tour SET human = 1 WHERE friend_tg = ?", (friend_tg,))
        return 1
    conn.execute("UPDATE bot_tour SET tries = tries + 1 WHERE friend_tg = ?", (friend_tg,))
    row = friend(conn, friend_tg)
    return -1 if row is None or row["tries"] >= 3 else 0


def set_subscribed(conn: sqlite3.Connection, friend_tg: int, on: bool) -> sqlite3.Row | None:
    """Подписка друга изменилась. Вернёт запись, если это меняет баллы (друг прошёл «Я не бот»)."""
    row = friend(conn, friend_tg)
    if row is None or bool(row["subscribed"]) == on:
        return None
    conn.execute("UPDATE bot_tour SET subscribed = ? WHERE friend_tg = ?", (1 if on else 0, friend_tg))
    return row if row["human"] and not row["banned"] else None


def ban(conn: sqlite3.Connection, inviter_tg: int) -> int:
    """Снять участника за накрутку: все его друзья этой и прошлых недель не считаются."""
    return conn.execute("UPDATE bot_tour SET banned = 1 WHERE inviter_tg = ?", (inviter_tg,)).rowcount


# ── Баллы и таблица ──

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def leaderboard(conn: sqlite3.Connection, start, end, limit: int | None = 10) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT t.inviter_tg, t.inviter_user, s.name, "
        " SUM(CASE WHEN t.human = 1 AND t.subscribed = 1 THEN 1 ELSE 0 END) AS subs, "
        " SUM(CASE WHEN EXISTS (SELECT 1 FROM orders o WHERE o.user_id = t.friend_user AND o.status = 'completed' "
        "     AND o.created_at >= t.joined_at) THEN 1 ELSE 0 END) AS buys, "
        " MIN(t.joined_at) AS first "
        "FROM bot_tour t LEFT JOIN shop_users s ON s.tg_id = t.inviter_tg "
        "WHERE t.banned = 0 AND t.joined_at >= ? AND t.joined_at < ? GROUP BY t.inviter_tg",
        (_iso(start), _iso(end))).fetchall()
    out = [{"tg": r["inviter_tg"], "user_id": r["inviter_user"], "name": r["name"] or "Игрок",
            "subs": r["subs"], "buys": r["buys"], "points": r["subs"] * SUB_POINTS + r["buys"] * BUY_POINTS,
            "first": r["first"]} for r in rows]
    out = [r for r in out if r["points"] > 0]
    out.sort(key=lambda r: (-r["points"], r["first"]))
    for i, r in enumerate(out):
        r["place"] = i + 1
    return out[:limit] if limit else out


def mask(name: str) -> str:
    name = (name or "Игрок").strip()
    return name[:2] + "***" if len(name) > 2 else name + "***"


def view(conn: sqlite3.Connection, tz: int, tg: int) -> dict[str, Any]:
    start, end = week_bounds(tz)
    full = leaderboard(conn, start, end, None)
    me = next((r for r in full if r["tg"] == tg), None)
    return {"end": end.astimezone(_local(tz)), "left": end - _now(), "top": full[:10], "me": me,
            "prizes": prizes(conn), "channel": channel(conn)}


def settle(conn: sqlite3.Connection, config: Any, is_member: Callable[[Any, int], bool | None]) -> list[dict]:
    """Итоги прошедшей недели (один раз): перепроверить подписки, топ-3 — призы на баланс. Вернёт победителей."""
    if not enabled(conn):
        return []
    start, _ = week_bounds(config.tz_offset)
    prev_start, prev_end = start - timedelta(days=7), start
    week = prev_end.astimezone(_local(config.tz_offset)).strftime("%Y-%m-%d")
    if db.get_setting(conn, f"tour.done.{week}"):
        return []
    ch = channel(conn)
    if ch:   # вышел из канала, а бот не узнал (не был админом, перезапуск) — перед призами проверяем всех
        for r in conn.execute("SELECT friend_tg FROM bot_tour WHERE subscribed = 1 AND joined_at >= ? AND joined_at < ?",
                              (_iso(prev_start), _iso(prev_end))).fetchall():
            member = is_member(ch["chat_id"], r["friend_tg"])
            if member is False:
                conn.execute("UPDATE bot_tour SET subscribed = 0 WHERE friend_tg = ?", (r["friend_tg"],))
    from . import payments
    rate = payments.settings(conn, config)["tjs_rate"]
    top = leaderboard(conn, prev_start, prev_end, 3)
    won = []
    with db.tx(conn):
        if db.get_setting(conn, f"tour.done.{week}"):
            return []
        for r, tjs in zip(top, prizes(conn)):
            if tjs <= 0:
                continue
            micro = int((Decimal(tjs) / rate * 10000).quantize(Decimal(1), rounding=ROUND_DOWN))
            conn.execute("INSERT INTO bot_tour_winners (week, place, inviter_tg, user_id, points, prize_tjs, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (week, r["place"], r["tg"], r["user_id"], r["points"], tjs, db.now()))
            accounts.post_ledger(conn, r["user_id"], micro, f"Турнир друзей {week}: {r['place']} место ({tjs} сомони)")
            won.append({**r, "prize": tjs, "week": week})
        db.set_setting(conn, f"tour.done.{week}", "1")
    return won
