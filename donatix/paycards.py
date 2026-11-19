"""Несколько карт на один банк: каждому клиенту — своя карта, суммы по картам ровные, чек — хозяину карты.

Как работает:
- у банка (способа оплаты, например «Душанбе Сити» или «Алиф») может быть несколько карт; у каждой — хозяин:
  кассир (его Telegram ID) или владелец магазина (0);
- клиент открывает пополнение → карты выдаются строго по очереди: 1-й клиент — А, 2-й — Б, 3-й — В, 4-й — снова А.
  Новая карта не забирает все переводы — каждая получает поровну с момента, как её добавили;
- выбранная карта держится за клиентом 2 часа (форма → заявка → чек — одна и та же карта) и записывается в заявку;
- чек приходит ТОЛЬКО хозяину этой карты (владельцу — в админ-чат, кассиру — ему одному);
- ИИ читает в чеке номер получателя: клиент по привычке перевёл на другую нашу карту — заявка сама уходит
  хозяину ТОЙ карты, и сумма засчитывается ей.
Нет ни одной включённой карты у банка — всё как раньше: реквизиты из настроек способа и кассиры по банкам.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db

HOLD_HOURS = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS pay_cards (
    id         INTEGER PRIMARY KEY,
    method     TEXT NOT NULL,
    details    TEXT NOT NULL,
    owner_tg   INTEGER NOT NULL DEFAULT 0,
    names      TEXT NOT NULL DEFAULT '',          -- имя получателя, как пишет банк в чеке: «Исомиддин Х., Isomiddin Kh»
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pay_card_hold (
    user_id INTEGER NOT NULL,
    method  TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    at      TEXT NOT NULL,
    PRIMARY KEY (user_id, method)
);
"""


class CardError(ValueError):
    pass


def ensure(conn: sqlite3.Connection) -> None:
    # executescript сам закрывает открытую транзакцию — поэтому только если таблиц ещё нет (обычно их создаёт db.init)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'pay_card_hold'").fetchone():
        conn.executescript(SCHEMA)
    if "card_id" not in {r[1] for r in conn.execute("PRAGMA table_info(payments)")}:
        conn.execute("ALTER TABLE payments ADD COLUMN card_id INTEGER")
    if "names" not in {r[1] for r in conn.execute("PRAGMA table_info(pay_cards)")}:
        conn.execute("ALTER TABLE pay_cards ADD COLUMN names TEXT NOT NULL DEFAULT ''")


# ── список карт (админка) ──

def listing(conn: sqlite3.Connection, method: str = "") -> list[sqlite3.Row]:
    ensure(conn)
    if method:
        return conn.execute("SELECT * FROM pay_cards WHERE method = ? ORDER BY id", (method,)).fetchall()
    return conn.execute("SELECT * FROM pay_cards ORDER BY method, id").fetchall()


def get(conn: sqlite3.Connection, card_id: int | None) -> sqlite3.Row | None:
    if not card_id:
        return None
    ensure(conn)
    return conn.execute("SELECT * FROM pay_cards WHERE id = ?", (int(card_id),)).fetchone()


def numbers(details: str) -> list[str]:
    """Номера в реквизитах: карты (16–19 цифр), счета и телефоны (от 9 цифр)."""
    return [d for d in (re.sub(r"\D", "", m) for m in re.findall(r"\+?\d[\d \-]{7,}\d", details or "")) if len(d) >= 9]


def add(conn: sqlite3.Connection, method: str, details: str, owner_tg: int = 0, names: str = "") -> int:
    ensure(conn)
    details = (details or "").strip()[:500]
    if not method:
        raise CardError("Выберите банк.")
    if not numbers(details):
        raise CardError("В реквизитах нет номера карты или телефона.")
    return int(conn.execute("INSERT INTO pay_cards (method, details, owner_tg, names, active, created_at) "
                            "VALUES (?, ?, ?, ?, 1, ?)",
                            (method, details, int(owner_tg or 0), clean_names(names), db.now())).lastrowid)


