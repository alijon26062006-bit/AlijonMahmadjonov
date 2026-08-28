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

    # ---- деньги ----
    currency: str = "с."
    # Цена одной звезды в дирамах (1 сомони = 100 дирам). 20 = 0.20 сомони.
    star_price_diram: int = 20
    min_stars: int = 50
    max_stars: int = 10_000
    min_deposit_diram: int = 1000
    referral_percent: int = 5

    # ---- реквизиты для пополнения ----
    pay_card_number: str = ""
    pay_card_holder: str = ""
    pay_card_bank: str = ""
    pay_city: str = "Душанбе"
    pay_extra: str = ""
    dc_account: str = ""
    dc_comment: str = ""
    dc_service: str = "133"

    # ---- шлюз выдачи (apifragment.online) ----
    fragment_mode: str = "mock"
    fragment_base_url: str = "https://apifragment.online"
    fragment_api_key: str = ""
    # Сид-фраза кошелька: шлюз логинится ею на Fragment и хранит сессию у себя.
    fragment_wallet_seed: str = ""
    fragment_payment_method: str = "ton"   # ton | usdt_ton
    # Заказ выполняется асинхронно: ждём результат опросом задачи.
    task_poll_interval: int = 3
    task_poll_timeout: int = 300

    # ---- FazerCards (api.fzr.cards) ----
    # Баланс реселлера пополняется один раз, сид-фраза не нужна.
    fazer_api_key: str = ""
    fazer_base_url: str = "https://api.fzr.cards"
    # Пути из разделов Orders и Account: их надо сверить с документацией,
    # угадывать молча нельзя — от них зависит подтверждение выдачи.
    fazer_order_path: str = "/api/v2/orders/{order_id}"
    fazer_balance_path: str = "/api/v2/account"

    # ---- MyStars FaaS (api.mystars.tg) ----
    # Ключ выдаётся в @my_stars_tg_bot. Сид-фраза сервису НЕ передаётся.
    mystars_api_key: str = ""
    mystars_base_url: str = "https://api.mystars.tg/v1"
    mystars_currency: str = "ton"          # ton | usdt_ton
    # Сколько ждать оплату и доставку (окно оплаты у MyStars — 2 часа)
    mystars_wait_timeout: int = 1800

    # ---- ссылки ----
    support_username: str = ""
    reviews_url: str = ""
    telegapay_key: str = ""
    news_url: str = ""
    bot_username: str = ""

    db_path: str = "data/bot.sqlite3"
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

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


settings = Settings()  # type: ignore[call-arg]
