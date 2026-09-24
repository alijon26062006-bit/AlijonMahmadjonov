"""Общий интерфейс поставщика. Сегодня это FazerCards, завтра можно добавить второго."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable, Protocol

KINDS = ("telegram_stars", "telegram_premium", "steam_topup", "steam_gift", "topup", "gift_card")

STEAM_CURRENCIES = ("USD", "RUB", "KZT", "UAH")

KIND_TITLES = {
    "telegram_stars": "Telegram Stars",
    "telegram_premium": "Telegram Premium",
    "steam_topup": "Пополнение Steam",
    "steam_gift": "Steam Гифты",
    "topup": "Пополнение сервисов",
    "gift_card": "Подарочные карты",
}


@dataclass
class ProductData:
    id: str
    kind: str
    category_id: str
    category_name: str
    name: str
    base_price: Decimal
    unit: str = "item"
    min_qty: int = 1
    max_qty: int = 1
    stock: int | None = None
    fields: list[dict[str, str]] = field(default_factory=list)
    supplier_ref: dict[str, Any] = field(default_factory=dict)
    image_url: str | None = None
    region: str | None = None


@dataclass
class SupplierOrder:
    order_id: str | None
    status: str  # processing | completed | failed
    raw_status: str = ""
    delivery: dict[str, Any] | None = None
    message: str = ""


def steam_gift_product() -> ProductData:
    """Один «товар» на все Steam-гифты: цена берётся у поставщика по изданию и региону.
    base_price = 1 — платим поставщику ровно его цену в USD."""
    return ProductData(
        id="steam-gift", kind="steam_gift", category_id="steam", category_name="Steam",
        name="Steam Гифты", base_price=Decimal(1), unit="usd",
        fields=[
            {"key": "app_id", "label": "App ID", "type": "number"},
            {"key": "sub_id", "label": "ID пакета", "type": "number"},
            {"key": "region", "label": "Регион", "type": "text"},
            {"key": "invite_url", "label": "Steam Invite ссылка", "type": "url"},
        ],
    )


class SupplierError(Exception):
    """Базовая ошибка поставщика."""


class SupplierRejected(SupplierError):
    """Поставщик точно отказал (4xx): заказа у него нет, деньги клиенту можно вернуть."""

    def __init__(self, message: str, code: str = "", http_status: int = 0):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class SupplierUnavailable(SupplierError):
    """Непонятно, прошёл ли запрос (таймаут, 5xx, сеть). Деньги не возвращаем,
    пока не выясним статус."""


# Статусы поставщика → наши. Точного списка в документации FazerCards нет,
# поэтому незнакомый статус считаем «ещё в работе».
_DONE = {"completed", "complete", "success", "succeeded", "delivered", "done", "fulfilled"}
_FAILED = {"failed", "fail", "error", "cancelled", "canceled", "rejected", "refunded", "declined", "expired"}


_IMAGE_KEYS = ("image", "image_url", "imageUrl", "cover", "cover_url", "coverUrl", "logo", "logo_url",
               "icon", "icon_url", "banner", "picture", "img", "thumbnail")


def pick_image(*sources: Any) -> str | None:
    """Найти ссылку на картинку в ответе поставщика. Точное имя поля в документации
    не указано, поэтому смотрим типичные варианты, в том числе во вложенном "ui"."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for obj in (src, src.get("ui"), src.get("media"), src.get("images")):
            if not isinstance(obj, dict):
                continue
            for key in _IMAGE_KEYS:
                val = obj.get(key)
                if isinstance(val, dict):
                    val = val.get("url") or val.get("src")
                if isinstance(val, str) and val.startswith(("https://", "http://")):
                    return val
    return None


