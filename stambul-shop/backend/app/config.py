"""Настройки магазина. Все значения — из окружения / .env."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"

    # --- Магазин ---
    shop_name: str = "Stambul Shop"
    shop_tagline: str = "Товары из Турции с доставкой по Казахстану"
    # Куда писать, если человек хочет спросить до заказа
    support_username: str = ""            # без @

    # --- Telegram ---
    bot_token: str = ""
    bot_username: str = "stambul_shop_bot"
    miniapp_short_name: str = "shop"
    channel_id: int = 0                   # витрина-канал с новинками
    channel_username: str = ""
    admin_chat_id: int = 0                # группа, куда падают заказы
    storage_chat_id: int = 0              # чат-хранилище фотографий
    admin_ids: str = ""

    # --- Адреса ---
    webapp_url: str = "http://localhost:5173"
    api_public_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # --- Хранилища ---
    database_url: str = "postgresql+asyncpg://shop:shop@localhost:5432/shop"
    redis_url: str = "redis://localhost:6379/0"
    media_cache_dir: str = "/data/media_cache"

    # --- Безопасность ---
    jwt_secret: str = "change-me"
    jwt_ttl: int = 43200
    init_data_ttl: int = 86400

    # --- Деньги ---
    currency: str = "KZT"
    currency_sign: str = "₸"
    # Стартовый курс. Настоящий выставляется в панели: цены в магазине
    # ведутся в тенге, доллар нужен только для пересчёта закупки.
    kzt_per_usd: float = 500.0

    # --- Доставка ---
    delivery_city_price: int = 1500       # курьер по городу
    delivery_country_price: int = 2500    # почтой по стране
    free_delivery_from: int = 30000       # бесплатно от этой суммы, 0 — выключено
    pickup_address: str = ""              # адрес самовывоза, пусто — нет самовывоза

    # --- Оплата ---
    # В Казахстане платят переводом на Kaspi. Приём карт требует юрлица и
    # договора с банком — на старте достаточно номера и ссылки.
    kaspi_phone: str = ""
    kaspi_name: str = ""                  # имя получателя, как в переводе
    kaspi_link: str = ""                  # ссылка на оплату, если есть

    # --- Витрина ---
    feed_w_freshness: float = 0.35
    feed_w_quality: float = 0.25
    feed_w_affinity: float = 0.25
    feed_w_jitter: float = 0.15

    # --- Ограничения ---
    max_photos: int = 10
    cart_max_items: int = 30
    order_min_total: int = 0

    @field_validator("channel_id", "admin_chat_id", "storage_chat_id", mode="before")
    @classmethod
    def _chat_id(cls, v):
        """Нечисловое значение (например имя канала) не должно ронять запуск."""
        try:
            return int(str(v).strip())
        except (TypeError, ValueError):
            return 0

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.replace(" ", "").split(",") if x]

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def miniapp_link(self) -> str:
        return f"https://t.me/{self.bot_username}/{self.miniapp_short_name}"

    @property
    def payment_ready(self) -> bool:
        return bool(self.kaspi_phone or self.kaspi_link)


@lru_cache
def get_settings() -> Settings:
    return Settings()
