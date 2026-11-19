from functools import lru_cache
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment / .env. Secrets never live in code."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://shop:shop_dev_pw@localhost:5432/shop"
    secret_key: str = Field(default="", min_length=0)
    session_days: int = 14

    supplier_api_url: str = "https://api.fzr.cards"
    supplier_api_key: str = ""
    supplier_timeout_seconds: float = 20.0
    catalog_cache_seconds: int = 600

    default_markup_percent: Decimal = Decimal("10")
    # safety limits (can be changed in the admin panel)
    default_max_order_usd: Decimal = Decimal("200")
    default_daily_user_usd: Decimal = Decimal("1000")
    order_sync_enabled: bool = True
    order_sync_interval_seconds: int = 20
    admin_emails: str = ""
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if len(s.secret_key) < 32:
        raise RuntimeError("SECRET_KEY в .env должен быть не короче 32 символов")
    return s
