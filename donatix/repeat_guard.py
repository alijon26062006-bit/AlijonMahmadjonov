"""ИИ-модератор повторных чеков — правило, которое вынес суд 10 агентов и судьи.

Клиент прикладывает чек, который уже ЗАЧИСЛЕН в прошлой заявке (payments.ReceiptUsed):

1. Автоматический страйк — только по точному доказательству: тот же файл (SHA-256) или код операции от банка.
   Похожая картинка и номер+сумма+минута, прочитанные ИИ, — отказ в заявке и задача модератору; страйк он
   ставит вручную, если подтвердит повтор.
2. Повторы в одной заявке или в течение 10 минут — один случай.
3. Лестница: 1-й — отказ с номером прошлой заявки; 2-й — предупреждение; 3-й за 30 дней — блок 5 дней;
   следующий — 7 дней; следующий — вечная блокировка, но только после решения живого модератора
   (до решения действует блок на 7 дней).
4. 90 дней без нарушений — уровень на ступень ниже. Счётчик отдельный от fraud_count (поддельные чеки).
5. Во время блока: API отвечает 403 с датой разблокировки, новые заказы и пополнения не принимаются;
   оплаченные заказы выполняются, баланс не трогаем. Боты партнёра замораживаются и сохраняют место;
   удаляются только при вечной блокировке, через 24 часа после уведомления.
6. Покупатель партнёра (external_user_id в API) отвечает сам; аккаунт партнёра — только если повторов больше
   5% его заявок за 7 дней (минимум 20): сначала предупреждение и 48 часов.
7. Апелляция — 48 часов, решает живой модератор. Всё пишется в журнал, админ отменяет одной кнопкой.
8. Правило действует с 24.11.2026 (настройка repeat.start_ts, её можно поменять в админке). Раньше — только отказ.

Субъект нарушения: "u:<id>" — аккаунт Donatix, "x:<id>:<external_user_id>" — покупатель партнёра.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db

log = logging.getLogger(__name__)

DAY = 86400
SAME_CASE = 10 * 60          # повторы в течение 10 минут — один случай
WINDOW = 30 * DAY            # блок — при 3 страйках за 30 дней
DECAY = 90 * DAY             # 90 дней без нарушений — ступень вниз
APPEAL = 48 * 3600           # апелляция — 48 часов
NOTICE = 24 * 3600           # перед удалением бота — уведомление за 24 часа
PARTNER_WINDOW = 7 * DAY
PARTNER_SHARE = 0.05
PARTNER_MIN = 20
PARTNER_FIX = 48 * 3600
START_DEFAULT = 1795460400   # 24.11.2026 00:00 (Душанбе) — с этого дня правило действует, так решил владелец
STRONG = ("sha256", "bank_code")   # точные доказательства — страйк сам
TZ = timezone(timedelta(hours=5))   # Душанбе

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipt_strikes (
    id          INTEGER PRIMARY KEY,
    subject     TEXT NOT NULL,
    user_id     INTEGER NOT NULL,
    payment_id  INTEGER,
    prev_id     INTEGER,
    evidence    TEXT NOT NULL,              -- sha256 | bank_code | manual | partner_ratio | transfer
    status      TEXT NOT NULL DEFAULT 'active',   -- active | revoked | decayed
    ts          INTEGER NOT NULL,
    note        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS receipt_strikes_subject ON receipt_strikes(subject, status, ts);
CREATE TABLE IF NOT EXISTS receipt_reviews (
    id          INTEGER PRIMARY KEY,
    subject     TEXT NOT NULL,
    user_id     INTEGER NOT NULL,
    payment_id  INTEGER,
    prev_id     INTEGER,
    evidence    TEXT NOT NULL,              -- picture | ai_transfer
    status      TEXT NOT NULL DEFAULT 'open',     -- open | confirmed | dismissed
    ts          INTEGER NOT NULL,
    decided_by  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS account_holds (
    id          INTEGER PRIMARY KEY,
    subject     TEXT NOT NULL,
    user_id     INTEGER NOT NULL,
    level       INTEGER NOT NULL,
    kind        TEXT NOT NULL,              -- temp | perm_pending | perm
    ts          INTEGER NOT NULL,
    until_ts    INTEGER,                    -- конец блока; NULL — навсегда
    status      TEXT NOT NULL DEFAULT 'active',   -- active | lifted | expired
    strike_id   INTEGER,
    bots        TEXT NOT NULL DEFAULT '[]', -- какие боты заморожены (id)
    appeal      TEXT NOT NULL DEFAULT '',
    appeal_ts   INTEGER,
    appeal_state TEXT NOT NULL DEFAULT '',  -- '' | open | accepted | rejected
    notice_ts   INTEGER,                    -- вечная: когда партнёра предупредили об удалении ботов
    decided_by  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS account_holds_subject ON account_holds(subject, status);
CREATE TABLE IF NOT EXISTS receipt_guard_log (
    id          INTEGER PRIMARY KEY,
    subject     TEXT NOT NULL,
    user_id     INTEGER NOT NULL,
    action      TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '',
    by_who      TEXT NOT NULL DEFAULT 'ИИ-модератор',
    ts          INTEGER NOT NULL
);
"""


