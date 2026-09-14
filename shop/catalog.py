"""Каталоги молҳо. Нархҳо дар дирам (1 сомонӣ = 100 дирам) нигоҳ дошта мешаванд.

Ин рӯйхат танҳо қиматҳои ибтидоист: ҳангоми аввалин оғоз ба базаи маълумот
кӯчонида мешавад, баъд админ нархҳоро аз панели худ иваз карда метавонад.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ── Бахшҳо ────────────────────────────────────────────────────────────
CAT_STARS = "tg_stars"
CAT_PREMIUM = "tg_premium"
CAT_FF_CIS = "ff_cis"
CAT_FF_ID = "ff_id"
CAT_PUBG = "pubg"

CATEGORIES = (CAT_STARS, CAT_PREMIUM, CAT_FF_CIS, CAT_FF_ID, CAT_PUBG)

# Чӣ тавр молро ба харидор мерасонем:
#   "username" — ба @username-и Telegram
#   "player"   — ба ID-и бозӣ (бо тафтиши лақаб)
TargetKind = Literal["username", "player"]


@dataclass(frozen=True)
class Category:
    code: str
    title: str          # номи бахш барои тугма
    unit: str           # воҳиди ченак: ситора, алмос, UC, моҳ
    target: TargetKind
    game: str           # калиди бозӣ барои API-и таъминкунанда
    icon: str
    hint: str           # тавзеҳ дар экрани вориди ID/username


CATEGORY_INFO: dict[str, Category] = {
    CAT_STARS: Category(
        code=CAT_STARS,
        title="Telegram Stars",
        unit="ситора",
        target="username",
        game="telegram_stars",
        icon="⭐️",
        hint="@username-и аккаунтеро нависед, ки ситораҳо ба он равона мешаванд.",
    ),
    CAT_PREMIUM: Category(
        code=CAT_PREMIUM,
        title="Telegram Premium",
        unit="моҳ",
        target="username",
        game="telegram_premium",
        icon="👑",
        hint="@username-и аккаунтеро нависед, ки Premium ба он фаъол мешавад.",
    ),
    CAT_FF_CIS: Category(
        code=CAT_FF_CIS,
        title="Free Fire (ИДМ)",
        unit="алмос",
        target="player",
        game="freefire_cis",
        icon="🔥",
        hint="ID-и бозигари Free Fire (ИДМ)-ро нависед — танҳо рақамҳо.",
    ),
    CAT_FF_ID: Category(
        code=CAT_FF_ID,
        title="Free Fire (Индонезия)",
        unit="алмос",
        target="player",
        game="freefire_id",
        icon="🇮🇩",
        hint="ID-и бозигари Free Fire (Индонезия)-ро нависед — танҳо рақамҳо.",
    ),
    CAT_PUBG: Category(
        code=CAT_PUBG,
        title="PUBG Mobile",
        unit="UC",
        target="player",
        game="pubg_mobile",
        icon="🎯",
        hint="ID-и бозигари PUBG Mobile-ро нависед — танҳо рақамҳо.",
    ),
}


@dataclass(frozen=True)
class Product:
    code: str
    category: str
    title: str
    amount: int      # шумораи ситора/алмос/UC/моҳ
    price: int       # дирам


def _p(code: str, category: str, title: str, amount: int, price_somoni: float) -> Product:
    return Product(code, category, title, amount, round(price_somoni * 100))


DEFAULT_PRODUCTS: tuple[Product, ...] = (
    # ── Telegram Stars ────────────────────────────────────────────────
    _p("stars_50", CAT_STARS, "50 ⭐️", 50, 11),
    _p("stars_75", CAT_STARS, "75 ⭐️", 75, 16),
    _p("stars_100", CAT_STARS, "100 ⭐️", 100, 21),
    _p("stars_150", CAT_STARS, "150 ⭐️", 150, 31),
    _p("stars_250", CAT_STARS, "250 ⭐️", 250, 51),
    _p("stars_350", CAT_STARS, "350 ⭐️", 350, 71),
    _p("stars_500", CAT_STARS, "500 ⭐️", 500, 100),
    _p("stars_750", CAT_STARS, "750 ⭐️", 750, 149),
    _p("stars_1000", CAT_STARS, "1000 ⭐️", 1000, 197),
    _p("stars_1500", CAT_STARS, "1500 ⭐️", 1500, 295),
    _p("stars_2500", CAT_STARS, "2500 ⭐️", 2500, 490),
    _p("stars_5000", CAT_STARS, "5000 ⭐️", 5000, 975),
    _p("stars_10000", CAT_STARS, "10000 ⭐️", 10000, 1940),
    # ── Telegram Premium ──────────────────────────────────────────────
    _p("prem_3", CAT_PREMIUM, "Premium — 3 моҳ", 3, 165),
    _p("prem_6", CAT_PREMIUM, "Premium — 6 моҳ", 6, 225),
    _p("prem_12", CAT_PREMIUM, "Premium — 12 моҳ", 12, 390),
    # ── Free Fire ИДМ ─────────────────────────────────────────────────
    _p("ffcis_100", CAT_FF_CIS, "100 💎", 100, 24),
    _p("ffcis_310", CAT_FF_CIS, "310 💎", 310, 70),
    _p("ffcis_520", CAT_FF_CIS, "520 💎", 520, 115),
    _p("ffcis_1060", CAT_FF_CIS, "1060 💎", 1060, 230),
    _p("ffcis_2180", CAT_FF_CIS, "2180 💎", 2180, 460),
    _p("ffcis_5600", CAT_FF_CIS, "5600 💎", 5600, 1150),
    _p("ffcis_week", CAT_FF_CIS, "Обунаи ҳафтаина", 0, 55),
    _p("ffcis_month", CAT_FF_CIS, "Обунаи моҳона", 0, 260),
    # ── Free Fire Индонезия ───────────────────────────────────────────
    _p("ffid_5", CAT_FF_ID, "5 💎", 5, 2),
    _p("ffid_12", CAT_FF_ID, "12 💎", 12, 4),
    _p("ffid_50", CAT_FF_ID, "50 💎", 50, 14),
    _p("ffid_70", CAT_FF_ID, "70 💎", 70, 19),
    _p("ffid_140", CAT_FF_ID, "140 💎", 140, 37),
    _p("ffid_355", CAT_FF_ID, "355 💎", 355, 90),
    _p("ffid_720", CAT_FF_ID, "720 💎", 720, 180),
    _p("ffid_1450", CAT_FF_ID, "1450 💎", 1450, 355),
    _p("ffid_2180", CAT_FF_ID, "2180 💎", 2180, 530),
    _p("ffid_week", CAT_FF_ID, "Обунаи ҳафтаина", 0, 45),
    _p("ffid_month", CAT_FF_ID, "Обунаи моҳона", 0, 215),
    # ── PUBG Mobile ───────────────────────────────────────────────────
    _p("pubg_60", CAT_PUBG, "60 UC", 60, 22),
    _p("pubg_325", CAT_PUBG, "325 UC", 325, 105),
    _p("pubg_660", CAT_PUBG, "660 UC", 660, 210),
    _p("pubg_1800", CAT_PUBG, "1800 UC", 1800, 520),
    _p("pubg_3850", CAT_PUBG, "3850 UC", 3850, 1040),
    _p("pubg_8100", CAT_PUBG, "8100 UC", 8100, 2080),
)

# Маблағҳои тайёр барои пур кардани ҳисоб (дирам).
TOPUP_PRESETS: tuple[int, ...] = (
    20_00, 50_00, 100_00, 200_00, 300_00, 500_00, 1000_00, 2000_00,
)


def category_of(code: str) -> Category:
    return CATEGORY_INFO[code]


def default_products_for(category: str) -> tuple[Product, ...]:
    return tuple(p for p in DEFAULT_PRODUCTS if p.category == category)
