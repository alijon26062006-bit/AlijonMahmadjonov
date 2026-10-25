"""Рекламные баннеры вверху страниц (как лента акций в приложениях магазинов).

Баннеры ставит админ: картинка, ссылка, порядок, даты показа. Картинку сайт сам обрезает до 5:2 и
сохраняет в WebP двумя размерами (телефон / компьютер) — лёгкая и чёткая на любом экране.
Нажатие идёт через /bn-go/<id>: считаем клики и только потом уводим на ссылку.
"""

from __future__ import annotations

import io
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from . import cache, db
from .config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS banners (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',     -- подпись для доступности (alt) и для админки
    image       TEXT NOT NULL,                -- имя файла без размера: <name>-1500.webp / <name>-750.webp
    link        TEXT NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1,
    sort        INTEGER NOT NULL DEFAULT 0,
    starts_at   TEXT,                         -- YYYY-MM-DD; пусто — сразу
    ends_at     TEXT,                         -- YYYY-MM-DD включительно; пусто — без срока
    clicks      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
)
"""
RATIO = (5, 2)                 # ширина : высота — на телефоне баннер ~150 px в высоту, не закрывает экран
SIZES = (1500, 750)            # компьютер / телефон
MAX_BYTES = 8 * 1024 * 1024
MAX_ACTIVE = 10
CACHE_KEY = "banners:active"


class BannerError(ValueError):
    pass


DAYS = (1, 2, 3)               # срок показа в заявке пользователя (дольше — подаёт заново)
PRICE_TJS_DAY = 7              # цена показа клиентского баннера, сомони за день
STATUS_TITLES = {"pending": "На проверке", "approved": "Одобрен", "rejected": "Отклонён"}
#: Что нельзя рекламировать — показываем людям в разделе «Реклама» и в админке
FORBIDDEN = (
    ("🎰", "Азартные игры", "казино, ставки, букмекеры, рулетки, «кейсы», лотереи на деньги"),
    ("🛒", "Конкуренты", "другие магазины доната, пополнений игр, Stars и Premium"),
    ("©️", "Чужие бренды", "логотипы и картинки игр, банков, Telegram, Garena и т. д."),
    ("💸", "«Лёгкий заработок»", "пирамиды, «заработок на SMS», инвестиции с гарантией дохода"),
    ("🔞", "18+", "интим, насилие, оружие, наркотики, алкоголь и табак"),
    ("🎣", "Обман", "фишинг, продажа аккаунтов, накрутки, взломы, фейковые раздачи"),
)


def ensure(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(banners)")}
    for col, kind in (("user_id", "INTEGER"), ("status", "TEXT NOT NULL DEFAULT 'approved'"), ("days", "INTEGER"),
                      ("note", "TEXT NOT NULL DEFAULT ''"), ("paid_micro", "INTEGER NOT NULL DEFAULT 0")):
        if col not in cols:   # заявки пользователей: чьё, статус проверки, срок, причина отказа
            conn.execute(f"ALTER TABLE banners ADD COLUMN {col} {kind}")


def folder(config: Config) -> Path:
    return Path(config.db_path).parent / "banners"


def clean_link(link: str) -> str:
    """Куда ведёт баннер: страница сайта (/…), https:// или Telegram. Другое (javascript:, http://) — нельзя."""
    link = (link or "").strip()
    if not link:
        return ""
    if link.startswith("/") and not link.startswith("//"):
        return link[:500]
    if link.startswith("t.me/"):
        link = "https://" + link
    if not link.startswith("https://") or any(c in link for c in ' "<>\'\\') or len(link) > 500:
        raise BannerError("Ссылка — адрес страницы сайта (/…), https://… или t.me/…")
    return link