class HoldError(Exception):
    """Аккаунт (или покупатель партнёра) заблокирован за повторные чеки — текст для человека."""

    def __init__(self, text: str, until_ts: int | None):
        super().__init__(text)
        self.until_ts = until_ts


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    saved = db.get_setting(conn, "repeat.start_ts")
    if not saved or (saved.isdigit() and int(saved) > START_DEFAULT and not db.get_setting(conn, "repeat.start_by_admin")):
        db.set_setting(conn, "repeat.start_ts", str(START_DEFAULT))   # с 24.11.2026; админ может поменять в админке


def _now() -> int:
    return int(time.time())


def when(ts: int | None) -> str:
    if not ts:
        return "навсегда"
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y %H:%M")


def start_ts(conn: sqlite3.Connection) -> int:
    try:
        return int(db.get_setting(conn, "repeat.start_ts") or 0)
    except ValueError:
        return 0


def subject_for(user_id: int, ext: str | None = None) -> str:
    ext = (ext or "").strip()
    return f"x:{user_id}:{ext}" if ext else f"u:{user_id}"


def _log(conn, subject: str, user_id: int, action: str, details: str = "", by: str = "ИИ-модератор") -> None:
    conn.execute("INSERT INTO receipt_guard_log (subject, user_id, action, details, by_who, ts) VALUES (?,?,?,?,?,?)",
                 (subject, user_id, action, details[:500], by[:80], _now()))


def _admins(config, text: str) -> None:
    from .worker import notify_admin
    threading.Thread(target=notify_admin, args=(config, text), daemon=True).start()


# ── Уровень ─────────────────────────────────────────────────────

def _strikes(conn, subject: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM receipt_strikes WHERE subject = ? AND status = 'active' ORDER BY ts, id",
                        (subject,)).fetchall()


def _decay(conn, subject: str, now: int) -> None:
    """90 дней без нарушений — ступень вниз: самый старый страйк гасится (за каждые полные 90 дней)."""
    rows = _strikes(conn, subject)
    if not rows:
        return
    steps = (now - rows[-1]["ts"]) // DECAY
    for r in rows[: int(steps)]:
        conn.execute("UPDATE receipt_strikes SET status = 'decayed' WHERE id = ?", (r["id"],))


