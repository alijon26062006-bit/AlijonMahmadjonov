"""Настройки бота курса. Читаются из окружения или из файла course_bot/.env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: frozenset[int]
    db_path: Path
    tz_name: str = "Asia/Dushanbe"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


def _parse_ids(raw: str) -> frozenset[int]:
    ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError as exc:
                raise ValueError(f"ADMIN_IDS: {part!r} — это не число") from exc
    return frozenset(ids)


def load_config() -> Config:
    load_dotenv(HERE / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("не задан BOT_TOKEN (токен от @BotFather) в course_bot/.env")
    admins = _parse_ids(os.getenv("ADMIN_IDS", ""))
    if not admins:
        raise RuntimeError("не задан ADMIN_IDS (ваш id в Telegram) в course_bot/.env")
    db_path = Path(os.getenv("DB_PATH", HERE / "data" / "course.db"))
    tz_name = os.getenv("TZ_NAME", "Asia/Dushanbe").strip() or "Asia/Dushanbe"
    ZoneInfo(tz_name)  # опечатка в поясе — ошибка сразу при запуске
    return Config(token=token, admin_ids=admins, db_path=db_path, tz_name=tz_name)
