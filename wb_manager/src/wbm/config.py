"""Настройки приложения. Читаются из переменных окружения или файла .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WBSettings(BaseSettings):
    """Настройки клиента Wildberries API (переменные с префиксом WB_)."""

    model_config = SettingsConfigDict(
        env_prefix="WB_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    sandbox: bool = False
    timeout_connect: float = Field(default=10.0, gt=0)
    timeout_read: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=4, ge=0, le=10)
    max_rate_limit_retries: int = Field(default=5, ge=0, le=20)
    backoff_base: float = Field(default=1.0, gt=0)
    backoff_max: float = Field(default=30.0, gt=0)
    max_wait: float = Field(default=300.0, gt=0)
    max_concurrency: int = Field(default=4, ge=1, le=32)


class AppSettings(BaseSettings):
    """Общие настройки приложения."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_wb_settings() -> WBSettings:
    return WBSettings()


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()