def level(conn, subject: str, now: int | None = None) -> int:
    now = now or _now()
    rows = _strikes(conn, subject)
    if not rows:
        return 0
    return max(0, len(rows) - int((now - rows[-1]["ts"]) // DECAY))


# ── Блокировки ──────────────────────────────────────────────────

def active_hold(conn, subject: str, now: int | None = None) -> sqlite3.Row | None:
    now = now or _now()
    return conn.execute("SELECT * FROM account_holds WHERE subject = ? AND status = 'active' "
                        "AND (until_ts IS NULL OR until_ts > ?) ORDER BY id DESC LIMIT 1", (subject, now)).fetchone()


def hold_text(h: sqlite3.Row) -> str:
    if h["kind"] == "perm":
        return ("⛔ Аккаунт заблокирован навсегда: несколько раз присылали чек, который уже был зачислен. "
                "/ Аккаунт барои ҳамеша баста шуд.")
    tail = " Решение о вечной блокировке принимает модератор." if h["kind"] == "perm_pending" else ""
    return (f"⛔ Аккаунт заблокирован до {when(h['until_ts'])} (Душанбе): повторно присылали чек, который уже "
            f"зачислен. Новые пополнения и заказы недоступны, оплаченные заказы выполняются, баланс сохранён. "
            f"Обжаловать можно в течение 48 часов в кабинете.{tail} "
            f"/ Аккаунт то {when(h['until_ts'])} баста аст: чеки аллакай қабулшударо такроран фиристодед.")


def check(conn, user_id: int, ext: str | None = None) -> None:
    """Перед новым заказом, пополнением, запросом API: есть блок — HoldError."""
    for subject in ([subject_for(user_id, ext)] if ext else []) + [subject_for(user_id)]:
        h = active_hold(conn, subject)
        if h is not None:
            raise HoldError(hold_text(h), h["until_ts"])


def _freeze_bots(conn, user_id: int) -> list[int]:
    ids = [r[0] for r in conn.execute("SELECT id FROM bots WHERE user_id = ? AND enabled = 1", (user_id,))]
    for bid in ids:   # место остаётся за партнёром: бот не удаляется, только останавливается
        conn.execute("UPDATE bots SET enabled = 0, disabled_reason = 'hold', updated_at = ? WHERE id = ?",
                     (db.now(), bid))
    return ids


def _unfreeze_bots(conn, h: sqlite3.Row) -> None:
    for bid in json.loads(h["bots"] or "[]"):
        conn.execute("UPDATE bots SET enabled = 1, disabled_reason = NULL, updated_at = ? "
                     "WHERE id = ? AND disabled_reason = 'hold'", (db.now(), bid))


def _tell_partner(conn, config, user_id: int, text: str) -> None:
    from . import bot_watch
    for b in conn.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,)).fetchall():
        try:
            bot_watch._tell(conn, config, b, text)
        except Exception:  # noqa: BLE001 — уведомление не должно ломать блокировку
            log.exception("уведомление партнёру")


def _place_hold(conn, config, subject: str, user_id: int, lvl: int, strike_id: int, now: int) -> sqlite3.Row:
    days, kind = (5, "temp") if lvl == 3 else (7, "temp") if lvl == 4 else (7, "perm_pending")
    old = active_hold(conn, subject, now)
    if old is not None:   # уже под блоком — продлеваем новой ступенью
        conn.execute("UPDATE account_holds SET status = 'lifted', decided_by = 'новая ступень' WHERE id = ?", (old["id"],))
    bots = _freeze_bots(conn, user_id) if subject.startswith("u:") else []
    if old is not None:
        bots = sorted(set(bots) | set(json.loads(old["bots"] or "[]")))
    cur = conn.execute("INSERT INTO account_holds (subject, user_id, level, kind, ts, until_ts, strike_id, bots) "
                       "VALUES (?,?,?,?,?,?,?,?)", (subject, user_id, lvl, kind, now, now + days * DAY, strike_id,
                                                    json.dumps(bots)))
    h = conn.execute("SELECT * FROM account_holds WHERE id = ?", (cur.lastrowid,)).fetchone()
    _log(conn, subject, user_id, "hold", f"ступень {lvl}: блок до {when(h['until_ts'])}"
         + (" — ждёт решения модератора о вечной блокировке" if kind == "perm_pending" else "")
         + (f"; заморожены боты {bots}" if bots else ""))
    who = _who(conn, user_id, subject)
    _admins(config, f"⛔ Повторные чеки: {who} заблокирован до {when(h['until_ts'])} (ступень {lvl})."
            + ("\n⚖️ Нужно ваше решение о вечной блокировке: /admin/repeat-guard" if kind == "perm_pending" else ""))
    if bots:
        _tell_partner(conn, config, user_id,
                      f"⛔ Аккаунт Donatix заблокирован до {when(h['until_ts'])} за повторные чеки. Бот остановлен "
                      "и сохраняет место — включится сам после разблокировки. Обжаловать: кабинет Donatix → Апелляция.")
    return h


