"""Настройки приложения. Все значения берутся из окружения / .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"

    # --- Telegram ---
    bot_token: str = ""
    bot_username: str = "bozor_bot"           # без @
    miniapp_short_name: str = "app"           # short name из /newapp
    channel_id: int = 0                       # канал публикаций (-100...)
    channel_username: str = ""                # для ссылок t.me/<username>/<msg>
    admin_chat_id: int = 0                    # приватная группа модерации
    storage_chat_id: int = 0                  # чат-хранилище фото с сайта
    admin_ids: str = ""                       # tg_id через запятую

    # --- Адреса ---
    webapp_url: str = "http://localhost:5173"      # Mini App / сайт
    api_public_url: str = "http://localhost:8000"  # публичный адрес API
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # --- Хранилища ---
    database_url: str = "postgresql+asyncpg://bozor:bozor@localhost:5432/bozor"
    redis_url: str = "redis://localhost:6379/0"
    media_cache_dir: str = "/data/media_cache"

    # --- Безопасность ---
    jwt_secret: str = "change-me"
    jwt_ttl: int = 43200          # 12 часов
    init_data_ttl: int = 86400    # 24 часа

    # --- Бизнес ---
    tjs_per_usd: float = 10.9     # стартовый курс, обновляется в currency_rates
    daily_listing_limit: int = 3
    active_listing_limit: int = 10
    listing_ttl_days: int = 30
    max_photos: int = 10

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.replace(" ", "").split(",") if x]

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def miniapp_link(self) -> str:
        return f"https://t.me/{self.bot_username}/{self.miniapp_short_name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