# Регионы: код → как показываем клиенту. Незнакомый код показываем как есть.
REGION_TITLES = {
    "GLOBAL": "Глобальный", "WW": "Глобальный", "CIS": "СНГ", "RU": "Россия", "KZ": "Казахстан",
    "UA": "Украина", "BY": "Беларусь", "UZ": "Узбекистан", "TJ": "Таджикистан", "KG": "Киргизия",
    "TR": "Турция", "EU": "Европа", "US": "США", "UK": "Великобритания", "GB": "Великобритания",
    "DE": "Германия", "PL": "Польша", "FR": "Франция", "IN": "Индия", "ID": "Индонезия",
    "PH": "Филиппины", "MY": "Малайзия", "SG": "Сингапур", "TH": "Таиланд", "VN": "Вьетнам",
    "BR": "Бразилия", "LATAM": "Лат. Америка", "MENA": "Ближний Восток", "AE": "ОАЭ", "SA": "Сауд. Аравия",
    "AR": "Аргентина", "MX": "Мексика", "JP": "Япония", "KR": "Корея", "CN": "Китай", "TW": "Тайвань",
    "ASIA": "Азия", "SEA": "Юго-Вост. Азия", "NA": "Сев. Америка",
}
_REGION_WORDS = {
    "global": "GLOBAL", "глобал": "GLOBAL", "worldwide": "GLOBAL", "россия": "RU", "russia": "RU",
    "турция": "TR", "turkey": "TR", "türkiye": "TR", "казахстан": "KZ", "kazakhstan": "KZ",
    "europe": "EU", "европа": "EU", "снг": "CIS", "usa": "US", "indonesia": "ID", "индонезия": "ID",
    "philippines": "PH", "malaysia": "MY", "brazil": "BR", "india": "IN", "ukraine": "UA", "украина": "UA",
}
_REGION_KEYS = ("region", "region_code", "regionCode", "country", "country_code", "countryCode", "server_region")


def region_title(code: str | None) -> str:
    return REGION_TITLES.get((code or "").upper(), code or "")


def pick_region(name: str = "", *sources: Any) -> str | None:
    """Регион товара: из полей ответа поставщика, иначе — из названия («… (TR)», «Global»)."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in _REGION_KEYS:
            val = src.get(key)
            if isinstance(val, dict):
                val = val.get("code") or val.get("name")
            if isinstance(val, str) and val.strip():
                return _norm_region(val)
        regions = src.get("regions")
        if isinstance(regions, list) and len(regions) == 1 and isinstance(regions[0], str):
            return _norm_region(regions[0])
    for token in re.findall(r"[\(\[]([^\)\]]{2,20})[\)\]]", name):
        code = _norm_region(token, strict=True)
        if code:
            return code
    for word in re.findall(r"[\wÀ-ž]+", name.lower()):
        if word in _REGION_WORDS:
            return _REGION_WORDS[word]
    return None


def _norm_region(value: str, strict: bool = False) -> str | None:
    v = value.strip()
    if v.lower() in _REGION_WORDS:
        return _REGION_WORDS[v.lower()]
    if v.upper() in REGION_TITLES:
        return v.upper()
    if strict:
        return None
    return v[:20]


def normalize_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in _DONE:
        return "completed"
    if value in _FAILED:
        return "failed"
    return "processing"


class Supplier(Protocol):
    name: str

    def fetch_catalog(self) -> Iterable[ProductData]: ...

    def create_order(
        self, product: dict[str, Any], quantity: int, fields: dict[str, str], idem_key: str
    ) -> SupplierOrder: ...

    def get_order(self, supplier_order_id: str) -> SupplierOrder: ...

    def balance(self) -> Decimal: ...

    def steam_gift_games(self) -> list[dict[str, Any]]:
        """Каталог игр для Steam-гифтов: [{"appid": 730, "name": "Counter-Strike 2"}, ...]."""
        ...

    def steam_gift_offers(self, appid: int) -> list[dict[str, Any]]:
        """Издания игры: [{"sub_id", "name", "regions": [{"region", "price"}]}]."""
        ...

    def validate_id_categories(self) -> list[str]:
        """category_id игр, где можно проверить аккаунт по ID до оплаты."""
        ...

    def validate_account(self, category_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """{"valid", "player_name", "region", "message"}."""
        ...

    def check_steam_login(self, login: str) -> bool:
        """Можно ли пополнить этот Steam-аккаунт."""
        ...

    def is_idempotent(self, kind: str) -> bool:
        """Можно ли безопасно повторить создание заказа с тем же ключом."""
        ...
