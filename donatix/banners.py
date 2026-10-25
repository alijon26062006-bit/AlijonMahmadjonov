"""Рекламные баннеры вверху страниц (как лента акций в приложениях магазинов).

Баннеры ставит админ: картинка, ссылка, порядок, даты показа. Картинку сайт сам обрезает до 5:2 и
сохраняет в WebP двумя размерами (телефон / компьютер) — лёгкая и чёткая на любом экране.
Нажатие идёт через /bn/go/<id>: считаем клики и только потом уводим на ссылку.
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


def ensure(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)


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
    return conn.execute("SELECT * FROM banners ORDER BY active DESC, sort, id DESC").fetchall()


def active(conn: sqlite3.Connection, today: str | None = None) -> list[dict[str, Any]]:
    """Что показывать сейчас: включённые и в сроке. Кэш на 30 секунд — список нужен на каждой странице."""
    def load() -> list[dict[str, Any]]:
        ensure(conn)
        from datetime import date
        day = today or date.today().isoformat()
        rows = conn.execute(
            "SELECT id, title, image, link FROM banners WHERE active = 1 "
            "AND (starts_at IS NULL OR starts_at <= ?) AND (ends_at IS NULL OR ends_at >= ?) "
            "ORDER BY sort, id DESC LIMIT ?", (day, day, MAX_ACTIVE)).fetchall()
        return [{"id": r["id"], "title": r["title"], "link": r["link"],
                 "src": f"/bn/{r['image']}-{SIZES[0]}.webp", "src_small": f"/bn/{r['image']}-{SIZES[1]}.webp"}
                for r in rows]
    if today is not None:
        return load()
    return cache.get_or_set(CACHE_KEY, 30, load)


def click(conn: sqlite3.Connection, bid: int) -> str | None:
    """Засчитать нажатие и вернуть ссылку (None — баннера нет или ссылки нет)."""
    ensure(conn)
    row = conn.execute("SELECT link FROM banners WHERE id = ? AND active = 1", (bid,)).fetchone()
    if row is None or not row["link"]:
        return None
    conn.execute("UPDATE banners SET clicks = clicks + 1 WHERE id = ?", (bid,))
    return row["link"]
