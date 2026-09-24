"""Настройки Donatix. Читаются из окружения или из файла .env в папке donatix/."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TIERS = ("bronze", "silver", "gold")

# Способы пополнения баланса: код → (название, валюта перевода).
PAY_METHODS = {
    "alif": ("Алиф (Alif Mobi)", "TJS"),
    "dc": ("Душанбе Сити (DC)", "TJS"),
    "eskhata": ("Эсхата", "TJS"),
    "korti_milli": ("Корти Милли", "TJS"),
    "usdt_trc20": ("USDT TRC20", "USDT"),
    "binance": ("Binance Pay", "USDT"),
}


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
    # Скидка вашего тарифа FazerCards на пополнение Steam, %.
    fazer_steam_discount: Decimal = Decimal("2.5")
    # Адрес, к которому дописываются пути картинок поставщика (пусто — домен из FAZER_BASE_URL)
    fazer_image_base: str = ""
    # Пауза между запросами каталога, сек. Больше — медленнее загрузка, но другим ботам на том же ключе
    # остаётся больше лимита FazerCards.
    fazer_catalog_pause: float = 2.0

    # Наценка в процентах поверх закупочной цены, по уровням клиентов.
    markups: dict[str, Decimal] = field(
        default_factory=lambda: {"bronze": Decimal("8"), "silver": Decimal("8"), "gold": Decimal("8")}
    )

    # Своя наценка для вида товара (вместо наценки уровня). У Steam маржа тонкая.
    kind_markups: dict[str, Decimal] = field(default_factory=lambda: {"steam_topup": Decimal("1.5")})

    # Первый админ создаётся при запуске, если таких пользователей ещё нет.
    admin_email: str = ""
    admin_password: str = ""

    # Фоновый обработчик (проверка заказов, обновление каталога) внутри веб-процесса.
    run_worker: bool = True
    catalog_sync_minutes: int = 60
    order_poll_seconds: int = 20

    # Предупреждение, когда баланс у поставщика меньше этой суммы (USD).
    supplier_low_balance: Decimal = Decimal("50")
    alert_telegram_token: str = ""
    alert_telegram_chat_id: str = ""

    # Новые клиенты ждут одобрения админа.
    require_approval: bool = True
    cookie_secure: bool = False

    # Способы пополнения: код → реквизиты (показываются клиенту). Пустые не показываются.
    pay_methods: dict[str, str] = field(default_factory=dict)
    # Курс сомони за 1 USD — для способов оплаты в TJS.
    tjs_rate: Decimal = Decimal("10.9")
    pay_min_usd: Decimal = Decimal("5")
    # Минимальное пополнение в сомони и порог «мало денег» на балансе клиента, $
    pay_min_tjs: Decimal = Decimal("500")
    low_balance_usd: Decimal = Decimal("10")

    # Почта для уведомлений клиентам (необязательно).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Куда писать клиентам для пополнения баланса и поддержки (например, @donatix_support).
    support_contact: str = ""
    # Код подтверждения сайта из Google Search Console и Яндекс Вебмастера (метатег)
    google_verify: str = ""
    yandex_verify: str = ""
    # Часовой пояс для аналитики, часы от UTC (Душанбе — 5)
    tz_offset: int = 5
    # Конструктор ботов: запускать ботов партнёров и по какому адресу они ходят в Donatix
    run_bots: bool = True
    internal_url: str = "http://127.0.0.1:8000"

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv(ROOT / ".env")
        secret = _env("DONATIX_SECRET_KEY")
        if not secret:
            # Без ключа сессии слетают при каждом перезапуске — годится только для разработки.
            secret = secrets.token_urlsafe(32)
        markups = {}
        for tier, default in (("bronze", "8"), ("silver", "8"), ("gold", "8")):
            markups[tier] = Decimal(_env(f"DONATIX_MARKUP_{tier.upper()}", default))
        pay_methods = {code: _env(f"DONATIX_PAY_{code.upper()}") for code in PAY_METHODS}
        pay_methods = {k: v.replace("\\n", "\n") for k, v in pay_methods.items() if v}
        kind_markups = {"steam_topup": Decimal(_env("DONATIX_MARKUP_STEAM", "1.5"))}
        if _env("DONATIX_MARKUP_STEAM_GIFT"):
            kind_markups["steam_gift"] = Decimal(_env("DONATIX_MARKUP_STEAM_GIFT"))
        return cls(
            secret_key=secret,
            db_path=Path(_env("DONATIX_DB", str(ROOT / "data" / "donatix.db"))),
            site_name=_env("DONATIX_SITE_NAME", "Donatix"),
            base_url=_env("DONATIX_BASE_URL", "http://localhost:8000").rstrip("/"),
            supplier=_env("DONATIX_SUPPLIER", "mock").lower(),
            fazer_api_key=_env("FAZER_API_KEY"),
            fazer_base_url=_env("FAZER_BASE_URL", "https://api.fzr.cards/api/v2").rstrip("/"),
            fazer_steam_discount=Decimal(_env("FAZER_STEAM_DISCOUNT", "2.5")),
            fazer_image_base=_env("FAZER_IMAGE_BASE"),
            fazer_catalog_pause=float(_env("FAZER_CATALOG_PAUSE") or 2.0),
            markups=markups,
            kind_markups=kind_markups,
            admin_email=_env("DONATIX_ADMIN_EMAIL").lower(),
            admin_password=_env("DONATIX_ADMIN_PASSWORD"),
            run_worker=_flag("DONATIX_RUN_WORKER", True),
            # не чаще раза в 30 минут: полная загрузка каталога съедает лимит ключа FazerCards
            catalog_sync_minutes=max(30, int(_env("DONATIX_CATALOG_SYNC_MINUTES", "60"))),
            order_poll_seconds=int(_env("DONATIX_ORDER_POLL_SECONDS", "20")),
            supplier_low_balance=Decimal(_env("DONATIX_SUPPLIER_LOW_BALANCE", "50")),
            alert_telegram_token=_env("DONATIX_ALERT_TELEGRAM_TOKEN"),
            alert_telegram_chat_id=_env("DONATIX_ALERT_TELEGRAM_CHAT_ID"),
            require_approval=_flag("DONATIX_REQUIRE_APPROVAL", True),
            cookie_secure=_flag("DONATIX_COOKIE_SECURE", False),
            support_contact=_env("DONATIX_SUPPORT_CONTACT"),
            google_verify=_env("DONATIX_GOOGLE_VERIFY"),
            yandex_verify=_env("DONATIX_YANDEX_VERIFY"),
            tz_offset=int(_env("DONATIX_TZ_OFFSET") or 5),
            run_bots=_flag("DONATIX_RUN_BOTS", True),
            internal_url=_env("DONATIX_INTERNAL_URL") or "http://127.0.0.1:8000",
            pay_methods=pay_methods,
            tjs_rate=Decimal(_env("DONATIX_TJS_RATE", "10.9")),
            pay_min_usd=Decimal(_env("DONATIX_PAY_MIN_USD", "5")),
            pay_min_tjs=Decimal(_env("DONATIX_PAY_MIN_TJS", "500")),
            low_balance_usd=Decimal(_env("DONATIX_LOW_BALANCE_USD", "10")),
            smtp_host=_env("DONATIX_SMTP_HOST"),
            smtp_port=int(_env("DONATIX_SMTP_PORT", "587")),
            smtp_user=_env("DONATIX_SMTP_USER"),
            smtp_password=_env("DONATIX_SMTP_PASSWORD"),
            smtp_from=_env("DONATIX_SMTP_FROM"),
        )