def _who(conn, user_id: int, subject: str) -> str:
    row = conn.execute("SELECT login FROM users WHERE id = ?", (user_id,)).fetchone()
    name = row["login"] if row else f"#{user_id}"
    return f"покупатель {subject.split(':', 2)[2]} партнёра {name}" if subject.startswith("x:") else name


# ── Главное: чек уже был зачислен ────────────────────────────────

def _ack_key(subject: str) -> str:
    return f"repeat.ack.{subject}"


def _strike(conn, config, subject: str, user_id: int, payment_id: int | None, prev_id: int | None,
            evidence: str, now: int, by: str = "ИИ-модератор", note: str = "") -> dict[str, Any]:
    _decay(conn, subject, now)
    last = conn.execute("SELECT * FROM receipt_strikes WHERE subject = ? AND status = 'active' ORDER BY ts DESC LIMIT 1",
                        (subject,)).fetchone()
    if last is not None and evidence != "manual" and (now - last["ts"] < SAME_CASE or
                                                     (payment_id and last["payment_id"] == payment_id)):
        _log(conn, subject, user_id, "same_case", f"заявка #{payment_id}: тот же случай, что и страйк #{last['id']}")
        return {"step": level(conn, subject, now), "new": False}
    cur = conn.execute("INSERT INTO receipt_strikes (subject, user_id, payment_id, prev_id, evidence, ts, note) "
                       "VALUES (?,?,?,?,?,?,?)", (subject, user_id, payment_id, prev_id, evidence, now, note[:200]))
    sid = cur.lastrowid
    lvl = level(conn, subject, now)
    recent = conn.execute("SELECT COUNT(*) FROM receipt_strikes WHERE subject = ? AND status = 'active' AND ts > ?",
                          (subject, now - WINDOW)).fetchone()[0]
    _log(conn, subject, user_id, "strike", f"страйк #{sid}: заявка #{payment_id}, чек уже зачислен в #{prev_id}, "
         f"доказательство {evidence}; уровень {lvl}, за 30 дней {recent}", by)
    out: dict[str, Any] = {"step": lvl, "new": True, "strike_id": sid}
    if lvl >= 3 and recent >= 3:
        out["hold"] = _place_hold(conn, config, subject, user_id, lvl, sid, now)
    elif lvl >= 2:
        db.set_setting(conn, _ack_key(subject), "need")
        out["warn"] = True
    if subject.startswith("x:"):
        _partner_share(conn, config, user_id, now)
    return out


def message(out: dict[str, Any], prev_id: int | None, prev_date: str = "") -> str:
    """Что клиент видит вместо простого «чек уже принят» — RU / TJ."""
    base = (f"Этот чек уже зачислен{(' ' + prev_date) if prev_date else ''} в заявке #{prev_id}. Приложите новый чек "
            f"перевода. / Ин чек аллакай дар дархости #{prev_id} қабул шудааст — чеки навро замима кунед.")
    if out.get("hold") is not None:
        return hold_text(out["hold"])
    if out.get("warn"):
        return (base + "\n⚠️ Предупреждение: это уже повтор. Ещё один повтор уже зачисленного чека — блокировка "
                "аккаунта на 5 дней. Подтвердите предупреждение в кабинете. / Огоҳӣ: боз як такрор — аккаунт "
                "5 рӯз баста мешавад.")
    return base


