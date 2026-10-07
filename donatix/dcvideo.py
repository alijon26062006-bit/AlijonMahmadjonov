"""Обязательная видео-инструкция перед оплатой «Душанбе Сити · авто».

Клиент, который пополняет через «Душанбе Сити», сначала смотрит видео и отмечает «Посмотрел — за ошибку
в переводе отвечаю сам». Только после этого видит реквизиты. Отметка хранится у аккаунта; видео потом
доступно по кнопке. Админ заменил видео — смотреть нужно заново (у видео новая версия).

Видео два, отдельно: для сайта (kind="site") и для бота-магазина (kind="bot"). Каждое — загруженный файл
(MP4/WebM/MOV) или ссылка (YouTube, прямая ссылка на MP4). Настраивается в админке → Реквизиты.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import db
from .config import Config

KINDS = ("site", "bot")
TYPES = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}
MAX_BYTES = 50 * 1024 * 1024        # больше Telegram-бот всё равно не отправит
NAME_RE = re.compile(r"[a-f0-9]{16}\.(mp4|webm|mov)")
YOUTUBE_RE = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{6,20})")


class VideoError(ValueError):
    pass


def videos_dir(config: Config) -> Path:
    path = Path(config.db_path).parent / "videos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS dc_video_ack (user_id INTEGER NOT NULL, kind TEXT NOT NULL, "
                 "version TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (user_id, kind))")


def get(conn: sqlite3.Connection, kind: str) -> dict[str, Any] | None:
    """Видео для сайта или бота: {"file": имя файла | "", "url": ссылка | "", "youtube": id | "", "version"}."""
    raw = (db.get_setting(conn, f"pay.dc_video_{kind}") or "").strip()
    if not raw:
        return None
    version = db.get_setting(conn, f"pay.dc_video_{kind}_v") or "1"
    if NAME_RE.fullmatch(raw):
        return {"file": raw, "url": "", "youtube": "", "version": version}
    yt = YOUTUBE_RE.search(raw)
    return {"file": "", "url": raw, "youtube": yt.group(1) if yt else "", "version": version}


def set_video(conn: sqlite3.Connection, config: Config, kind: str, *, data: bytes = b"", content_type: str = "",
              url: str = "", delete: bool = False) -> None:
    """Загрузить файл, задать ссылку или убрать видео. Новое видео — новая версия: смотреть заново."""
    if kind not in KINDS:
        raise VideoError("Неизвестное место для видео.")
    old = get(conn, kind)
    if delete:
        value = ""
    elif data:
        if len(data) > MAX_BYTES:
            raise VideoError("Видео больше 50 МБ — сожмите его или дайте ссылку на YouTube.")
        ext = TYPES.get((content_type or "").split(";")[0].strip()) or _sniff(data)
        if ext is None:
            raise VideoError("Видео — файл MP4, WebM или MOV.")
        value = f"{secrets.token_hex(8)}.{ext}"
        (videos_dir(config) / value).write_bytes(data)
    elif url.strip():
        value = url.strip()[:500]
        if not value.startswith("https://"):
            raise VideoError("Ссылка на видео должна начинаться с https:// (YouTube или прямая ссылка на MP4).")
    else:
        return
    db.set_setting(conn, f"pay.dc_video_{kind}", value)
    db.set_setting(conn, f"pay.dc_video_{kind}_v", f"{int(time.time())}-{secrets.token_hex(3)}")
    if kind == "bot":
        db.set_setting(conn, "pay.dc_video_bot_fid", "")   # file_id Telegram — от старого файла
    if old and old["file"] and old["file"] != value:
        (videos_dir(config) / old["file"]).unlink(missing_ok=True)


def _sniff(data: bytes) -> str | None:
    if data[4:8] == b"ftyp":
        return "mov" if data[8:10] == b"qt" else "mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    return None


def needed(conn: sqlite3.Connection, user_id: int, kind: str) -> dict[str, Any] | None:
    """Видео, которое клиент ещё не посмотрел (или посмотрел старое). None — смотреть нечего."""
    video = get(conn, kind)
    if video is None:
        return None
    _ensure_table(conn)
    row = conn.execute("SELECT version FROM dc_video_ack WHERE user_id = ? AND kind = ?", (user_id, kind)).fetchone()
    return None if row is not None and row["version"] == video["version"] else video


def ack(conn: sqlite3.Connection, user_id: int, kind: str) -> None:
    """Клиент посмотрел и согласился: за ошибку в переводе отвечает сам."""
    video = get(conn, kind)
    if video is None:
        return
    _ensure_table(conn)
    conn.execute("INSERT INTO dc_video_ack (user_id, kind, version, at) VALUES (?, ?, ?, ?) "
                 "ON CONFLICT(user_id, kind) DO UPDATE SET version = excluded.version, at = excluded.at",
                 (user_id, kind, video["version"], db.now()))


def src(config: Config, video: dict[str, Any]) -> str:
    """Адрес видео для страницы."""
    return f"{config.base_url}/pay-videos/{video['file']}" if video["file"] else video["url"]