def clean_names(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").replace("\n", ", ")).strip(" ,")[:200]


def set_names(conn: sqlite3.Connection, card_id: int, names: str) -> None:
    """Имя получателя, как пишет банк в чеке (не показывается клиентам) — для чеков без номера."""
    ensure(conn)
    conn.execute("UPDATE pay_cards SET names = ? WHERE id = ?", (clean_names(names), card_id))


def set_active(conn: sqlite3.Connection, card_id: int, on: bool) -> None:
    ensure(conn)
    conn.execute("UPDATE pay_cards SET active = ? WHERE id = ?", (1 if on else 0, card_id))
    if not on:
        conn.execute("DELETE FROM pay_card_hold WHERE card_id = ?", (card_id,))


def delete(conn: sqlite3.Connection, card_id: int) -> None:
    ensure(conn)
    conn.execute("DELETE FROM pay_card_hold WHERE card_id = ?", (card_id,))
    conn.execute("DELETE FROM pay_cards WHERE id = ?", (card_id,))


# ── какую карту показать ──

def _day_start(tz_offset: int) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=tz_offset)
    return start.strftime("%Y-%m-%dT%H:%M:%S")


def load(conn: sqlite3.Connection, card_id: int, tz_offset: int = 5) -> int:
    """Сколько пришло на карту сегодня + сколько ждёт оплаты (за последние 2 часа), в micro-USD."""
    ensure(conn)
    since = _day_start(tz_offset)
    recent = (datetime.now(timezone.utc) - timedelta(hours=HOLD_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    return int(conn.execute(
        "SELECT COALESCE(SUM(amount_micro), 0) FROM payments WHERE card_id = ? AND ("
        "(status = 'paid' AND resolved_at >= ?) OR (status = 'pending' AND created_at >= ?))",
        (card_id, since, recent)).fetchone()[0])


def rest_on(conn: sqlite3.Connection) -> bool:
    """Отдых карт: у банка с 2+ картами каждый день одна карта не показывается (по кругу). Выключается в админке."""
    return db.get_setting(conn, "cards.rest", "1") == "1"


def resting_id(conn: sqlite3.Connection, method: str, tz_offset: int = 5) -> int:
    """Какая карта этого банка сегодня отдыхает: включённые карты по порядку, сегодня — следующая по кругу.
    Меньше двух карт — не отдыхает никто (иначе клиенту нечего показать)."""
    ensure(conn)
    if not rest_on(conn):
        return 0
    ids = [r[0] for r in conn.execute("SELECT id FROM pay_cards WHERE method = ? AND active = 1 ORDER BY id", (method,))]
    if len(ids) < 2:
        return 0
    day = (datetime.now(timezone.utc) + timedelta(hours=tz_offset)).date().toordinal()
    return ids[day % len(ids)]


def pick(conn: sqlite3.Connection, user_id: int, method: str, tz_offset: int = 5) -> sqlite3.Row | None:
    """Карта для этого клиента и банка — СТРОГО ПО ОЧЕРЕДИ: 1-й клиент — карта А, 2-й — Б, 3-й — В, 4-й — снова А…
    Так новая карта не забирает все переводы, а каждая получает поровну с момента запуска.
    Тот же клиент 2 часа видит ту же карту (форма → заявка → чек), это не новая очередь.
    Отдыхающую сегодня карту не показываем никому."""
    ensure(conn)
    rest = resting_id(conn, method, tz_offset)
    cards = [c for c in conn.execute("SELECT * FROM pay_cards WHERE method = ? AND active = 1 ORDER BY id",
                                     (method,)).fetchall() if c["id"] != rest]
    if not cards:
        return None
    fresh = (datetime.now(timezone.utc) - timedelta(hours=HOLD_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    if user_id:
        held = conn.execute("SELECT card_id FROM pay_card_hold WHERE user_id = ? AND method = ? AND at >= ?",
                            (user_id, method, fresh)).fetchone()
        if held:
            card = next((c for c in cards if c["id"] == held["card_id"]), None)
            if card is not None:
                return card
    key = f"cards.turn.{method}"
    try:
        last = int(db.get_setting(conn, key) or 0)
    except ValueError:
        last = 0
    card = next((c for c in cards if c["id"] > last), cards[0])   # следующая после выданной в прошлый раз, по кругу
    db.set_setting(conn, key, str(card["id"]))
    if user_id:
        conn.execute("INSERT INTO pay_card_hold (user_id, method, card_id, at) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT(user_id, method) DO UPDATE SET card_id = excluded.card_id, at = excluded.at",
                     (user_id, method, card["id"], db.now()))
    return card


def details_for(conn: sqlite3.Connection, user_id: int, method: str, default: str, tz_offset: int = 5) -> str:
    card = pick(conn, user_id, method, tz_offset)
    return card["details"] if card else default


def all_details(conn: sqlite3.Connection, method: str, default: str = "") -> str:
    """Все наши реквизиты — для ИИ. Каждая карта помечена «[карта #N]»: ИИ называет, на какую именно пришли деньги
    (our_card), и чек уходит хозяину этой карты. Сначала карты выбранного банка, потом наши карты других банков —
    клиент мог по привычке перевести на нашу карту другого банка."""
    ensure(conn)
    rows = conn.execute("SELECT id, method, details, names FROM pay_cards ORDER BY method != ?, method, id",
                        (method,)).fetchall()
    lines = [default] if default else []
    lines += [f"[карта #{r['id']}] " + ("" if r["method"] == method else f"(банк {r['method']}) ")
              + re.sub(r"\s+", " ", r["details"]) + (f" · имя получателя в чеке: {r['names']}" if r["names"] else "")
              for r in rows]
    return "\n".join(lines).strip()


_LAT = {"а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "e", "ж": "j", "з": "z", "и": "i",
        "ӣ": "i", "й": "i", "к": "k", "қ": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
        "т": "t", "у": "u", "ӯ": "u", "ф": "f", "х": "h", "ҳ": "h", "ц": "s", "ч": "ch", "ҷ": "j", "ш": "sh", "щ": "sh",
        "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya"}


def _skel(word: str) -> str:
    """Имя «скелетом»: кириллица → латиница, kh/x → h, y → i, двойные буквы — одна. «Исомиддин» = «Isomiddin»."""
    w = "".join(_LAT.get(ch, ch) for ch in word.lower())
    w = w.replace("kh", "h").replace("x", "h").replace("dzh", "j").replace("zh", "j").replace("y", "i").replace("w", "v")
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[^a-z]", "", w))


def _person(text: str) -> list[tuple[str, str]]:
    """Люди в тексте: (имя-скелет, первая буква фамилии или ''). «Исомиддин Х., Isomiddin Kh» → [("isomidin", "h"), …]."""
    out = []
    for part in re.split(r"[,;/\n]|\bили\b", text or ""):
        words = re.findall(r"[A-Za-zА-Яа-яЁёҒғӢӣҚқӮӯҲҳҶҷ]+", part)
        words = [w for w in words if w.lower() not in _SKIP]
        if not words or len(words[0]) < 3:
            continue
        initial = _skel(words[1])[:1] if len(words) > 1 else ""
        out.append((_skel(words[0]), initial))
    return out


def name_hits(recipient: str, cards: list) -> list:
    """Карты, чьё «имя получателя» совпадает с получателем из чека. Если в чеке есть буква фамилии — она тоже должна
    совпасть (два «Исомиддина» различаются по ней)."""
    seen = _person(recipient)
    if not seen:
        return []
    found = []
    for c in cards:
        mine = _person(c["names"] if "names" in c.keys() else "")
        if any(a == b and (not ia or not ib or ia == ib) for a, ia in seen for b, ib in mine):
            found.append(c)
    return found


_SKIP = {"карта", "карты", "получатель", "тел", "телефон", "счёт", "счет", "номер", "банк", "алиф", "сити", "душанбе",
         "card", "visa", "mastercard", "korti", "милли", "корти", "кому", "перевод", "на", "кошелек", "кошелёк", "гиранда",
         "қабулкунанда"}


def _names(details: str) -> set[str]:
    """Слова-имена из реквизитов (без «карта», «получатель» и т.п.) — для сверки по имени получателя."""
    skip = {"карта", "карты", "получатель", "тел", "телефон", "счёт", "счет", "номер", "банк", "алиф", "сити", "душанбе",
            "card", "visa", "mastercard", "korti", "милли", "корти"}
    return {w for w in (x.lower().replace("ё", "е") for x in re.findall(r"[A-Za-zА-Яа-яЁё]{3,}", details or ""))
            if w not in skip}


MASK = "*•●xXхХ#…"


def _strip992(d: str) -> str:
    """+992 93 555 44 33 и 93 555 44 33 — один и тот же номер."""
    return d[3:] if d.startswith("992") and len(d) >= 12 else d


def _chunks(recipient: str) -> list[str]:
    """Номера в строке получателя: «Фаррух +992 93 *** 44 33, карта 4444 55** **** 1111» → два куска."""
    return [c.strip() for c in re.findall(r"\+?[\d" + re.escape(MASK) + r"][\d" + re.escape(MASK) + r" \-.]*", recipient or "")
            if sum(ch.isdigit() for ch in c) >= 4]


def _fits(chunk: str, num: str) -> bool:
    """Подходит ли кусок из чека к нашему номеру num (только цифры).
    С маской: видимое начало — начало номера, видимый конец — конец номера, всего видно не меньше 4 цифр.
    Без маски: телефон/счёт — последние 9 цифр; карта целиком — равна; только 4 цифры — конец номера."""
    num = _strip992(num)
    mask_at = [i for i, ch in enumerate(chunk) if ch in MASK]
    if mask_at:
        head = re.sub(r"\D", "", chunk[:mask_at[0]])
        if head.startswith("992") and (chunk.lstrip().startswith("+") or len(num) <= 9):   # код страны у телефона
            head = head[3:]
        tail = re.sub(r"\D", "", chunk[mask_at[-1] + 1:])
        if len(head) + len(tail) < 4 or len(tail) < 2 or len(head) + len(tail) > len(num):
            return False
        return num.endswith(tail) and num.startswith(head)
    seen = _strip992(re.sub(r"\D", "", chunk))
    if len(seen) >= 9:
        return num.endswith(seen[-9:]) or seen.endswith(num[-9:])
    return len(seen) >= 4 and num.endswith(seen)


def labelled_hits(details_text: str, recipient: str | None) -> list[int]:
    """По тексту «[карта #N] реквизиты» (как его видит ИИ): номера наших карт, к которым подходит получатель по цифрам."""
    chunks = _chunks(recipient or "")
    hits = []
    for m in re.finditer(r"\[карта #(\d+)\]([^\n]*)", details_text or ""):
        if any(_fits(ch, n) for ch in chunks for n in numbers(m.group(2))):
            hits.append(int(m.group(1)))
    return hits


def match(conn: sqlite3.Connection, recipient: str, method: str = "") -> sqlite3.Row | None:
    """Наша карта по получателю из чека: номер карты/телефона (с масками и без), иначе имя.
    Подходит несколько карт — не гадаем (None)."""
    ensure(conn)
    sql, args = "SELECT * FROM pay_cards", ()
    if method:
        sql, args = sql + " WHERE method = ?", (method,)
    cards = conn.execute(sql, args).fetchall()
    chunks = _chunks(recipient)
    found = [c for c in cards if any(_fits(ch, n) for ch in chunks for n in numbers(c["details"]))]
    if not found:   # цифр нет или не совпали — по имени получателя
        words = _names(recipient)
        if words:
            found = [c for c in cards if words & _names(c["details"])]
    return found[0] if len(found) == 1 else None


def which_card(conn: sqlite3.Connection, method: str, seen: dict | None) -> tuple[sqlite3.Row | None, str]:
    """На какую НАШУ карту этого банка пришли деньги — по тому, что ИИ прочитал в чеке. Возвращает (карта, почему).
    1) номер в чеке однозначно совпал с одной нашей картой — это факт;
    2) иначе — карта, которую назвал ИИ, если цифры ей не противоречат;
    3) иначе — по имени получателя. Ничего однозначного — (None, причина): не гадаем."""
    ensure(conn)
    seen = seen or {}
    text = str(seen.get("recipient") or "")
    cards = conn.execute("SELECT * FROM pay_cards WHERE method = ?", (method,)).fetchall()
    chunks = _chunks(text)
    by_num = [c for c in cards if any(_fits(ch, n) for ch in chunks for n in numbers(c["details"]))]
    ai_card = get(conn, seen.get("our_card") or 0)
    seen_ai = ai_card if ai_card is not None and ai_card["method"] != method else None
    if seen_ai is not None:
        ai_card = None
    if len(by_num) == 1:
        return by_num[0], "номер получателя в чеке"
    if len(by_num) > 1:
        if ai_card is not None and ai_card["id"] in {c["id"] for c in by_num}:
            return ai_card, "номер подходит к нескольким картам — выбрал ИИ"
        return None, "номер подходит к нескольким нашим картам"
    if ai_card is not None:
        return ai_card, "ИИ узнал карту в чеке"
    by_name = name_hits(text, cards)
    if len(by_name) == 1:
        return by_name[0], "имя получателя"
    if len(by_name) > 1:
        return None, "имя подходит к нескольким нашим картам — укажите в админке и первую букву фамилии"
    named = match(conn, text, method)
    if named is not None:
        return named, "имя получателя"
    every = conn.execute("SELECT * FROM pay_cards").fetchall()   # перевёл на нашу карту ДРУГОГО банка
    other = [c for c in every if any(_fits(ch, n) for ch in chunks for n in numbers(c["details"]))]
    if len(other) == 1:
        return other[0], "номер получателя — наша карта другого банка"
    if not other and not chunks:
        other_names = name_hits(text, every)
        if len(other_names) == 1:
            return other_names[0], "имя получателя — наша карта другого банка"
    if not other and seen_ai is not None:
        return seen_ai, "ИИ узнал нашу карту другого банка"
    return None, "в чеке нет номера/имени нашей карты" if text else "ИИ не нашёл получателя в чеке"


def reroute(conn: sqlite3.Connection, payment_id: int, seen: dict | str) -> str:
    """Заявка переходит на карту, куда реально пришли деньги, — чек получает хозяин этой карты.
    Записывает в заявку, узнана ли карта (card_ok) и почему. Возвращает пометку для чека (или пустую строку)."""
    import json
    if isinstance(seen, str):
        seen = {"recipient": seen}
    ensure(conn)
    p = conn.execute("SELECT card_id, method, receipt_ai FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if p is None:
        return ""
    real, why = which_card(conn, p["method"], seen)
    shown = get(conn, p["card_id"])
    note = ""
    if real is not None and real["id"] != p["card_id"]:
        conn.execute("UPDATE payments SET card_id = ? WHERE id = ?", (real["id"], payment_id))
        note = (f"💳 ИИ: деньги пришли на карту ****{tail(real)} — заявка у хозяина этой карты" if shown is None else
                f"↪️ Клиент перевёл на карту ****{tail(real)} вместо показанной ****{tail(shown)} — "
                f"заявка у хозяина карты ****{tail(real)}")
    elif real is None and shown is not None:
        note = (f"❓ ИИ не узнал в чеке нашу карту ({why}). Показали клиенту ****{tail(shown)} — "
                f"проверьте в банке, на какую карту пришли деньги. Кассиру чек не отправлен.")
    try:
        data = json.loads(p["receipt_ai"]) if p["receipt_ai"] else {}
    except ValueError:
        data = {}
    if data or seen:
        data = {**data, "card_ok": real is not None, "card_why": why}
        if note:
            data["card_note"] = note
        conn.execute("UPDATE payments SET receipt_ai = ? WHERE id = ?", (json.dumps(data, ensure_ascii=False), payment_id))
    return note


def confirmed(conn: sqlite3.Connection, config: Any, payment: sqlite3.Row) -> bool:
    """Подтверждено ли, что деньги пришли именно на карту этой заявки — только тогда чек и кнопки у кассира-хозяина.
    ИИ выключен (нет ключа) — как раньше: верим показанной карте."""
    import json

    from . import receipt_ai
    if not receipt_ai.enabled(config):
        return True
    try:
        data = json.loads(payment["receipt_ai"]) if payment["receipt_ai"] else {}
    except (ValueError, TypeError):
        data = {}
    return bool(data.get("card_ok"))


def owner_name(conn: sqlite3.Connection, card: sqlite3.Row | None) -> str:
    if card is None:
        return ""
    if not card["owner_tg"]:
        return "владелец (админ-чат)"
    row = conn.execute("SELECT name, active FROM cashiers WHERE tg_id = ?", (card["owner_tg"],)).fetchone()
    if row is None:
        return f"кассир {card['owner_tg']} (не найден — чек уйдёт в админ-чат)"
    return f"кассир {row['name']}" + ("" if row["active"] else " (выключен — чек уйдёт в админ-чат)")


def tail(card: sqlite3.Row) -> str:
    return (numbers(card["details"]) or ["????"])[0][-4:]


def report(conn: sqlite3.Connection, tz_offset: int = 5) -> list[dict[str, Any]]:
    """Для админки: по каждой карте — чья, сколько заявок и денег сегодня."""
    ensure(conn)
    since = _day_start(tz_offset)
    out = []
    resting = {m: resting_id(conn, m, tz_offset) for m in {c["method"] for c in listing(conn)}}
    for c in listing(conn):
        r = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(amount_micro), 0) AS s FROM payments "
                         "WHERE card_id = ? AND status = 'paid' AND resolved_at >= ?", (c["id"], since)).fetchone()
        owner = "" if not c["owner_tg"] else (conn.execute("SELECT name FROM cashiers WHERE tg_id = ?",
                                                           (c["owner_tg"],)).fetchone() or {"name": str(c["owner_tg"])})["name"]
        out.append({**dict(c), "tail": tail(c), "owner_name": owner or "Вы (владелец)", "today_n": r["n"], "today_micro": r["s"],
                    "resting": resting.get(c["method"]) == c["id"]})
    return out


def explain(conn: sqlite3.Connection, config: Any, data: bytes) -> str:
    """Проверка вживую: настоящий ИИ читает этот чек → что прочитал → на какую нашу карту и кому уйдёт чек.
    Ничего не записывает. Для админ-бота (/chek) и команды на сервере (python -m donatix receipt-check фото.jpg)."""
    import html

    from . import payments, receipt_ai
    ensure(conn)
    ext = payments.receipt_kind(data)
    if not receipt_ai.enabled(config):
        return "⚠️ ИИ выключен: нет ключа OpenAI на сервере (deploy/openai.sh) — чеки читает только человек."
    if ext not in receipt_ai.MIME:
        return "⚠️ Пришлите чек картинкой (фото или скриншот). PDF ИИ не читает."
    methods = [r[0] for r in conn.execute("SELECT DISTINCT method FROM pay_cards WHERE active = 1 ORDER BY method")]
    if not methods:
        return "⚠️ Нет ни одной включённой карты (Админка → Карты)."
    conf = payments.settings(conn, config)["details"]
    details = "\n".join([conf.get(m, "") for m in methods if conf.get(m)] + [all_details(conn, "")])
    seen = receipt_ai.read(config, data, ext, our_details=details)
    if not seen:
        return "⚠️ ИИ не ответил (ключ, баланс OpenAI или сеть). Попробуйте ещё раз."
    e = html.escape
    lines = ["🧪 <b>Проверка чека ИИ</b> (ничего не записано)",
             f"Банк в чеке: {e(seen.get('bank') or '—')} · сумма: {seen.get('amount') or '—'} {e(seen.get('currency') or '')}",
             f"Получатель (прочитал ИИ): <code>{e(seen.get('recipient') or '—')}</code>",
             f"ИИ назвал нашу карту: {('#' + str(seen['our_card'])) if seen.get('our_card') else 'нет'}", ""]
    hits: dict[int, tuple[sqlite3.Row, str]] = {}
    for m in methods:
        card, why = which_card(conn, m, seen)
        if card is not None:
            hits.setdefault(card["id"], (card, why))
    if len(hits) == 1:
        card, why = next(iter(hits.values()))
        lines.append(f"✅ Деньги пришли на карту <b>****{tail(card)}</b> ({e(card['method'])}) — {e(why)}")
        lines.append(f"📨 Чек получит: <b>{e(owner_name(conn, card))}</b> + копия вам")
    elif hits:
        lines.append("⚠️ Подходят несколько карт: " + ", ".join(f"****{tail(c)} ({e(c['method'])})" for c, _ in hits.values())
                     + " — в заявке выберется карта банка, который выбрал клиент.")
    else:
        lines.append("❓ Ни одна наша карта не подошла — " + e(which_card(conn, methods[0], seen)[1]) + ".")
        lines.append("Чек придёт только вам (кассирам — нет): проверьте в банке, куда пришли деньги.")
    if seen.get("forgery") in ("suspicious", "fake"):
        lines.append("🚨 Признаки подделки: " + e("; ".join(seen.get("signs") or [seen["forgery"]])))
    return "\n".join(lines)
