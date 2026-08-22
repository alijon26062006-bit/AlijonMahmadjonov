"""Настройки из переменных окружения (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Не хватает обязательной настройки."""


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должно быть числом, получено: {raw!r}") from exc


def _str(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _ids(name: str) -> tuple[int, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    parts = raw.replace(";", ",").split(",")
    return tuple(int(p.strip()) for p in parts if p.strip())


@dataclass(frozen=True)
class Settings:
    mother_bot_token: str
    anthropic_api_key: str
    model: str
    chat_model: str
    fernet_key: str
    db_path: str
    brand_name: str
    max_bots_per_user: int
    ai_monthly_limit: int
    ai_history_limit: int
    admin_ids: tuple[int, ...]


def load_settings() -> Settings:
    token = os.getenv("MOTHER_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "MOTHER_BOT_TOKEN не задан. Возьмите токен главного бота у @BotFather "
            "и впишите его в файл .env"
        )

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY не задан. Получите ключ на platform.claude.com "
            "и впишите его в файл .env"
        )

    fernet_key = os.getenv("FERNET_KEY", "").strip()
    if not fernet_key:
        raise ConfigError(
            "FERNET_KEY не задан. Сгенерируйте ключ командой `python -m botfactory.crypto` "
            "и впишите его в .env — им шифруются чужие токены в базе."
        )

    return Settings(
        mother_bot_token=token,
        anthropic_api_key=api_key,
        model=_str("ANTHROPIC_MODEL", "claude-opus-5"),
        chat_model=_str("ANTHROPIC_CHAT_MODEL", "claude-sonnet-5"),
        fernet_key=fernet_key,
        db_path=_str("DB_PATH", "data/factory.db"),
        brand_name=_str("BRAND_NAME", "Bot Factory"),
        max_bots_per_user=_int("MAX_BOTS_PER_USER", 3),
        ai_monthly_limit=_int("AI_MONTHLY_LIMIT", 500),
        ai_history_limit=_int("AI_HISTORY_LIMIT", 10),
        admin_ids=_ids("ADMIN_IDS"),
    )
