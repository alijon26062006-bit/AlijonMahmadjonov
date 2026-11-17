"""Розыгрыш призов за покупки (итоги — в прямом эфире).

Правила:
- считаются только покупки ДЛЯ СЕБЯ: сайт, покупка без регистрации, мини-приложение, бот-магазин
  (не API и не боты партнёров), выполненные заказы с момента запуска розыгрыша;
- покупок на $15 и больше = ОДИН билет с номером (один человек — один билет); билет — только тем, кто нажал «Участвую»
  и написал свой ник Instagram (покупки с начала розыгрыша засчитываются и тем, кто нажал позже);
- подписка на Telegram-канал проверяется автоматически (бот-магазин — админ канала);
  Instagram проверяет ведущий в эфире — ник виден в админке рядом с победителем;
- один человек выигрывает один раз. Призы — на баланс Donatix (сомони по курсу).

Розыгрыш в эфире: админка → «Розыгрыш» → «Выбрать победителя» (с последнего места к первому). Выбор —
криптографически случайный билет среди билетов участников. Победитель не подписан — «Перевыбрать»;
подписан — «Подтвердить»: приз зачисляется на баланс.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Any

import httpx

from . import accounts, db
from .config import Config

log = logging.getLogger(__name__)

SOURCES = ("panel", "quick", "tgapp", "shopbot")          # покупки для себя; 'api' — партнёры, не считаются
DEFAULT_PRIZES = [[1, 250], [1, 200], [1, 100], [7, 50], [40, 40]]   # [сколько мест, сомони каждому]
DEFAULT_DRAW = "2026-12-18"
DEFAULT_MIN_USD = 15
TG_RECHECK_SECONDS = 600

SCHEMA = """
CREATE TABLE IF NOT EXISTS raffle_entries (
    user_id    INTEGER PRIMARY KEY,
    instagram  TEXT NOT NULL,
    tg_ok      INTEGER,                  -- 1 подписан, 0 нет, NULL — не удалось проверить
    tg_at      TEXT,
    joined_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS raffle_tickets (
    no         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS raffle_tickets_user ON raffle_tickets(user_id);
CREATE TABLE IF NOT EXISTS raffle_winners (
    id         INTEGER PRIMARY KEY,
    place      INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    ticket     INTEGER NOT NULL,
    prize_tjs  INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'drawn',   -- drawn (ждёт проверки) | paid | void (перевыбран)
    amount_micro INTEGER NOT NULL DEFAULT 0,
    drawn_at   TEXT NOT NULL
);
"""


class RaffleError(ValueError):
    pass


def ensure(conn: sqlite3.Connection) -> None:
    # executescript закрывает открытую транзакцию — поэтому только если таблиц ещё нет (обычно их создаёт db.init)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'raffle_winners'").fetchone():
        conn.executescript(SCHEMA)


# ── настройки ──

def cfg(conn: sqlite3.Connection) -> dict[str, Any]:
    g = lambda k, d="": db.get_setting(conn, "raffle." + k) or d   # noqa: E731
    try:
        prizes = [[int(n), int(p)] for n, p in json.loads(g("prizes") or "null") or DEFAULT_PRIZES if int(n) > 0]
    except (ValueError, TypeError):
        prizes = DEFAULT_PRIZES
    try:
        channel = json.loads(g("channel") or "null") or {}
    except ValueError:
        channel = {}
    try:
        min_usd = max(1, int(g("min_usd", str(DEFAULT_MIN_USD))))
    except ValueError:
        min_usd = DEFAULT_MIN_USD
    return {"on": g("on") == "1", "start": g("start"), "draw": g("draw", DEFAULT_DRAW), "min_usd": min_usd,
            "prizes": prizes, "channel": channel if isinstance(channel, dict) else {},
            "instagram": g("instagram"), "closed": g("closed") == "1"}


def active(conn: sqlite3.Connection) -> bool:
    c = cfg(conn)
    return c["on"] and bool(c["start"])


def clean_instagram(raw: str) -> str:
    """Ник Instagram из «@nick», «nick» или ссылки instagram.com/nick."""
    raw = (raw or "").strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)", raw)
    nick = (m.group(1) if m else raw).lstrip("@").strip().strip("/").lower()
    if not re.fullmatch(r"[a-z0-9._]{2,30}", nick) or nick.startswith(".") or nick.endswith("."):
        raise RaffleError("Напишите свой ник Instagram, например @ali_2006. / Номи Instagram-и худро нависед.")
    return nick


def save_settings(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    ensure(conn)
    if "prizes" in data:
        rows = []
        for line in str(data["prizes"]).replace(";", "\n").splitlines():
            m = re.fullmatch(r"\s*(\d{1,3})\s*[x×*хХ]\s*(\d{1,6})\s*", line)
            if line.strip() and not m:
                raise RaffleError("Призы: каждая строка «сколько мест x сомони», например 7 x 50.")
            if m and int(m.group(1)) > 0:
                rows.append([int(m.group(1)), int(m.group(2))])
        if not rows or sum(n for n, _ in rows) > 500:
            raise RaffleError("Призы: от 1 до 500 мест.")
        db.set_setting(conn, "raffle.prizes", json.dumps(rows))
    if "draw" in data:
        try:
            datetime.strptime(str(data["draw"]), "%Y-%m-%d")
        except ValueError:
            raise RaffleError("Дата итогов — в виде 2026-12-18.") from None
        db.set_setting(conn, "raffle.draw", str(data["draw"]))
    if "min_usd" in data:
        if not str(data["min_usd"]).isdigit() or not 1 <= int(data["min_usd"]) <= 1000:
            raise RaffleError("Минимум покупок — число долларов, например 15.")
        db.set_setting(conn, "raffle.min_usd", str(int(data["min_usd"])))
    if "instagram" in data:
        raw = str(data["instagram"]).strip()
        db.set_setting(conn, "raffle.instagram", "https://instagram.com/" + clean_instagram(raw) if raw else "")
    if "channel_id" in data or "channel_url" in data:
        chat = str(data.get("channel_id", "")).strip()
        url = str(data.get("channel_url", "")).strip()
        if chat and not re.fullmatch(r"@[A-Za-z0-9_]{5,64}|-100\d{6,20}", chat):
            raise RaffleError("Канал для проверки: @имя_канала или ID вида -100…")
        if url and not re.fullmatch(r"https://t\.me/[+A-Za-z0-9_/-]{3,120}", url):
            raise RaffleError("Ссылка на канал — вида https://t.me/…")
        if chat.startswith("@") and not url:
            url = "https://t.me/" + chat[1:]
        db.set_setting(conn, "raffle.channel", json.dumps({"chat_id": chat, "url": url}) if chat or url else "")


def start(conn: sqlite3.Connection) -> None:
    """Запуск: покупки считаются с этой минуты. Повторный запуск после паузы время начала не сбрасывает."""
    ensure(conn)
    if not db.get_setting(conn, "raffle.start"):
        db.set_setting(conn, "raffle.start", db.now())
    db.set_setting(conn, "raffle.on", "1")


def stop(conn: sqlite3.Connection) -> None:
    db.set_setting(conn, "raffle.on", "0")


def reset(conn: sqlite3.Connection) -> None:
    """Новый розыгрыш с нуля: участники, билеты и победители стираются (призы на балансах остаются)."""
    ensure(conn)
    for t in ("raffle_entries", "raffle_tickets", "raffle_winners"):
        conn.execute(f"DELETE FROM {t}")
    conn.execute("DELETE FROM sqlite_sequence WHERE name = 'raffle_tickets'")
    for k in ("start", "on", "closed"):
        db.set_setting(conn, "raffle." + k, "")


# ── призы ──

def places(conn: sqlite3.Connection) -> list[int]:
    """Приз (сомони) для каждого места: [250, 200, 100, 50, …]."""
    out: list[int] = []
    for n, tjs in cfg(conn)["prizes"]:
        out += [tjs] * n
    return out


def prize_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Для страницы: «1 место — 250 с.», «4–10 места · 7 человек — 50 с.». Общую сумму не показываем."""
    rows, at = [], 1
    for n, tjs in cfg(conn)["prizes"]:
        rows.append({"from": at, "to": at + n - 1, "n": n, "tjs": tjs})
        at += n
    return rows


# ── покупки, билеты, участие ──

def spent_micro(conn: sqlite3.Connection, user_id: int, since: str) -> int:
    marks = ",".join("?" * len(SOURCES))
    return int(conn.execute(
        f"SELECT COALESCE(SUM(total_micro), 0) FROM orders WHERE user_id = ? AND status = 'completed' "
        f"AND source IN ({marks}) AND created_at >= ?", (user_id, *SOURCES, since)).fetchone()[0])


def entry(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    ensure(conn)
    return conn.execute("SELECT * FROM raffle_entries WHERE user_id = ?", (user_id,)).fetchone()


def my_tickets(conn: sqlite3.Connection, user_id: int) -> list[int]:
    return [r[0] for r in conn.execute("SELECT no FROM raffle_tickets WHERE user_id = ? ORDER BY no", (user_id,))]


def sync(conn: sqlite3.Connection, user_id: int) -> list[int]:
    """Выдать билет участнику, когда набрал min_usd покупок. Один человек — один билет. Возвращает НОВЫЕ номера."""
    c = cfg(conn)
    if not (c["on"] and c["start"]) or c["closed"] or entry(conn, user_id) is None:
        return []
    due = 1 if spent_micro(conn, user_id, c["start"]) >= c["min_usd"] * 10_000 else 0
    have = conn.execute("SELECT COUNT(*) FROM raffle_tickets WHERE user_id = ?", (user_id,)).fetchone()[0]
    new = []
    for _ in range(max(0, int(due) - have)):
        new.append(int(conn.execute("INSERT INTO raffle_tickets (user_id, created_at) VALUES (?, ?)",
                                    (user_id, db.now())).lastrowid))
    return new


def sync_all(conn: sqlite3.Connection) -> int:
    return sum(len(sync(conn, r[0])) for r in conn.execute("SELECT user_id FROM raffle_entries").fetchall())


def tg_id_of(conn: sqlite3.Connection, user_id: int) -> int | None:
    row = conn.execute("SELECT tg_id FROM shop_users WHERE user_id = ? ORDER BY last_seen DESC LIMIT 1",
                       (user_id,)).fetchone()
    return int(row[0]) if row else None


def tg_member(config: Config, chat_id: str, tg_id: int, api: Any = None) -> bool | None:
    """Подписан ли на канал (через бот-магазин, он должен быть админом канала). None — проверить не удалось."""
    try:
        if api is not None:
            m = api("getChatMember", chat_id=chat_id, user_id=tg_id) or {}
        else:
            if not config.shop_bot_token:
                return None
            resp = httpx.post(f"https://api.telegram.org/bot{config.shop_bot_token}/getChatMember",
                              json={"chat_id": chat_id, "user_id": tg_id}, timeout=8)
            body = resp.json() or {}
            if not body.get("ok"):
                desc = str(body.get("description") or "")
                if "user not found" in desc.lower() or "participant" in desc.lower():
                    return False
                log.warning("розыгрыш: подписка %s не проверена: %s", chat_id, desc)
                return None
            m = body.get("result") or {}
    except Exception as exc:  # noqa: BLE001 — сеть/бот не админ: не мешаем участию, проверим позже
        log.warning("розыгрыш: подписка не проверена: %s", exc)
        return None
    return m.get("status") in ("creator", "administrator", "member") or bool(m.get("is_member"))


def check_tg(conn: sqlite3.Connection, config: Config, user_id: int, api: Any = None, force: bool = True) -> bool | None:
    """Проверить подписку участника и записать. Канал не задан — None (нечего проверять)."""
    e = entry(conn, user_id)
    chat = cfg(conn)["channel"].get("chat_id")
    tg = tg_id_of(conn, user_id)
    if not chat or tg is None:
        return None
    if not force and e is not None and e["tg_at"]:
        try:
            age = (datetime.now(timezone.utc) - datetime.strptime(e["tg_at"][:19], "%Y-%m-%dT%H:%M:%S")
                   .replace(tzinfo=timezone.utc)).total_seconds()
        except ValueError:
            age = TG_RECHECK_SECONDS
        if age < TG_RECHECK_SECONDS:
            return None if e["tg_ok"] is None else bool(e["tg_ok"])
    ok = tg_member(config, chat, tg, api)
    if e is not None:
        conn.execute("UPDATE raffle_entries SET tg_ok = ?, tg_at = ? WHERE user_id = ?",
                     (None if ok is None else int(ok), db.now(), user_id))
    return ok


def join(conn: sqlite3.Connection, config: Config, user_id: int, instagram: str, api: Any = None) -> dict[str, Any]:
    """Кнопка «Участвую»: ник Instagram обязателен; нужен Telegram и подписка на канал (проверяется сразу)."""
    ensure(conn)
    c = cfg(conn)
    if not (c["on"] and c["start"]) or c["closed"]:
        raise RaffleError("Розыгрыш сейчас не идёт. / Ҳоло қуръакашӣ нест.")
    nick = clean_instagram(instagram)
    taken = conn.execute("SELECT user_id FROM raffle_entries WHERE instagram = ? AND user_id != ?",
                         (nick, user_id)).fetchone()
    if taken:
        raise RaffleError("Этот Instagram уже участвует с другого аккаунта. / Ин Instagram аллакай иштирок мекунад.")
    chat = c["channel"].get("chat_id")
    tg = tg_id_of(conn, user_id)
    if chat and tg is None:
        raise RaffleError("NEED_TG")
    ok = tg_member(config, chat, tg, api) if chat and tg is not None else None
    if ok is False:
        raise RaffleError("NEED_SUB")
    conn.execute("INSERT INTO raffle_entries (user_id, instagram, tg_ok, tg_at, joined_at) VALUES (?, ?, ?, ?, ?) "
                 "ON CONFLICT(user_id) DO UPDATE SET instagram = excluded.instagram, tg_ok = excluded.tg_ok, "
                 "tg_at = excluded.tg_at", (user_id, nick, None if ok is None else int(ok), db.now(), db.now()))
    new = sync(conn, user_id)
    return {"instagram": nick, "new_tickets": new}


def status(conn: sqlite3.Connection, config: Config, user_id: int | None) -> dict[str, Any] | None:
    """Всё для баннера, страницы и профиля. None — розыгрыша нет."""
    ensure(conn)
    c = cfg(conn)
    if not (c["on"] and c["start"]):
        return None
    try:
        draw = datetime.strptime(c["draw"], "%Y-%m-%d")
    except ValueError:
        draw = datetime.strptime(DEFAULT_DRAW, "%Y-%m-%d")
    local_now = datetime.now(timezone.utc) + timedelta(hours=config.tz_offset)
    days = max(0, (draw.date() - local_now.date()).days)
    out: dict[str, Any] = {
        "on": True, "closed": c["closed"], "min_usd": c["min_usd"], "prizes": prize_rows(conn),
        "top": places(conn)[:3], "winners_n": len(places(conn)),
        "draw": draw.strftime("%d.%m"), "draw_iso": c["draw"], "days": days,
        "channel_url": c["channel"].get("url") or config.tg_channel, "instagram_url": c["instagram"],
        "check_tg": bool(c["channel"].get("chat_id")),
        "joined": False, "instagram": "", "spent": "0.00", "need": f"{c['min_usd']:.2f}", "percent": 0,
        "tickets": [], "tg_linked": False, "tg_ok": None, "next_need": "",
    }
    if not user_id:
        return out
    e = entry(conn, user_id)
    spent = spent_micro(conn, user_id, c["start"])
    step = c["min_usd"] * 10_000
    out["tg_linked"] = tg_id_of(conn, user_id) is not None
    out["spent"] = f"{spent / 10_000:.2f}"
    out["need"] = f"{max(0, step - spent) / 10_000:.2f}"
    out["percent"] = min(100, int(spent * 100 // step))
    out["next_need"] = f"{(step - spent % step) / 10_000:.2f}"
    if e is not None:
        sync(conn, user_id)
        out.update(joined=True, instagram=e["instagram"], tickets=my_tickets(conn, user_id),
                   tg_ok=None if e["tg_ok"] is None else bool(e["tg_ok"]))
    won = conn.execute("SELECT place, prize_tjs FROM raffle_winners WHERE user_id = ? AND status = 'paid'",
                       (user_id,)).fetchone()
    out["won"] = dict(won) if won else None
    return out


def new_ticket_note(conn: sqlite3.Connection, user_id: int) -> str:
    """После выполненного заказа — строка для уведомления (бот, мини-приложение). Пусто — нечего сказать."""
    try:
        c = cfg(conn)
        if not (c["on"] and c["start"]) or c["closed"]:
            return ""
        if entry(conn, user_id) is None:
            spent = spent_micro(conn, user_id, c["start"])
            if spent >= c["min_usd"] * 10_000:
                return ("🎁 Шумо метавонед дар қуръакашӣ иштирок кунед — тугмаи «Иштирок мекунам»-ро пахш кунед!\n"
                        "Вы можете участвовать в розыгрыше — нажмите «Участвую»!")
            return ""
        new = sync(conn, user_id)
        if new:
            nums = ", ".join(f"№ {n:04d}" for n in new)
            return (f"🎟 Шумо иштирок мекунед! Чипта: <b>{nums}</b>\n"
                    f"Вы участвуете в розыгрыше! Билет: <b>{nums}</b>")
    except sqlite3.Error:
        log.exception("розыгрыш: билет после заказа")
    return ""


# ── розыгрыш в эфире (админка) ──

def board(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure(conn)
    ps = places(conn)
    rows = {r["place"]: dict(r) for r in conn.execute(
        "SELECT w.*, u.login, e.instagram, e.tg_ok, COALESCE(s.name, '') AS tg_name, s.tg_id FROM raffle_winners w "
        "JOIN users u ON u.id = w.user_id LEFT JOIN raffle_entries e ON e.user_id = w.user_id "
        "LEFT JOIN shop_users s ON s.user_id = w.user_id WHERE w.status != 'void' GROUP BY w.id ORDER BY w.place")}
    pending = next((r for r in rows.values() if r["status"] == "drawn"), None)
    todo = [p for p in range(len(ps), 0, -1) if p not in rows]
    return {"places": [{"place": i + 1, "tjs": t, "w": rows.get(i + 1)} for i, t in enumerate(ps)],
            "pending": pending, "next_place": todo[0] if todo else None, "left": len(todo),
            "participants": conn.execute("SELECT COUNT(*) FROM raffle_entries").fetchone()[0],
            "with_tickets": conn.execute("SELECT COUNT(DISTINCT user_id) FROM raffle_tickets").fetchone()[0],
            "tickets": conn.execute("SELECT COUNT(*) FROM raffle_tickets").fetchone()[0]}


def draw_next(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    """Следующее место (с последнего к первому): случайный билет среди тех, кто ещё не выиграл."""
    ensure(conn)
    sync_all(conn)
    b = board(conn)
    if b["pending"]:
        raise RaffleError("Сначала подтвердите или перевыберите победителя, которого уже выбрали.")
    if b["next_place"] is None:
        raise RaffleError("Все места разыграны.")
    pool = conn.execute(
        "SELECT t.no, t.user_id FROM raffle_tickets t JOIN raffle_entries e ON e.user_id = t.user_id "
        "WHERE t.user_id NOT IN (SELECT user_id FROM raffle_winners) ORDER BY t.no").fetchall()
    if not pool:
        raise RaffleError("Билетов больше нет: все участники уже выиграли или никто не набрал покупок.")
    t = secrets.choice(pool)
    place = b["next_place"]
    conn.execute("INSERT INTO raffle_winners (place, user_id, ticket, prize_tjs, status, drawn_at) "
                 "VALUES (?, ?, ?, ?, 'drawn', ?)", (place, t["user_id"], t["no"], places(conn)[place - 1], db.now()))
    db.set_setting(conn, "raffle.closed", "1")     # розыгрыш начался — новые билеты не выдаются
    check_tg(conn, config, t["user_id"])            # свежая проверка подписки победителя
    return {"place": place, "ticket": t["no"], "user_id": t["user_id"]}


def redraw(conn: sqlite3.Connection) -> None:
    """Победитель не прошёл проверку (нет подписки) — его билет сгорает, место разыгрывается заново."""
    cur = conn.execute("UPDATE raffle_winners SET status = 'void' WHERE status = 'drawn'")
    if not cur.rowcount:
        raise RaffleError("Нет победителя, ожидающего проверки.")


def confirm(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    """Победитель подтверждён — приз (сомони по курсу) на баланс. Вне транзакции не вызывать дважды: статус защищает."""
    from . import payments
    w = conn.execute("SELECT * FROM raffle_winners WHERE status = 'drawn'").fetchone()
    if w is None:
        raise RaffleError("Нет победителя, ожидающего проверки.")
    rate = payments.settings(conn, config)["tjs_rate"]
    micro = int((Decimal(w["prize_tjs"]) / rate * 10000).quantize(Decimal(1), rounding=ROUND_DOWN))
    cur = conn.execute("UPDATE raffle_winners SET status = 'paid', amount_micro = ? WHERE id = ? AND status = 'drawn'",
                       (micro, w["id"]))
    if cur.rowcount:
        accounts.post_ledger(conn, w["user_id"], micro, f"Розыгрыш: {w['place']} место ({w['prize_tjs']} сомони)")
    return {"place": w["place"], "user_id": w["user_id"], "prize_tjs": w["prize_tjs"], "micro": micro}


def participants(conn: sqlite3.Connection, limit: int = 300) -> list[dict[str, Any]]:
    ensure(conn)
    c = cfg(conn)
    rows = conn.execute(
        "SELECT e.*, u.login, (SELECT COUNT(*) FROM raffle_tickets t WHERE t.user_id = e.user_id) AS tickets "
        "FROM raffle_entries e JOIN users u ON u.id = e.user_id ORDER BY tickets DESC, e.joined_at LIMIT ?",
        (limit,)).fetchall()
    return [{**dict(r), "spent": f"{spent_micro(conn, r['user_id'], c['start'] or db.now()) / 10_000:.2f}"}
            for r in rows]


def mask(name: str) -> str:
    name = (name or "Игрок").strip()
    return name[:2] + "***" if len(name) > 2 else name + "***"


def public_winners(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Подтверждённые победители — для страницы розыгрыша (имя скрыто, виден номер билета)."""
    ensure(conn)
    return [{"place": r["place"], "tjs": r["prize_tjs"], "ticket": r["ticket"], "name": mask(r["name"] or r["login"])}
            for r in conn.execute(
                "SELECT w.place, w.prize_tjs, w.ticket, u.login, (SELECT name FROM shop_users s WHERE s.user_id = "
                "w.user_id LIMIT 1) AS name FROM raffle_winners w JOIN users u ON u.id = w.user_id "
                "WHERE w.status = 'paid' ORDER BY w.place")]
