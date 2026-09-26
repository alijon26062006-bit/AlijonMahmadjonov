"""Танзимот: аз муҳити система ё аз файли .env хонда мешавад."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv ихтиёрӣ аст
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):  # type: ignore[misc]
        return False

ROOT = Path(__file__).resolve().parent.parent

# Реквизити пешфарз — админ метавонад онҳоро аз панел иваз кунад.
DEFAULT_CARD = "0000 0000 0000 0000"
DEFAULT_HOLDER = "ALIJON M."

# Шаблони ҳавола ба Душанбе Сити (DC Pay) — корт, маблағ ва код худкор пур мешаванд.
DEFAULT_PAY_LINK = "http://pay.dc.tj/?A={card}&s={amount}&c={comment}&f1=133&FIELD2=&FIELD3="

# Шаблони ҳавола ба Alif Mobi.
DEFAULT_ALIF_LINK = "https://alifmobi.page.link/providers?id=124&amount={amount}&account={account}"

FIRELOOT_BASE = "https://partner.firelootshop.com/api/v1"
DONATIX_BASE = "https://donatix.tj/api/v1"


def _ids(raw: str) -> tuple[int, ...]:
    out: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return tuple(dict.fromkeys(out))


def _int(raw: str | None, default: int) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: tuple[int, ...]
    db_path: Path
    currency: str
    support: str
    reviews_url: str
    channel_url: str
    card_number: str
    card_holder: str
    pay_link: str
    alif_link: str
    alif_account: str
    min_topup: int          # дар дирам
    max_topup: int          # дар дирам
    supplier: str           # fireloot | manual
    supplier_url: str
    supplier_key: str
    log_level: str
    # Donatix — танҳо Telegram Stars ва Premium. Холӣ — Stars аз FireLoot, Premium дастӣ.
    donatix_key: str = ""
    donatix_url: str = DONATIX_BASE

    @property
    def has_supplier(self) -> bool:
        return self.supplier == "fireloot" and bool(self.supplier_url and self.supplier_key)

    @property
    def has_donatix(self) -> bool:
        return bool(self.donatix_key and self.donatix_url)

    @property
    def has_pay_link(self) -> bool:
        return bool(self.pay_link.strip())

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def load_config(env_file: str | os.PathLike[str] | None = None) -> Config:
    """Танзимотро мехонад. `env_file` барои тестҳо фоиданок аст."""
    load_dotenv(env_file or ROOT / ".env", override=False)

    token = os.getenv("SHOP_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "SHOP_BOT_TOKEN холӣ аст. Токенро аз @BotFather гиред "
            "ва дар файли .env нависед (намуна: .env.shop.example)."
        )

    data_dir = Path(os.getenv("SHOP_DATA_DIR", str(ROOT / "data"))).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        token=token,
        admin_ids=_ids(os.getenv("SHOP_ADMIN_IDS", "")),
        db_path=data_dir / os.getenv("SHOP_DB_NAME", "shop.sqlite3"),
        currency=os.getenv("SHOP_CURRENCY", "с."),
        support=os.getenv("SHOP_SUPPORT", "").lstrip("@"),
        reviews_url=os.getenv("SHOP_REVIEWS_URL", ""),
        channel_url=os.getenv("SHOP_CHANNEL_URL", ""),
        card_number=os.getenv("SHOP_CARD_NUMBER", DEFAULT_CARD),
        card_holder=os.getenv("SHOP_CARD_HOLDER", DEFAULT_HOLDER),
        pay_link=os.getenv("SHOP_PAY_LINK", DEFAULT_PAY_LINK),
        alif_link=os.getenv("SHOP_ALIF_LINK", DEFAULT_ALIF_LINK),
        alif_account=os.getenv("SHOP_ALIF_ACCOUNT", ""),
        min_topup=_int(os.getenv("SHOP_MIN_TOPUP"), 1000),      # 10.00 с.
        max_topup=_int(os.getenv("SHOP_MAX_TOPUP"), 5_000_00),  # 5000 с.
        supplier=os.getenv("SHOP_SUPPLIER", "fireloot").strip().lower(),
        supplier_url=os.getenv("SHOP_SUPPLIER_URL", FIRELOOT_BASE),
        supplier_key=os.getenv("SHOP_SUPPLIER_KEY", os.getenv("FIRELOOT_KEY", "")),
        log_level=os.getenv("SHOP_LOG_LEVEL", "INFO").upper(),
        donatix_key=os.getenv("SHOP_DONATIX_KEY", "").strip(),
        donatix_url=(os.getenv("SHOP_DONATIX_URL", "").strip() or DONATIX_BASE),
    )