def on_used(conn, config, user_id: int, payment_id: int, prev_id: int, evidence: str) -> str:
    """Вызывается, когда чек отклонён как уже зачисленный. Возвращает текст для клиента.
    evidence: sha256 | bank_code (точные) · picture | ai_transfer (решает модератор)."""
    now = _now()
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    ext = (p["ext_user"] if p is not None and "ext_user" in p.keys() else None) or None
    subject = subject_for(user_id, ext)
    prev = conn.execute("SELECT * FROM payments WHERE id = ?", (prev_id,)).fetchone()
    prev_date = ""
    if prev is not None:   # когда зачислен (resolved_at), иначе — когда создан
        keys = prev.keys()
        stamp = (prev["resolved_at"] if "resolved_at" in keys and prev["resolved_at"] else prev["created_at"]) or ""
        prev_date = stamp[:10]
    base_out: dict[str, Any] = {"step": 0}
    if now < start_ts(conn):   # правило ещё не вступило в силу — только отказ, без страйков
        _log(conn, subject, user_id, "before_start", f"заявка #{payment_id}: повтор чека #{prev_id} до вступления правила")
        return message(base_out, prev_id, prev_date)
    if evidence not in STRONG:   # ИИ мог ошибиться — решит модератор
        open_ = conn.execute("SELECT 1 FROM receipt_reviews WHERE payment_id = ? AND status = 'open'",
                             (payment_id,)).fetchone()
        if not open_:
            conn.execute("INSERT INTO receipt_reviews (subject, user_id, payment_id, prev_id, evidence, ts) "
                         "VALUES (?,?,?,?,?,?)", (subject, user_id, payment_id, prev_id, evidence, now))
            _log(conn, subject, user_id, "review", f"заявка #{payment_id}: похоже на чек #{prev_id} ({evidence}) — "
                 "на проверку модератору, страйка нет")
        return message(base_out, prev_id, prev_date)
    out = _strike(conn, config, subject, user_id, payment_id, prev_id, evidence, now)
    return message(out, prev_id, prev_date)


# ── Партнёр: доля повторов среди заявок его покупателей ─────────

def _partner_share(conn, config, user_id: int, now: int) -> None:
    since = datetime.fromtimestamp(now - PARTNER_WINDOW, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND ext_user IS NOT NULL AND ext_user != '' "
                         "AND created_at >= ?", (user_id, since)).fetchone()[0]
    bad = conn.execute("SELECT COUNT(*) FROM receipt_strikes WHERE user_id = ? AND subject LIKE 'x:%' AND ts > ? "
                       "AND status != 'revoked'", (user_id, now - PARTNER_WINDOW)).fetchone()[0]
    if total < PARTNER_MIN or bad / total <= PARTNER_SHARE:
        return
    key = f"repeat.pwarn.{user_id}"
    warned = int(db.get_setting(conn, key) or 0)
    if warned and now - warned < PARTNER_WINDOW:
        return
    db.set_setting(conn, key, str(now))
    _log(conn, subject_for(user_id), user_id, "partner_warn",
         f"повторов {bad} из {total} заявок покупателей за 7 дней — предупреждение, 48 часов на исправление")
    _tell_partner(conn, config, user_id, f"⚠️ Donatix: за 7 дней {bad} из {total} заявок ваших покупателей — повторные "
                                         "чеки. Исправьте в течение 48 часов (проверяйте чеки покупателей), иначе "
                                         "правило о повторных чеках применится к вашему аккаунту.")
    _admins(config, f"⚠️ Партнёр {_who(conn, user_id, 'u:')}: {bad} из {total} заявок покупателей — повторы. "
                    "Предупреждён, 48 часов.")


