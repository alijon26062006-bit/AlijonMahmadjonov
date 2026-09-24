"""Настройки Donatix. Читаются из окружения или из файла .env в папке donatix/."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TIERS = ("bronze", "silver", "gold")


def _load_dotenv(path: Path) -> None:
    """Мини-загрузчик .env: KEY=VALUE, комментарии через #. Окружение важнее файла."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _flag(name: str, default: bool) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in ("1", "true", "yes", "on")


@dataclass
class Config:
    secret_key: str
    db_path: Path
    site_name: str = "Donatix"
    base_url: str = "http://localhost:8000"

    # Поставщик: "fazer" — настоящий FazerCards, "mock" — игрушечный для разработки.
    supplier: str = "mock"
    fazer_api_key: str = ""
    fazer_base_url: str = "https://api.fzr.cards/api/v2"

    # Наценка в процентах поверх закупочной цены, по уровням клиентов.
    markups: dict[str, Decimal] = field(
        default_factory=lambda: {"bronze": Decimal("8"), "silver": Decimal("6"), "gold": Decimal("4")}
    )

    # Первый админ создаётся при запуске, если таких пользователей ещё нет.
    admin_email: str = ""
    admin_password: str = ""

    # Фоновый обработчик (проверка заказов, обновление каталога) внутри веб-процесса.
    run_worker: bool = True
    catalog_sync_minutes: int = 15
    order_poll_seconds: int = 20

    # Предупреждение, когда баланс у поставщика меньше этой суммы (USD).
    supplier_low_balance: Decimal = Decimal("50")
    alert_telegram_token: str = ""
    alert_telegram_chat_id: str = ""

    # Новые клиенты ждут одобрения админа.
    require_approval: bool = True
    cookie_secure: bool = False

    # Куда писать клиентам для пополнения баланса и поддержки (например, @donatix_support).
    support_contact: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv(ROOT / ".env")
        secret = _env("DONATIX_SECRET_KEY")
        if not secret:
            # Без ключа сессии слетают при каждом перезапуске — годится только для разработки.
            secret = secrets.token_urlsafe(32)
        markups = {}
        for tier, default in (("bronze", "8"), ("silver", "6"), ("gold", "4")):
            markups[tier] = Decimal(_env(f"DONATIX_MARKUP_{tier.upper()}", default))
        return cls(
            secret_key=secret,
            db_path=Path(_env("DONATIX_DB", str(ROOT / "data" / "donatix.db"))),
            site_name=_env("DONATIX_SITE_NAME", "Donatix"),
            base_url=_env("DONATIX_BASE_URL", "http://localhost:8000").rstrip("/"),
            supplier=_env("DONATIX_SUPPLIER", "mock").lower(),
            fazer_api_key=_env("FAZER_API_KEY"),
            fazer_base_url=_env("FAZER_BASE_URL", "https://api.fzr.cards/api/v2").rstrip("/"),
            markups=markups,
            admin_email=_env("DONATIX_ADMIN_EMAIL").lower(),
            admin_password=_env("DONATIX_ADMIN_PASSWORD"),
            run_worker=_flag("DONATIX_RUN_WORKER", True),
            catalog_sync_minutes=int(_env("DONATIX_CATALOG_SYNC_MINUTES", "15")),
            order_poll_seconds=int(_env("DONATIX_ORDER_POLL_SECONDS", "20")),
            supplier_low_balance=Decimal(_env("DONATIX_SUPPLIER_LOW_BALANCE", "50")),
            alert_telegram_token=_env("DONATIX_ALERT_TELEGRAM_TOKEN"),
            alert_telegram_chat_id=_env("DONATIX_ALERT_TELEGRAM_CHAT_ID"),
            require_approval=_flag("DONATIX_REQUIRE_APPROVAL", True),
            cookie_secure=_flag("DONATIX_COOKIE_SECURE", False),
            support_contact=_env("DONATIX_SUPPORT_CONTACT"),
        )
