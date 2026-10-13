"""Конкурс рефералов недели: кто пригласил больше друзей — призы каждое воскресенье в 20:00 (по Душанбе).

Друг засчитывается пригласившему, только если:
- зарегистрировался по его ссылке и ПОДТВЕРДИЛ email (письмо со ссылкой; вход через Google — уже подтверждён);
- почта не одноразовая (temp-mail и т.п.), и такая почта ещё не засчитывалась — с учётом хитростей Gmail:
  a.li@gmail.com, ali+5@gmail.com и ali@gmail.com — один и тот же ящик;
- с этого устройства ещё не засчитывали другого друга (метка браузера dx_vid, а в ту же неделю — и «IP + браузер»);
- это не устройство самого пригласившего (себя пригласить нельзя).

Неделя — с воскресенья 20:00 до следующего воскресенья 20:00. Итоги подводит воркер: топ-3 получают призы
на баланс (в сомони по курсу), победителям и админу — уведомление. При равенстве выше тот, кто набрал раньше.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any

from . import accounts, db

log = logging.getLogger(__name__)

DEFAULT_PRIZES = (50, 30, 20)          # сомони за 1, 2, 3 место
END_WEEKDAY, END_HOUR = 6, 20          # воскресенье, 20:00 по местному времени
_DISPOSABLE: set[str] | None = None


def _ensure(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS ref_signups (user_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL, "
                 "device TEXT, netua TEXT, email_norm TEXT, created_at TEXT NOT NULL, counted_at TEXT, reason TEXT)")
    conn.execute("CREATE INDEX IF NOT EXISTS ref_signups_week ON ref_signups(counted_at, referrer_id)")
    conn.execute("CREATE TABLE IF NOT EXISTS contest_winners (week TEXT NOT NULL, place INTEGER NOT NULL, "
                 "user_id INTEGER NOT NULL, friends INTEGER NOT NULL, prize_tjs INTEGER NOT NULL, "
                 "amount_micro INTEGER NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (week, place))")


# ── Настройки ────────────────────────────────────────────────


def enabled(conn: sqlite3.Connection) -> bool:
    return (db.get_setting(conn, "contest.enabled") or "1") == "1"


def prizes(conn: sqlite3.Connection) -> list[int]:
    raw = db.get_setting(conn, "contest.prizes") or ""
    try:
        got = [max(0, int(x)) for x in raw.split(",") if x.strip()][:3]
    except ValueError:
        got = []
    return got if len(got) == 3 else list(DEFAULT_PRIZES)


def save_settings(conn: sqlite3.Connection, on: bool, raw_prizes: list[str]) -> None:
    try:
        vals = [int(str(x).strip()) for x in raw_prizes]
    except ValueError:
        raise ValueError("Призы — целые числа в сомони.") from None
    if len(vals) != 3 or any(v < 0 or v > 100000 for v in vals):
        raise ValueError("Три приза — от 0 до 100 000 сомони.")
    db.set_setting(conn, "contest.enabled", "1" if on else "0")
    db.set_setting(conn, "contest.prizes", ",".join(map(str, vals)))


# ── Неделя ───────────────────────────────────────────────────


def _local(tz: int) -> timezone:
    return timezone(timedelta(hours=tz))


def week_bounds(tz: int, now: datetime | None = None) -> tuple[datetime, datetime]:
    """(начало, конец) текущей недели конкурса в UTC: конец — ближайшее воскресенье 20:00 по местному."""
    now = (now or datetime.now(timezone.utc)).astimezone(_local(tz))
    end = (now + timedelta(days=(END_WEEKDAY - now.weekday()) % 7)).replace(
        hour=END_HOUR, minute=0, second=0, microsecond=0)
    if end <= now:
        end += timedelta(days=7)
    return (end - timedelta(days=7)).astimezone(timezone.utc), end.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ── Почта и устройство ───────────────────────────────────────


def normalize_email(email: str) -> str:
    """Один ящик — одна запись: у Gmail точки и «+что-угодно» не важны, у остальных — «+что-угодно»."""
    local, _, domain = (email or "").strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def disposable(email: str) -> bool:
    global _DISPOSABLE
    if _DISPOSABLE is None:
        f = Path(__file__).with_name("disposable_domains.txt")
        _DISPOSABLE = {ln.strip().lower() for ln in f.read_text().splitlines()
                       if ln.strip() and not ln.startswith("#")} if f.exists() else set()
    domain = (email or "").rpartition("@")[2].lower()
    parts = domain.split(".")
    return any(".".join(parts[i:]) in _DISPOSABLE for i in range(len(parts) - 1))


def netua(ip: str, ua: str) -> str:
    return hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()[:24]


# ── Регистрация друга и проверка ─────────────────────────────


def on_signup(conn: sqlite3.Connection, user_id: int, device: str, ip: str, ua: str, *, verified: bool) -> None:
    """Новый клиент пришёл по чьей-то ссылке — запомнить устройство; подтверждён (Google) — сразу проверить."""
    _ensure(conn)
    u = conn.execute("SELECT referred_by, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None or not u["referred_by"]:
        return
    conn.execute("INSERT OR IGNORE INTO ref_signups (user_id, referrer_id, device, netua, email_norm, created_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (user_id, u["referred_by"], device or None, netua(ip, ua),
                                               normalize_email(u["email"]), db.now()))
    if verified:
        mark_verified(conn, user_id)


def mark_verified(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("UPDATE users SET email_verified_at = COALESCE(email_verified_at, ?) WHERE id = ?",
                 (db.now(), user_id))
    evaluate(conn, user_id)


def evaluate(conn: sqlite3.Connection, user_id: int) -> bool:
    """Засчитать друга пригласившему (один раз). Нет — записать причину, её видит админ."""
    _ensure(conn)
    s = conn.execute("SELECT * FROM ref_signups WHERE user_id = ?", (user_id,)).fetchone()
    u = conn.execute("SELECT email, email_verified_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if s is None or u is None or s["counted_at"]:
        return bool(s and s["counted_at"])
    if not u["email_verified_at"]:
        return False
    email_norm = normalize_email(u["email"])
    reason = ""
    if u["email"].endswith(("@telegram.user", "@guest.donatix.tj")) or disposable(u["email"]):
        reason = "одноразовая или ненастоящая почта"
    elif conn.execute("SELECT 1 FROM ref_signups WHERE email_norm = ? AND counted_at IS NOT NULL AND user_id != ?",
                      (email_norm, user_id)).fetchone():
        reason = "эта почта уже засчитывалась"
    elif s["device"] and conn.execute("SELECT 1 FROM ref_signups WHERE device = ? AND counted_at IS NOT NULL "
                                      "AND user_id != ?", (s["device"], user_id)).fetchone():
        reason = "с этого устройства уже засчитан другой друг"
    elif _self_device(conn, s):
        reason = "устройство самого пригласившего"
    else:
        start_iso = _iso(datetime.now(timezone.utc) - timedelta(days=7))
        if conn.execute("SELECT 1 FROM ref_signups WHERE netua = ? AND counted_at >= ? AND user_id != ?",
                        (s["netua"], start_iso, user_id)).fetchone():
            reason = "с этого устройства (IP и браузер) уже засчитан другой друг на этой неделе"
    if reason:
        conn.execute("UPDATE ref_signups SET reason = ?, email_norm = ? WHERE user_id = ?",
                     (reason, email_norm, user_id))
        return False
    conn.execute("UPDATE ref_signups SET counted_at = ?, reason = NULL, email_norm = ? WHERE user_id = ?",
                 (db.now(), email_norm, user_id))
    return True


def _self_device(conn: sqlite3.Connection, s: sqlite3.Row) -> bool:
    ref = s["referrer_id"]
    if s["device"] and conn.execute("SELECT 1 FROM visits WHERE user_id = ? AND visitor = ? LIMIT 1",
                                    (ref, s["device"])).fetchone():
        return True
    for row in conn.execute("SELECT ip, user_agent FROM logins WHERE user_id = ? ORDER BY id DESC LIMIT 50", (ref,)):
        if netua(row["ip"] or "", row["user_agent"] or "") == s["netua"]:
            return True
    return False


def disqualify(conn: sqlite3.Connection, user_id: int, why: str = "снят админом") -> None:
    """Админ снимает приглашённого (накрутка) — он больше не считается."""
    _ensure(conn)
    conn.execute("UPDATE ref_signups SET counted_at = NULL, reason = ? WHERE user_id = ?", (why[:200], user_id))


# ── Таблица и итоги ──────────────────────────────────────────


def leaderboard(conn: sqlite3.Connection, start: datetime, end: datetime, limit: int = 10) -> list[dict[str, Any]]:
    _ensure(conn)
    rows = conn.execute(
        "SELECT s.referrer_id, u.login, COUNT(*) AS n, MAX(s.counted_at) AS last FROM ref_signups s "
        "JOIN users u ON u.id = s.referrer_id WHERE s.counted_at >= ? AND s.counted_at < ? "
        "AND u.status != 'blocked' GROUP BY s.referrer_id ORDER BY n DESC, last ASC LIMIT ?",
        (_iso(start), _iso(end), limit)).fetchall()
    return [{"place": i + 1, "user_id": r["referrer_id"], "login": r["login"], "name": mask(r["login"]),
             "friends": r["n"]} for i, r in enumerate(rows)]


def mask(login: str) -> str:
    login = login or "?"
    return login[:3] + "***" if len(login) > 3 else login[:1] + "***"


def view(conn: sqlite3.Connection, tz: int, user_id: int) -> dict[str, Any]:
    """Всё для страницы «Конкурс недели»."""
    start, end = week_bounds(tz)
    top = leaderboard(conn, start, end, 10)
    full = leaderboard(conn, start, end, 1000)
    mine = next((r for r in full if r["user_id"] == user_id), None)
    pending = conn.execute("SELECT COUNT(*) FROM ref_signups WHERE referrer_id = ? AND counted_at IS NULL "
                           "AND reason IS NULL", (user_id,)).fetchone()[0]
    winners = conn.execute(
        "SELECT w.week, w.place, w.friends, w.prize_tjs, u.login FROM contest_winners w JOIN users u ON u.id = w.user_id "
        "ORDER BY w.week DESC, w.place LIMIT 9").fetchall()
    return {"on": enabled(conn), "prizes": prizes(conn), "end": end, "end_iso": _iso(end),
            "end_local": end.astimezone(_local(tz)), "top": top,
            "mine": mine, "my_friends": mine["friends"] if mine else 0,
            "to_top3": _to_top3(full, mine),
            "pending": pending,
            "winners": [{**dict(w), "name": mask(w["login"])} for w in winners]}


def _to_top3(full: list[dict[str, Any]], mine: dict[str, Any] | None) -> int:
    """Сколько друзей не хватает до 3 места (0 — уже в тройке)."""
    if mine and mine["place"] <= 3:
        return 0
    if len(full) < 3:
        return 1
    return full[2]["friends"] - (mine["friends"] if mine else 0) + 1


def settle(conn: sqlite3.Connection, config: Any, now: datetime | None = None) -> int:
    """Подвести итоги прошедшей недели (один раз): топ-3 — призы на баланс. Возвращает, сколько выплачено."""
    _ensure(conn)
    if not enabled(conn):
        return 0
    start, _ = week_bounds(config.tz_offset, now)
    prev_start, prev_end = start - timedelta(days=7), start
    week = prev_end.astimezone(_local(config.tz_offset)).strftime("%Y-%m-%d")
    if db.get_setting(conn, f"contest.done.{week}"):
        return 0
    first_signup = conn.execute("SELECT MIN(created_at) FROM ref_signups").fetchone()[0]
    if first_signup is None or first_signup >= _iso(prev_end):
        db.set_setting(conn, f"contest.done.{week}", "1")   # конкурса в ту неделю ещё не было
        return 0
    from . import payments
    from .notify import notify
    rate = payments.settings(conn, config)["tjs_rate"]
    top = leaderboard(conn, prev_start, prev_end, 3)
    paid = 0
    medals = ("🥇", "🥈", "🥉")
    with db.tx(conn):
        if db.get_setting(conn, f"contest.done.{week}"):
            return 0
        for r, tjs in zip(top, prizes(conn)):
            if tjs <= 0:
                continue
            micro = int((Decimal(tjs) / rate * 10000).quantize(Decimal(1), rounding=ROUND_DOWN))
            conn.execute("INSERT INTO contest_winners (week, place, user_id, friends, prize_tjs, amount_micro, "
                         "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (week, r["place"], r["user_id"], r["friends"], tjs, micro, db.now()))
            accounts.post_ledger(conn, r["user_id"], micro,
                                 f"Конкурс рефералов {week}: {r['place']} место ({tjs} сомони)")
            paid += 1
        db.set_setting(conn, f"contest.done.{week}", "1")
    for r, tjs in zip(top, prizes(conn)):
        if tjs > 0:
            notify(conn, config, r["user_id"], f"{medals[r['place'] - 1]} Вы заняли {r['place']} место в конкурсе "
                   f"недели ({r['friends']} друзей)! Приз {tjs} сомони уже на балансе.", "/panel/referrals")
    if top:
        from .worker import notify_admin
        lines = "\n".join(f"{medals[r['place'] - 1]} {r['login']} — {r['friends']} друзей, {t} сомони"
                          for r, t in zip(top, prizes(conn)))
        notify_admin(config, f"🏆 Итоги конкурса рефералов ({week}):\n{lines}\n\n"
                             "Подробно и снять за накрутку: админка → Конкурс.")
    return paid


def participants(conn: sqlite3.Connection, tz: int) -> list[dict[str, Any]]:
    """Для админа: приглашённые этой недели с причинами, почему не засчитаны."""
    _ensure(conn)
    start, _ = week_bounds(tz)
    rows = conn.execute(
        "SELECT s.*, u.login, u.email, r.login AS ref_login FROM ref_signups s JOIN users u ON u.id = s.user_id "
        "JOIN users r ON r.id = s.referrer_id WHERE s.created_at >= ? OR s.counted_at >= ? ORDER BY s.created_at DESC "
        "LIMIT 300", (_iso(start), _iso(start))).fetchall()
    return [dict(r) for r in rows]