def _partner_followup(conn, config, now: int) -> None:
    for row in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'repeat.pwarn.%'").fetchall():
        try:
            uid, warned = int(row["key"].rsplit(".", 1)[1]), int(row["value"])
        except ValueError:
            continue
        if not (PARTNER_FIX <= now - warned < PARTNER_WINDOW):
            continue
        done = f"repeat.pdone.{uid}.{warned}"
        if db.get_setting(conn, done):
            continue
        db.set_setting(conn, done, "1")
        since = datetime.fromtimestamp(warned, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        total = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND ext_user IS NOT NULL AND ext_user != '' "
                             "AND created_at >= ?", (uid, since)).fetchone()[0]
        bad = conn.execute("SELECT COUNT(*) FROM receipt_strikes WHERE user_id = ? AND subject LIKE 'x:%' AND ts > ? "
                           "AND status != 'revoked'", (uid, warned)).fetchone()[0]
        if total and bad / total > PARTNER_SHARE:   # не исправил за 48 часов — страйк аккаунту партнёра
            _strike(conn, config, subject_for(uid), uid, None, None, "partner_ratio", now,
                    note=f"после предупреждения повторов {bad} из {total}")


# ── Фон: истёкшие блоки, удаление ботов после вечной блокировки ──

def tick(conn, config, now: int | None = None) -> None:
    now = now or _now()
    for h in conn.execute("SELECT * FROM account_holds WHERE status = 'active' AND until_ts IS NOT NULL "
                          "AND until_ts <= ? AND kind = 'temp'", (now,)).fetchall():
        conn.execute("UPDATE account_holds SET status = 'expired' WHERE id = ?", (h["id"],))
        _unfreeze_bots(conn, h)
        _log(conn, h["subject"], h["user_id"], "expired", "срок блокировки закончился — API и боты снова работают")
        if json.loads(h["bots"] or "[]"):
            _tell_partner(conn, config, h["user_id"], "✅ Блокировка Donatix закончилась — бот снова работает.")
    # вечная, ждёт модератора: срок временного блока вышел, а решения нет — продлеваем, пока не решат
    for h in conn.execute("SELECT * FROM account_holds WHERE status = 'active' AND kind = 'perm_pending' "
                          "AND until_ts <= ?", (now,)).fetchall():
        conn.execute("UPDATE account_holds SET until_ts = ? WHERE id = ?", (now + DAY, h["id"]))
    for h in conn.execute("SELECT * FROM account_holds WHERE status = 'active' AND kind = 'perm' "
                          "AND notice_ts IS NOT NULL AND notice_ts <= ?", (now - NOTICE,)).fetchall():
        from . import bots
        for b in conn.execute("SELECT id FROM bots WHERE user_id = ?", (h["user_id"],)).fetchall():
            bots.delete(conn, b["id"], config)   # место освобождается для других партнёров
        conn.execute("UPDATE account_holds SET notice_ts = NULL WHERE id = ?", (h["id"],))
        _log(conn, h["subject"], h["user_id"], "bots_deleted", "вечная блокировка: боты удалены, место освобождено")
    _partner_followup(conn, config, now)


# ── Кабинет клиента ─────────────────────────────────────────────

def banner(conn, user_id: int) -> dict[str, Any] | None:
    """Для кабинета: блок, предупреждение или скорое вступление правила в силу."""
    subject = subject_for(user_id)
    h = active_hold(conn, subject)
    if h is not None:
        can_appeal = _now() - h["ts"] < APPEAL and h["appeal_state"] == ""
        return {"kind": "hold", "text": hold_text(h), "hold_id": h["id"], "can_appeal": can_appeal,
                "appeal_state": h["appeal_state"]}
    if db.get_setting(conn, _ack_key(subject)) == "need":
        return {"kind": "warn", "text": "⚠️ Вы прислали чек, который уже был зачислен. Ещё один повтор — блокировка "
                                        "аккаунта на 5 дней. / Боз як такрор — аккаунт 5 рӯз баста мешавад."}
    start = start_ts(conn)
    if _now() < start:
        return {"kind": "soon", "text": f"С {when(start)[:10]} действует правило: повторная отправка уже зачисленного "
                                        "чека — предупреждение, затем блокировка на 5 и 7 дней, затем навсегда. "
                                        "Подробнее — в пользовательском соглашении, раздел 4."}
    return None


