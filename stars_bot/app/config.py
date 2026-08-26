"""Конфигурация бота. Все значения читаются из .env."""
from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        ignored_types=(cached_property,),
    )

    bot_token: str
    # Читаем как строку: pydantic-settings пытается json-декодить list-поля
    # из .env, а мы хотим человеческий формат "111,222".
    admin_ids_raw: str = Field(default="", validation_alias=AliasChoices("ADMIN_IDS", "admin_ids"))
    orders_chat_id: int | None = None

    payment_card_number: str = ""
    payment_card_holder: str = ""
    payment_bank: str = ""
    currency: str = "UZS"

    fragment_mode: str = "mock"
    fragment_base_url: str = "https://api.fragment.com"
    fragment_api_key: str = ""
    fragment_phone_number: str = ""
    fragment_mnemonics: str = ""

    db_path: str = "data/bot.sqlite3"
    support_username: str = ""
    log_level: str = "INFO"

    @cached_property
    def admin_ids(self) -> list[int]:
        raw = self.admin_ids_raw.replace(";", ",")
        return [int(part.strip()) for part in raw.split(",") if part.strip()]

    @field_validator("orders_chat_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def db_file(self) -> Path:
        path = Path(self.db_path)
        return path if path.is_absolute() else BASE_DIR / path

    @property
    def mnemonics_list(self) -> list[str]:
        return self.fragment_mnemonics.split()

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


settings = Settings()  # type: ignore[call-arg]
