"""Конфигурация приложения. Все секреты берутся из .env."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    # список ID через запятую, например: "123456789,987654321"
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    database_url: str = "sqlite+aiosqlite:///./cargo.db"
    seed_on_start: bool = True

    @property
    def admin_ids(self) -> list[int]:
        return [int(x) for x in self.admin_ids_raw.replace(";", ",").split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