def ack(conn, user_id: int) -> None:
    subject = subject_for(user_id)
    if db.get_setting(conn, _ack_key(subject)) == "need":
        db.set_setting(conn, _ack_key(subject), "ok")
        _log(conn, subject, user_id, "ack", "клиент подтвердил предупреждение", "клиент")


def appeal(conn, config, user_id: int, text: str) -> None:
    h = active_hold(conn, subject_for(user_id))
    text = (text or "").strip()
    if h is None:
        raise ValueError("Блокировки нет — обжаловать нечего.")
    if h["appeal_state"]:
        raise ValueError("Апелляция уже подана — модератор ответит в течение 24 часов.")
    if _now() - h["ts"] >= APPEAL:
        raise ValueError("Срок апелляции (48 часов) прошёл.")
    if len(text) < 10:
        raise ValueError("Опишите, что произошло (хотя бы пару предложений).")
    conn.execute("UPDATE account_holds SET appeal = ?, appeal_ts = ?, appeal_state = 'open' WHERE id = ?",
                 (text[:2000], _now(), h["id"]))
    _log(conn, h["subject"], user_id, "appeal", text[:300], "клиент")
    _admins(config, f"📨 Апелляция по блокировке за повторные чеки: {_who(conn, user_id, h['subject'])}. "
                    "Ответьте в течение 24 часов: /admin/repeat-guard")


# ── Решения модератора ──────────────────────────────────────────

def lift(conn, config, hold_id: int, by: str, revoke: bool = True) -> None:
    """Снять блок (апелляция принята или ошибка): боты включаются, страйк снимается."""
    h = conn.execute("SELECT * FROM account_holds WHERE id = ?", (hold_id,)).fetchone()
    if h is None:
        return
    conn.execute("UPDATE account_holds SET status = 'lifted', decided_by = ?, appeal_state = CASE WHEN appeal_state = "
                 "'open' THEN 'accepted' ELSE appeal_state END WHERE id = ?", (by[:80], hold_id))
    _unfreeze_bots(conn, h)
    if h["kind"] == "perm":
        conn.execute("UPDATE users SET status = 'active' WHERE id = ? AND status = 'blocked'", (h["user_id"],))
    if revoke and h["strike_id"]:
        conn.execute("UPDATE receipt_strikes SET status = 'revoked' WHERE id = ?", (h["strike_id"],))
    _log(conn, h["subject"], h["user_id"], "lifted", "блок снят" + (", страйк отменён" if revoke else ""), by)


def reject_appeal(conn, hold_id: int, by: str) -> None:
    h = conn.execute("SELECT * FROM account_holds WHERE id = ?", (hold_id,)).fetchone()
    if h is None or h["appeal_state"] != "open":
        return
    conn.execute("UPDATE account_holds SET appeal_state = 'rejected', decided_by = ? WHERE id = ?", (by[:80], hold_id))
    _log(conn, h["subject"], h["user_id"], "appeal_rejected", "апелляция отклонена", by)


def confirm_perm(conn, config, hold_id: int, by: str) -> str:
    """Вечная блокировка — только человек, и только после срока апелляции или её отказа."""
    h = conn.execute("SELECT * FROM account_holds WHERE id = ?", (hold_id,)).fetchone()
    if h is None or h["kind"] != "perm_pending" or h["status"] != "active":
        return "Эта блокировка не ждёт решения."
    if h["appeal_state"] == "open":
        return "Сначала ответьте на апелляцию."
    if h["appeal_state"] != "rejected" and _now() - h["ts"] < APPEAL:
        return f"Срок апелляции ещё идёт — до {when(h['ts'] + APPEAL)}."
    conn.execute("UPDATE account_holds SET kind = 'perm', until_ts = NULL, notice_ts = ?, decided_by = ? WHERE id = ?",
                 (_now(), by[:80], hold_id))
    if h["subject"].startswith("u:"):
        conn.execute("UPDATE users SET status = 'blocked' WHERE id = ?", (h["user_id"],))
        _tell_partner(conn, config, h["user_id"], "⛔ Аккаунт Donatix заблокирован навсегда за повторные чеки. "
                                                  "Через 24 часа бот будет удалён, и его место освободится.")
    _log(conn, h["subject"], h["user_id"], "perm", "вечная блокировка подтверждена; боты удалятся через 24 часа", by)
    return ""