def save_image(config: Config, data: bytes) -> str:
    """Картинку → два WebP 5:2 (обрезка по центру). Вернёт общее имя файлов."""
    if not data or len(data) > MAX_BYTES:
        raise BannerError("Картинка пустая или больше 8 МБ.")
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001 — не картинка или повреждена
        raise BannerError("Нужна картинка: JPG, PNG или WebP.") from None
    if im.format not in ("JPEG", "PNG", "WEBP", "GIF"):
        raise BannerError("Нужна картинка: JPG, PNG или WebP.")
    im = ImageOps.exif_transpose(im).convert("RGB")
    name = secrets.token_hex(8)
    out = folder(config)
    out.mkdir(parents=True, exist_ok=True)
    for width in SIZES:
        height = width * RATIO[1] // RATIO[0]
        ImageOps.fit(im, (width, height), Image.LANCZOS).save(out / f"{name}-{width}.webp", "WEBP", quality=80, method=6)
    return name


def remove_files(config: Config, name: str) -> None:
    for width in SIZES:
        (folder(config) / f"{name}-{width}.webp").unlink(missing_ok=True)


def create(conn: sqlite3.Connection, config: Config, *, data: bytes, title: str, link: str, sort: int = 0,
           starts_at: str = "", ends_at: str = "") -> int:
    ensure(conn)
    link = clean_link(link)
    starts_at, ends_at = _date(starts_at), _date(ends_at)
    name = save_image(config, data)
    with db.tx(conn):
        bid = int(conn.execute(
            "INSERT INTO banners (title, image, link, sort, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ((title or "").strip()[:120], name, link, int(sort), starts_at, ends_at, db.now())).lastrowid)
    cache.clear(CACHE_KEY)
    return bid


def update(conn: sqlite3.Connection, bid: int, *, title: str, link: str, sort: int, starts_at: str, ends_at: str) -> None:
    ensure(conn)
    conn.execute("UPDATE banners SET title = ?, link = ?, sort = ?, starts_at = ?, ends_at = ? WHERE id = ?",
                 ((title or "").strip()[:120], clean_link(link), int(sort), _date(starts_at), _date(ends_at), bid))
    cache.clear(CACHE_KEY)


def toggle(conn: sqlite3.Connection, bid: int) -> None:
    ensure(conn)
    conn.execute("UPDATE banners SET active = 1 - active WHERE id = ?", (bid,))
    cache.clear(CACHE_KEY)


def delete(conn: sqlite3.Connection, config: Config, bid: int) -> None:
    ensure(conn)
    row = conn.execute("SELECT image FROM banners WHERE id = ?", (bid,)).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM banners WHERE id = ?", (bid,))
    remove_files(config, row["image"])
    cache.clear(CACHE_KEY)


def _date(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    from datetime import date
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        raise BannerError("Дата — в виде ГГГГ-ММ-ДД.") from None


def all_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    ensure(conn)
    return conn.execute("SELECT * FROM banners WHERE status != 'pending' ORDER BY active DESC, sort, id DESC").fetchall()


def active(conn: sqlite3.Connection, today: str | None = None) -> list[dict[str, Any]]:
    """Что показывать сейчас: включённые и в сроке. Кэш на 30 секунд — список нужен на каждой странице."""
    def load() -> list[dict[str, Any]]:
        ensure(conn)
        from datetime import date
        day = today or date.today().isoformat()
        rows = conn.execute(
            "SELECT id, title, image, link FROM banners WHERE active = 1 AND status = 'approved' "
            "AND (starts_at IS NULL OR starts_at <= ?) AND (ends_at IS NULL OR ends_at >= ?) "
            "ORDER BY sort, id DESC LIMIT ?", (day, day, MAX_ACTIVE)).fetchall()
        return [{"id": r["id"], "title": r["title"], "link": r["link"],
                 "src": f"/static/bn/{r['image']}-{SIZES[0]}.webp", "src_small": f"/static/bn/{r['image']}-{SIZES[1]}.webp"}
                for r in rows]
    if today is not None:
        return load()
    return cache.get_or_set(CACHE_KEY, 30, load)


def click(conn: sqlite3.Connection, bid: int) -> str | None:
    """Засчитать нажатие и вернуть ссылку (None — баннера нет или ссылки нет)."""
    ensure(conn)
    row = conn.execute("SELECT link FROM banners WHERE id = ? AND active = 1 AND status = 'approved'",
                       (bid,)).fetchone()
    if row is None or not row["link"]:
        return None
    conn.execute("UPDATE banners SET clicks = clicks + 1 WHERE id = ?", (bid,))
    return row["link"]


# ── Заявки пользователей ─────────────────────────────────────


def price_micro(conn: sqlite3.Connection, config: Config, days: int) -> int:
    """Цена показа в микро-долларах баланса: сомони по курсу сайта, округление вверх."""
    from decimal import Decimal

    from .money import to_micro_ceil
    from .payments import settings
    rate = Decimal(str(settings(conn, config)["tjs_rate"] or config.tjs_rate))
    return to_micro_ceil(Decimal(PRICE_TJS_DAY * days) / rate)


def submit(conn: sqlite3.Connection, config: Config, user_id: int, *, data: bytes, title: str, link: str,
           days: int) -> int:
    """Заявка на рекламу: баннер сохраняется, но не показывается, пока админ не одобрит."""
    ensure(conn)
    if days not in DAYS:
        raise BannerError("Выберите срок показа.")
    if not (title or "").strip():
        raise BannerError("Напишите, что рекламируете.")
    link = clean_link(link)
    if not link:
        raise BannerError("Укажите ссылку: https://… или t.me/…")
    open_n = conn.execute("SELECT COUNT(*) FROM banners WHERE user_id = ? AND status = 'pending'", (user_id,)).fetchone()[0]
    if open_n >= 3:
        raise BannerError("У вас уже 3 заявки на проверке — дождитесь ответа.")
    from .accounts import InsufficientBalance, post_ledger
    price = price_micro(conn, config, days)
    name = save_image(config, data)
    try:
        with db.tx(conn):
            bid = int(conn.execute(
                "INSERT INTO banners (title, image, link, active, sort, user_id, status, days, paid_micro, created_at) "
                "VALUES (?, ?, ?, 0, 100, ?, 'pending', ?, ?, ?)",
                (title.strip()[:120], name, link, user_id, days, price, db.now())).lastrowid)
            post_ledger(conn, user_id, -price, f"Реклама на сайте: заявка #{bid}, {days} дн.")
    except InsufficientBalance:
        remove_files(config, name)
        raise BannerError(f"Не хватает денег на балансе: показ на {days} дн. стоит {PRICE_TJS_DAY * days} сомони. "
                          "Пополните баланс и отправьте заявку снова.") from None
    return bid


def decide(conn: sqlite3.Connection, bid: int, approve: bool, note: str = "") -> sqlite3.Row | None:
    """Одобрить (показ с сегодня на выбранный срок) или отклонить с причиной."""
    ensure(conn)
    from datetime import date, timedelta
    row = conn.execute("SELECT * FROM banners WHERE id = ? AND status = 'pending'", (bid,)).fetchone()
    if row is None:
        return None
    if approve:
        start = date.today()
        end = start + timedelta(days=max(int(row["days"] or 1), 1) - 1)
        conn.execute("UPDATE banners SET status = 'approved', active = 1, starts_at = ?, ends_at = ?, note = '' "
                     "WHERE id = ?", (start.isoformat(), end.isoformat(), bid))
    else:
        from .accounts import post_ledger
        with db.tx(conn):   # отказ — деньги назад на баланс
            conn.execute("UPDATE banners SET status = 'rejected', active = 0, note = ? WHERE id = ?",
                         ((note or "").strip()[:300], bid))
            if row["paid_micro"] and row["user_id"]:
                post_ledger(conn, row["user_id"], row["paid_micro"], f"Возврат: реклама #{bid} отклонена")
    cache.clear(CACHE_KEY)
    return conn.execute("SELECT * FROM banners WHERE id = ?", (bid,)).fetchone()


def of_user(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    ensure(conn)
    return conn.execute("SELECT * FROM banners WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()


def pending(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    ensure(conn)
    return conn.execute("SELECT b.*, u.login FROM banners b LEFT JOIN users u ON u.id = b.user_id "
                        "WHERE b.status = 'pending' ORDER BY b.id").fetchall()