def decline_perm(conn, hold_id: int, by: str) -> None:
    """Модератор не подтвердил вечную: остаётся блок на 7 дней от его начала."""
    h = conn.execute("SELECT * FROM account_holds WHERE id = ?", (hold_id,)).fetchone()
    if h is None or h["kind"] != "perm_pending":
        return
    conn.execute("UPDATE account_holds SET kind = 'temp', until_ts = ?, decided_by = ? WHERE id = ?",
                 (max(h["ts"] + 7 * DAY, _now() + 60), by[:80], hold_id))
    _log(conn, h["subject"], h["user_id"], "perm_declined", "вечная не подтверждена — блок на 7 дней", by)


def review(conn, config, review_id: int, confirm: bool, by: str) -> None:
    r = conn.execute("SELECT * FROM receipt_reviews WHERE id = ? AND status = 'open'", (review_id,)).fetchone()
    if r is None:
        return
    conn.execute("UPDATE receipt_reviews SET status = ?, decided_by = ? WHERE id = ?",
                 ("confirmed" if confirm else "dismissed", by[:80], review_id))
    if confirm:
        _strike(conn, config, r["subject"], r["user_id"], r["payment_id"], r["prev_id"], "manual", _now(), by,
                f"модератор подтвердил повтор ({r['evidence']})")
    else:
        _log(conn, r["subject"], r["user_id"], "review_dismissed", f"заявка #{r['payment_id']}: не повтор", by)


def revoke(conn, strike_id: int, by: str) -> None:
    r = conn.execute("SELECT * FROM receipt_strikes WHERE id = ?", (strike_id,)).fetchone()
    if r is None:
        return
    conn.execute("UPDATE receipt_strikes SET status = 'revoked' WHERE id = ?", (strike_id,))
    _log(conn, r["subject"], r["user_id"], "revoked", f"страйк #{strike_id} отменён", by)


def transfer(conn, from_user: int, to_user: int, by: str) -> int:
    """Новый аккаунт той же карты/устройства — модератор переносит уровень (не автоматически)."""
    rows = _strikes(conn, subject_for(from_user))
    for r in rows:
        conn.execute("INSERT INTO receipt_strikes (subject, user_id, payment_id, prev_id, evidence, ts, note) "
                     "VALUES (?,?,?,?, 'manual', ?, ?)", (subject_for(to_user), to_user, r["payment_id"], r["prev_id"],
                                                         r["ts"], f"перенесён с аккаунта #{from_user}"))
    _log(conn, subject_for(to_user), to_user, "transfer", f"перенесено {len(rows)} страйков с #{from_user}", by)
    return len(rows)


def overview(conn) -> dict[str, Any]:
    now = _now()
    q = lambda sql, *a: conn.execute(sql, a).fetchall()  # noqa: E731
    return {
        "start": start_ts(conn), "now": now,
        "holds": q("SELECT h.*, u.login FROM account_holds h LEFT JOIN users u ON u.id = h.user_id "
                   "WHERE h.status = 'active' AND (h.until_ts IS NULL OR h.until_ts > ?) ORDER BY h.id DESC", now),
        "reviews": q("SELECT r.*, u.login FROM receipt_reviews r LEFT JOIN users u ON u.id = r.user_id "
                     "WHERE r.status = 'open' ORDER BY r.id DESC LIMIT 100"),
        "strikes": q("SELECT s.*, u.login FROM receipt_strikes s LEFT JOIN users u ON u.id = s.user_id "
                     "ORDER BY s.id DESC LIMIT 100"),
        "log": q("SELECT l.*, u.login FROM receipt_guard_log l LEFT JOIN users u ON u.id = l.user_id "
                 "ORDER BY l.id DESC LIMIT 200"),
    }
